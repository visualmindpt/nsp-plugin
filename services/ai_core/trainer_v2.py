"""
Trainers otimizados para datasets pequenos.

FASE 1 - Otimizações:
- OneCycleLR scheduler para convergência mais rápida
- Mixed precision training para melhor performance
- Logging detalhado com learning rate e tempo
- Gradient accumulation opcional
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, classification_report
import numpy as np
import logging
import time
from typing import Optional, Tuple, List

from .model_architectures_v2 import OptimizedPresetClassifier, OptimizedRefinementRegressor
from .training_utils import WeightedMSELoss

logger = logging.getLogger(__name__)


class OptimizedClassifierTrainer:
    """
    Trainer otimizado para o classificador de presets.

    Melhorias:
    - OneCycleLR scheduler
    - Mixed precision training
    - Logging detalhado com LR e tempo
    - Gradient clipping
    """

    def __init__(self,
                 model: OptimizedPresetClassifier,
                 device: str = 'cuda',
                 use_mixed_precision: bool = True,
                 weight_decay: float = 0.01,
                 class_weights: Optional[torch.Tensor] = None):
        """
        Inicializa o trainer.

        Args:
            model: Modelo a treinar
            device: Dispositivo (cuda, mps, cpu)
            use_mixed_precision: Se True, usa mixed precision training
            class_weights: Pesos por classe para CrossEntropyLoss (combate class imbalance)
        """
        self.model = model.to(device)
        self.device = device
        if class_weights is not None:
            self.criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
        else:
            self.criterion = nn.CrossEntropyLoss()
        self.use_mixed_precision = use_mixed_precision and device != 'mps'

        # Mixed precision scaler
        self.scaler = GradScaler() if self.use_mixed_precision else None

        # Optimizer com weight decay
        self.optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=weight_decay)

        # Scheduler será configurado no método train
        self.scheduler: Optional[optim.lr_scheduler._LRScheduler] = None

        # Histórico
        self.train_losses: List[float] = []
        self.val_losses: List[float] = []
        self.val_accuracies: List[float] = []
        self.learning_rates: List[float] = []

    def train_epoch(self, train_loader: DataLoader) -> float:
        """Treina por uma época."""
        self.model.train()
        total_loss = 0
        epoch_start = time.time()

        for batch in train_loader:
            stat_feat = batch['stat_features'].to(self.device)
            deep_feat = batch['deep_features'].to(self.device)
            labels = batch['label'].to(self.device)

            self.optimizer.zero_grad()

            # Mixed precision forward pass
            if self.use_mixed_precision:
                with autocast():
                    outputs = self.model(stat_feat, deep_feat)
                    loss = self.criterion(outputs, labels)

                # Backward com scaler
                self.scaler.scale(loss).backward()

                # Gradient clipping
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

                # Optimizer step
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                outputs = self.model(stat_feat, deep_feat)
                loss = self.criterion(outputs, labels)
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

                self.optimizer.step()

            total_loss += loss.item()

            # Update scheduler a cada batch (OneCycleLR)
            if self.scheduler is not None:
                self.scheduler.step()

        epoch_time = time.time() - epoch_start

        # Prevent division by zero
        if len(train_loader) == 0:
            logger.warning("⚠️ Train loader is empty - no batches to process!")
            return 0.0

        avg_loss = total_loss / len(train_loader)

        return avg_loss

    def validate(self, val_loader: DataLoader) -> Tuple[float, float, List, List]:
        """Valida o modelo."""
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for batch in val_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                labels = batch['label'].to(self.device)

                if self.use_mixed_precision:
                    with autocast():
                        outputs = self.model(stat_feat, deep_feat)
                        loss = self.criterion(outputs, labels)
                else:
                    outputs = self.model(stat_feat, deep_feat)
                    loss = self.criterion(outputs, labels)

                total_loss += loss.item()

                _, preds = torch.max(outputs, 1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        # Prevent division by zero
        if len(val_loader) == 0:
            logger.warning("⚠️ Validation loader is empty - no batches to process!")
            return 0.0, 0.0, [], []

        val_loss = total_loss / len(val_loader)
        val_acc = accuracy_score(all_labels, all_preds) if all_labels else 0.0

        return val_loss, val_acc, all_preds, all_labels

    def train(self,
              train_loader: DataLoader,
              val_loader: DataLoader,
              epochs: int = 50,
              patience: int = 7,
              num_presets: int = 4,
              max_lr: float = 0.01,
              checkpoint_path: Optional[Path] = None) -> OptimizedPresetClassifier:
        """
        Treina o modelo.

        Args:
            train_loader: DataLoader de treino
            val_loader: DataLoader de validação
            epochs: Número máximo de épocas
            patience: Paciência para early stopping
            num_presets: Número de presets (para relatório)
            max_lr: Learning rate máximo para OneCycleLR

        Returns:
            Modelo treinado
        """
        # Configurar OneCycleLR
        steps_per_epoch = len(train_loader)
        total_steps = epochs * steps_per_epoch

        self.scheduler = optim.lr_scheduler.OneCycleLR(
            self.optimizer,
            max_lr=max_lr,
            total_steps=total_steps,
            pct_start=0.1,
            anneal_strategy='cos',
            div_factor=25.0,
            final_div_factor=10000.0
        )

        ckpt = Path(checkpoint_path) if checkpoint_path else Path('best_preset_classifier_v2.pth')
        best_val_loss = float('inf')
        patience_counter = 0

        logger.info(f"Iniciando treino com OneCycleLR (max_lr={max_lr})")
        logger.info(f"Mixed precision: {'Ativado' if self.use_mixed_precision else 'Desativado'}")

        for epoch in range(epochs):
            epoch_start = time.time()

            train_loss = self.train_epoch(train_loader)
            val_loss, val_acc, preds, labels = self.validate(val_loader)

            # Obter LR atual
            current_lr = self.optimizer.param_groups[0]['lr']

            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.val_accuracies.append(val_acc)
            self.learning_rates.append(current_lr)

            epoch_time = time.time() - epoch_start

            logger.info(f"Epoch {epoch+1}/{epochs} ({epoch_time:.1f}s)")
            logger.info(f"  Train Loss: {train_loss:.4f}")
            logger.info(f"  Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")
            logger.info(f"  LR: {current_lr:.6f}")

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), ckpt)
                logger.info("  Melhor modelo guardado!")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"\nEarly stopping triggered após {epoch+1} epochs")
                    break

        # Carregar melhor modelo
        self.model.load_state_dict(torch.load(ckpt))

        # Report final
        _, _, final_preds, final_labels = self.validate(val_loader)
        logger.info("\nClassification Report:")
        report_labels = list(range(num_presets))
        target_names = [f'Preset {i + 1}' for i in report_labels]
        logger.info(classification_report(final_labels, final_preds,
                                          labels=report_labels,
                                          target_names=target_names,
                                          zero_division=0))

        return self.model


class OptimizedRefinementTrainer:
    """
    Trainer otimizado para o regressor de refinamento.

    Melhorias:
    - OneCycleLR scheduler
    - Mixed precision training
    - Logging detalhado com LR e tempo
    - Gradient accumulation opcional
    """

    def __init__(self,
                 model: OptimizedRefinementRegressor,
                 param_weights: torch.Tensor,
                 device: str = 'cuda',
                 use_mixed_precision: bool = True,
                 weight_decay: float = 0.02):
        """
        Inicializa o trainer.

        Args:
            model: Modelo a treinar
            param_weights: Pesos dos parâmetros para loss
            device: Dispositivo (cuda, mps, cpu)
            use_mixed_precision: Se True, usa mixed precision training
        """
        self.model = model.to(device)
        self.device = device
        self.criterion = WeightedMSELoss(param_weights)
        self.use_mixed_precision = use_mixed_precision and device != 'mps'

        # Mixed precision scaler
        self.scaler = GradScaler() if self.use_mixed_precision else None

        # Optimizer com weight decay mais agressivo
        self.optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=weight_decay)

        # Scheduler será configurado no método train
        self.scheduler: Optional[optim.lr_scheduler._LRScheduler] = None

        # Histórico
        self.train_losses: List[float] = []
        self.val_losses: List[float] = []
        self.learning_rates: List[float] = []
        self.best_val_loss = float('inf')

    def train_epoch(self, train_loader: DataLoader) -> float:
        """Treina por uma época."""
        self.model.train()
        total_loss = 0

        for batch in train_loader:
            stat_feat = batch['stat_features'].to(self.device)
            deep_feat = batch['deep_features'].to(self.device)
            preset_id = batch['label'].to(self.device)
            deltas = batch['deltas'].to(self.device)

            self.optimizer.zero_grad()

            # Mixed precision forward pass
            if self.use_mixed_precision:
                with autocast():
                    predicted_deltas = self.model(stat_feat, deep_feat, preset_id)
                    loss = self.criterion(predicted_deltas, deltas)

                # Backward com scaler
                self.scaler.scale(loss).backward()

                # Gradient clipping
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

                # Optimizer step
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                predicted_deltas = self.model(stat_feat, deep_feat, preset_id)
                loss = self.criterion(predicted_deltas, deltas)
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

                self.optimizer.step()

            total_loss += loss.item()

            # Update scheduler a cada batch
            if self.scheduler is not None:
                self.scheduler.step()

        return total_loss / len(train_loader)

    def validate(self, val_loader: DataLoader) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
        """Valida o modelo."""
        self.model.eval()
        total_loss = 0
        all_predictions = []
        all_targets = []

        with torch.no_grad():
            for batch in val_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                preset_id = batch['label'].to(self.device)
                deltas = batch['deltas'].to(self.device)

                if self.use_mixed_precision:
                    with autocast():
                        predicted_deltas = self.model(stat_feat, deep_feat, preset_id)
                        loss = self.criterion(predicted_deltas, deltas)
                else:
                    predicted_deltas = self.model(stat_feat, deep_feat, preset_id)
                    loss = self.criterion(predicted_deltas, deltas)

                total_loss += loss.item()

                all_predictions.append(predicted_deltas.cpu().numpy())
                all_targets.append(deltas.cpu().numpy())

        val_loss = total_loss / len(val_loader)

        predictions = np.vstack(all_predictions)
        targets = np.vstack(all_targets)

        # Calcular MAE por parâmetro
        mae_per_param = np.abs(predictions - targets).mean(axis=0)

        return val_loss, mae_per_param, predictions, targets

    def train(self,
              train_loader: DataLoader,
              val_loader: DataLoader,
              epochs: int = 100,
              patience: int = 15,
              delta_columns: List[str] = [],
              scaler_deltas=None,
              max_lr: float = 0.005,
              checkpoint_path: Optional[Path] = None) -> OptimizedRefinementRegressor:
        """
        Treina o modelo.

        Args:
            train_loader: DataLoader de treino
            val_loader: DataLoader de validação
            epochs: Número máximo de épocas
            patience: Paciência para early stopping
            delta_columns: Nomes das colunas de delta
            scaler_deltas: Scaler para desnormalizar MAE
            max_lr: Learning rate máximo para OneCycleLR

        Returns:
            Modelo treinado
        """
        # Configurar OneCycleLR
        steps_per_epoch = len(train_loader)
        total_steps = epochs * steps_per_epoch

        self.scheduler = optim.lr_scheduler.OneCycleLR(
            self.optimizer,
            max_lr=max_lr,
            total_steps=total_steps,
            pct_start=0.1,
            anneal_strategy='cos',
            div_factor=25.0,
            final_div_factor=10000.0
        )

        ckpt = Path(checkpoint_path) if checkpoint_path else Path('best_refinement_model_v2.pth')
        patience_counter = 0

        logger.info(f"Iniciando treino com OneCycleLR (max_lr={max_lr})")
        logger.info(f"Mixed precision: {'Ativado' if self.use_mixed_precision else 'Desativado'}")

        for epoch in range(epochs):
            epoch_start = time.time()

            train_loss = self.train_epoch(train_loader)
            val_loss, mae_per_param, preds, targets = self.validate(val_loader)

            # Obter LR atual
            current_lr = self.optimizer.param_groups[0]['lr']

            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.learning_rates.append(current_lr)

            epoch_time = time.time() - epoch_start

            logger.info(f"\nEpoch {epoch+1}/{epochs} ({epoch_time:.1f}s)")
            logger.info(f"  Train Loss: {train_loss:.6f}")
            logger.info(f"  Val Loss: {val_loss:.6f}")
            logger.info(f"  LR: {current_lr:.6f}")

            # Mostrar MAE por parâmetro a cada 10 epochs
            if (epoch + 1) % 10 == 0 and delta_columns:
                logger.info("\n  MAE por parâmetro:")
                for i, col in enumerate(delta_columns[:10]):  # Mostrar apenas top 10
                    param_name = col.replace('delta_', '')
                    logger.info(f"    {param_name}: {mae_per_param[i]:.4f}")

            # Early stopping
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), ckpt)
                logger.info("  Melhor modelo guardado!")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"\nEarly stopping após {epoch+1} epochs")
                    break

        # Carregar melhor modelo
        self.model.load_state_dict(torch.load(ckpt))

        # Análise final
        _, final_mae, final_preds, final_targets = self.validate(val_loader)

        logger.info("\nAnálise Final de Precisão:")
        logger.info("=" * 50)
        for i, col in enumerate(delta_columns):
            param_name = col.replace('delta_', '')
            mae = final_mae[i]

            # Desnormalizar para valores reais
            if scaler_deltas:
                mae_real = mae * scaler_deltas.scale_[i]
            else:
                mae_real = mae

            logger.info(f"{param_name:20s}: MAE = {mae_real:.3f}")

        return self.model
