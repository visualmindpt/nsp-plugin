"""
ReferenceMatchTrainer — trainer para o ReferenceRegressor.

Semelhante ao OptimizedRefinementTrainer mas:
  - Batch contém 'style_fingerprint' em vez de 'label' (preset_id)
  - Loss é WeightedMSELoss sobre parâmetros absolutos
  - Métricas: MAE por parâmetro + MAE médio global
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader

from .reference_regressor import ReferenceRegressor
from .training_utils import WeightedMSELoss

logger = logging.getLogger(__name__)


class ReferenceMatchTrainer:
    """
    Trainer para o ReferenceRegressor (modo Reference Match).

    Features:
    - OneCycleLR scheduler (pct_start=0.1)
    - Mixed precision training
    - Gradient clipping
    - Early stopping com checkpoint
    """

    def __init__(
        self,
        model: ReferenceRegressor,
        param_weights: torch.Tensor,
        device: str = 'cpu',
        use_mixed_precision: bool = True,
        weight_decay: float = 0.02,
    ) -> None:
        self.model = model.to(device)
        self.device = device
        self.criterion = WeightedMSELoss(param_weights)
        self.use_mixed_precision = use_mixed_precision and device != 'mps'
        self.scaler = GradScaler() if self.use_mixed_precision else None
        self.optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=weight_decay)
        self.scheduler: Optional[optim.lr_scheduler._LRScheduler] = None

        self.train_losses: List[float] = []
        self.val_losses: List[float] = []
        self.learning_rates: List[float] = []
        self.best_val_loss = float('inf')

    def train_epoch(self, loader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0

        for batch in loader:
            stat = batch['stat_features'].to(self.device)
            deep = batch['deep_features'].to(self.device)
            style = batch['style_fingerprint'].to(self.device)
            targets = batch['target_params'].to(self.device)

            self.optimizer.zero_grad()

            if self.use_mixed_precision:
                with autocast():
                    preds = self.model(stat, deep, style)
                    loss = self.criterion(preds, targets)
                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                preds = self.model(stat, deep, style)
                loss = self.criterion(preds, targets)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()

            total_loss += loss.item()
            if self.scheduler is not None:
                self.scheduler.step()

        return total_loss / max(len(loader), 1)

    def validate(self, loader: DataLoader) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
        self.model.eval()
        total_loss = 0.0
        all_preds: List[np.ndarray] = []
        all_targets: List[np.ndarray] = []

        with torch.no_grad():
            for batch in loader:
                stat = batch['stat_features'].to(self.device)
                deep = batch['deep_features'].to(self.device)
                style = batch['style_fingerprint'].to(self.device)
                targets = batch['target_params'].to(self.device)

                if self.use_mixed_precision:
                    with autocast():
                        preds = self.model(stat, deep, style)
                        loss = self.criterion(preds, targets)
                else:
                    preds = self.model(stat, deep, style)
                    loss = self.criterion(preds, targets)

                total_loss += loss.item()
                all_preds.append(preds.cpu().numpy())
                all_targets.append(targets.cpu().numpy())

        val_loss = total_loss / max(len(loader), 1)
        predictions = np.vstack(all_preds) if all_preds else np.array([])
        tgts = np.vstack(all_targets) if all_targets else np.array([])
        mae_per_param = np.abs(predictions - tgts).mean(axis=0) if len(predictions) > 0 else np.array([])
        return val_loss, mae_per_param, predictions, tgts

    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: int = 100,
        patience: int = 15,
        param_columns: List[str] = [],
        scaler_params=None,
        max_lr: float = 0.005,
        checkpoint_path: Optional[Path] = None,
    ) -> ReferenceRegressor:
        """
        Treina o ReferenceRegressor.

        Args:
            train_loader: DataLoader de treino (ReferencePairDataset)
            val_loader:   DataLoader de validação
            epochs:       Número máximo de épocas
            patience:     Paciência para early stopping
            param_columns: Nomes dos parâmetros (para logging)
            scaler_params: Scaler para desnormalizar MAE (opcional)
            max_lr:        LR máximo para OneCycleLR
            checkpoint_path: Path para guardar checkpoint (default: 'reference_model.pth')

        Returns:
            Modelo treinado
        """
        steps_per_epoch = len(train_loader)
        total_steps = epochs * steps_per_epoch

        self.scheduler = optim.lr_scheduler.OneCycleLR(
            self.optimizer,
            max_lr=max_lr,
            total_steps=total_steps,
            pct_start=0.1,
            anneal_strategy='cos',
            div_factor=25.0,
            final_div_factor=10000.0,
        )

        ckpt = Path(checkpoint_path) if checkpoint_path else Path('reference_model.pth')
        patience_counter = 0

        logger.info(f"[ReferenceMatchTrainer] OneCycleLR max_lr={max_lr}")
        logger.info(f"[ReferenceMatchTrainer] Mixed precision: {self.use_mixed_precision}")

        for epoch in range(epochs):
            t0 = time.time()
            train_loss = self.train_epoch(train_loader)
            val_loss, mae_per_param, _, _ = self.validate(val_loader)
            current_lr = self.optimizer.param_groups[0]['lr']

            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.learning_rates.append(current_lr)

            elapsed = time.time() - t0
            logger.info(f"Epoch {epoch + 1}/{epochs} ({elapsed:.1f}s)")
            logger.info(f"  Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f} | LR: {current_lr:.6f}")

            if (epoch + 1) % 10 == 0 and len(mae_per_param) > 0 and param_columns:
                logger.info("  MAE por parâmetro (top 10):")
                for i, col in enumerate(param_columns[:10]):
                    mae = mae_per_param[i]
                    if scaler_params is not None:
                        mae = mae * scaler_params.scale_[i]
                    logger.info(f"    {col:20s}: {mae:.4f}")

            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), ckpt)
                logger.info("  Melhor modelo guardado!")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping após {epoch + 1} epochs")
                    break

        # Carregar melhor
        self.model.load_state_dict(torch.load(ckpt))

        # Análise final
        _, final_mae, _, _ = self.validate(val_loader)
        logger.info("\nAnálise Final de Precisão (Reference Match):")
        logger.info("=" * 50)
        for i, col in enumerate(param_columns):
            mae = final_mae[i] if i < len(final_mae) else 0.0
            mae_real = mae * scaler_params.scale_[i] if scaler_params is not None else mae
            logger.info(f"{col:20s}: MAE = {mae_real:.3f}")

        return self.model
