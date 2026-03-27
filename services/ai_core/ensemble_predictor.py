"""
Ensemble de Modelos para melhor accuracy e robustez.

FASE 3.1 - Ensemble Methods
Implementa:
- Bagging: Treina múltiplos modelos com bootstrap sampling
- Boosting: Treino sequencial focando em erros
- Stacking: Meta-learner combina predições
- Voting: Soft/hard voting com pesos opcionais

Benefícios esperados:
- +10-15% accuracy sobre modelo único
- Mais robusto a outliers
- Reduz variance
- Melhor calibração de probabilidades
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Optional, Dict, Literal, Tuple
import logging
from pathlib import Path
from tqdm import tqdm

logger = logging.getLogger(__name__)

VotingStrategy = Literal["soft", "hard", "weighted"]


class EnsemblePredictor(nn.Module):
    """
    Ensemble de múltiplos modelos.

    Combina predições de vários modelos para obter
    resultados mais robustos e precisos.
    """

    def __init__(
        self,
        models: List[nn.Module],
        weights: Optional[List[float]] = None,
        voting: VotingStrategy = "soft"
    ):
        """
        Inicializa ensemble predictor.

        Args:
            models: Lista de modelos treinados
            weights: Pesos para cada modelo (opcional, default: uniforme)
            voting: Estratégia de voting ('soft', 'hard', 'weighted')
        """
        super(EnsemblePredictor, self).__init__()

        if len(models) == 0:
            raise ValueError("Need at least one model for ensemble")

        self.models = nn.ModuleList(models)
        self.num_models = len(models)
        self.voting = voting

        # Setup weights
        if weights is None:
            self.weights = torch.ones(self.num_models) / self.num_models
        else:
            if len(weights) != self.num_models:
                raise ValueError("Number of weights must match number of models")
            weights_tensor = torch.tensor(weights, dtype=torch.float32)
            self.weights = weights_tensor / weights_tensor.sum()

        logger.info(f"Initialized ensemble with {self.num_models} models")
        logger.info(f"Voting strategy: {voting}")
        logger.info(f"Weights: {self.weights.tolist()}")

    def forward(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor,
        preset_id: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass do ensemble.

        Args:
            stat_features: Stat features [batch, stat_dim]
            deep_features: Deep features [batch, deep_dim]
            preset_id: Preset ID (para regressores) [batch]

        Returns:
            Predição do ensemble [batch, output_dim]
        """
        predictions = []

        # Get predictions from each model
        for model in self.models:
            model.eval()
            with torch.no_grad():
                if preset_id is not None:
                    # Regressor
                    pred = model(stat_features, deep_features, preset_id)
                else:
                    # Classifier
                    pred = model(stat_features, deep_features)

                predictions.append(pred)

        # Combine predictions
        if self.voting == "soft":
            # Soft voting: average probabilities
            ensemble_pred = self._soft_voting(predictions)

        elif self.voting == "hard":
            # Hard voting: majority vote
            ensemble_pred = self._hard_voting(predictions)

        elif self.voting == "weighted":
            # Weighted voting: weighted average
            ensemble_pred = self._weighted_voting(predictions)

        else:
            raise ValueError(f"Unknown voting strategy: {self.voting}")

        return ensemble_pred

    def _soft_voting(self, predictions: List[torch.Tensor]) -> torch.Tensor:
        """
        Soft voting: Média das probabilidades.

        Args:
            predictions: Lista de predições [num_models x [batch, output_dim]]

        Returns:
            Predição combinada [batch, output_dim]
        """
        # Stack predictions
        stacked = torch.stack(predictions, dim=0)  # [num_models, batch, output_dim]

        # Average
        ensemble_pred = stacked.mean(dim=0)

        return ensemble_pred

    def _hard_voting(self, predictions: List[torch.Tensor]) -> torch.Tensor:
        """
        Hard voting: Voto maioritário.

        Args:
            predictions: Lista de predições logits

        Returns:
            Predição combinada (logits)
        """
        # Get class predictions
        class_preds = []
        for pred in predictions:
            class_pred = pred.argmax(dim=1)
            class_preds.append(class_pred)

        # Stack
        stacked = torch.stack(class_preds, dim=0)  # [num_models, batch]

        # Majority vote
        ensemble_classes = torch.mode(stacked, dim=0).values  # [batch]

        # Convert back to logits (one-hot style)
        num_classes = predictions[0].shape[1]
        ensemble_pred = F.one_hot(ensemble_classes, num_classes=num_classes).float()

        return ensemble_pred

    def _weighted_voting(self, predictions: List[torch.Tensor]) -> torch.Tensor:
        """
        Weighted voting: Média ponderada.

        Args:
            predictions: Lista de predições

        Returns:
            Predição combinada
        """
        # Stack predictions
        stacked = torch.stack(predictions, dim=0)  # [num_models, batch, output_dim]

        # Apply weights
        weights = self.weights.view(-1, 1, 1).to(stacked.device)
        weighted = stacked * weights

        # Sum
        ensemble_pred = weighted.sum(dim=0)

        return ensemble_pred

    def predict_with_uncertainty(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor,
        preset_id: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predição com estimativa de incerteza.

        Args:
            stat_features: Stat features
            deep_features: Deep features
            preset_id: Preset ID (opcional)

        Returns:
            (predição_média, desvio_padrão)
        """
        predictions = []

        for model in self.models:
            model.eval()
            with torch.no_grad():
                if preset_id is not None:
                    pred = model(stat_features, deep_features, preset_id)
                else:
                    pred = model(stat_features, deep_features)

                predictions.append(pred)

        # Stack
        stacked = torch.stack(predictions, dim=0)  # [num_models, batch, output_dim]

        # Mean and std
        mean = stacked.mean(dim=0)
        std = stacked.std(dim=0)

        return mean, std


class BaggingEnsemble:
    """
    Bagging Ensemble: Treina múltiplos modelos com bootstrap sampling.

    Reduz variance ao treinar modelos em diferentes subsets dos dados.
    """

    def __init__(
        self,
        model_class: type,
        model_kwargs: Dict,
        n_models: int = 5,
        bootstrap_ratio: float = 0.8
    ):
        """
        Inicializa Bagging Ensemble.

        Args:
            model_class: Classe do modelo
            model_kwargs: Kwargs para inicializar modelo
            n_models: Número de modelos no ensemble
            bootstrap_ratio: Fração dos dados para bootstrap (0-1)
        """
        self.model_class = model_class
        self.model_kwargs = model_kwargs
        self.n_models = n_models
        self.bootstrap_ratio = bootstrap_ratio

        self.models = []

        logger.info(f"Initialized Bagging Ensemble with {n_models} models")

    def train(
        self,
        train_dataset,
        trainer_fn: callable,
        device: str = 'cuda'
    ) -> List[nn.Module]:
        """
        Treina ensemble com bagging.

        Args:
            train_dataset: Dataset de treino
            trainer_fn: Função de treino (recebe model, dataset)
            device: Device

        Returns:
            Lista de modelos treinados
        """
        dataset_size = len(train_dataset)
        bootstrap_size = int(dataset_size * self.bootstrap_ratio)

        self.models = []

        for i in range(self.n_models):
            logger.info(f"\nTraining model {i+1}/{self.n_models}")

            # Create bootstrap sample
            indices = np.random.choice(dataset_size, size=bootstrap_size, replace=True)
            bootstrap_dataset = torch.utils.data.Subset(train_dataset, indices)

            # Initialize model
            model = self.model_class(**self.model_kwargs).to(device)

            # Train
            trained_model = trainer_fn(model, bootstrap_dataset)

            self.models.append(trained_model)

        logger.info(f"\nTrained {len(self.models)} models successfully")

        return self.models

    def get_ensemble(
        self,
        voting: VotingStrategy = "soft"
    ) -> EnsemblePredictor:
        """
        Retorna EnsemblePredictor com modelos treinados.

        Args:
            voting: Estratégia de voting

        Returns:
            EnsemblePredictor
        """
        if not self.models:
            raise ValueError("No models trained yet. Call train() first.")

        return EnsemblePredictor(self.models, voting=voting)


class StackingEnsemble:
    """
    Stacking Ensemble: Usa meta-learner para combinar predições.

    Treina um modelo secundário que aprende a combinar
    as predições dos modelos base de forma ótima.
    """

    def __init__(
        self,
        base_models: List[nn.Module],
        meta_learner: nn.Module
    ):
        """
        Inicializa Stacking Ensemble.

        Args:
            base_models: Lista de modelos base treinados
            meta_learner: Modelo que combina predições
        """
        self.base_models = nn.ModuleList(base_models)
        self.meta_learner = meta_learner
        self.num_base_models = len(base_models)

        logger.info(f"Initialized Stacking Ensemble with {self.num_base_models} base models")

    def get_base_predictions(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor,
        preset_id: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Obtém predições de todos os modelos base.

        Args:
            stat_features: Stat features
            deep_features: Deep features
            preset_id: Preset ID (opcional)

        Returns:
            Predições concatenadas [batch, num_models * output_dim]
        """
        base_preds = []

        for model in self.base_models:
            model.eval()
            with torch.no_grad():
                if preset_id is not None:
                    pred = model(stat_features, deep_features, preset_id)
                else:
                    pred = model(stat_features, deep_features)

                base_preds.append(pred)

        # Concatenate
        stacked_preds = torch.cat(base_preds, dim=1)

        return stacked_preds

    def train_meta_learner(
        self,
        train_loader,
        optimizer,
        criterion,
        num_epochs: int = 10,
        device: str = 'cuda'
    ):
        """
        Treina meta-learner.

        Args:
            train_loader: DataLoader de treino
            optimizer: Optimizer
            criterion: Loss function
            num_epochs: Número de epochs
            device: Device
        """
        self.meta_learner.to(device)
        self.meta_learner.train()

        for epoch in range(num_epochs):
            epoch_loss = 0.0
            num_batches = 0

            pbar = tqdm(train_loader, desc=f"Meta-learner epoch {epoch+1}/{num_epochs}")

            for batch in pbar:
                stat_feat = batch['stat_features'].to(device)
                deep_feat = batch['deep_features'].to(device)
                labels = batch['label'].to(device)

                preset_id = batch.get('preset_id', None)
                if preset_id is not None:
                    preset_id = preset_id.to(device)

                # Get base predictions
                base_preds = self.get_base_predictions(stat_feat, deep_feat, preset_id)

                # Meta-learner prediction
                meta_pred = self.meta_learner(base_preds)

                # Compute loss
                loss = criterion(meta_pred, labels)

                # Backward
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                num_batches += 1

                pbar.set_postfix({'loss': f'{loss.item():.4f}'})

            avg_loss = epoch_loss / num_batches
            logger.info(f"Meta-learner epoch {epoch+1}: Loss = {avg_loss:.4f}")

    def predict(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor,
        preset_id: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Predição final do stacking ensemble.

        Args:
            stat_features: Stat features
            deep_features: Deep features
            preset_id: Preset ID (opcional)

        Returns:
            Predição final
        """
        self.meta_learner.eval()

        with torch.no_grad():
            # Get base predictions
            base_preds = self.get_base_predictions(stat_features, deep_features, preset_id)

            # Meta-learner prediction
            final_pred = self.meta_learner(base_preds)

        return final_pred


def save_ensemble(
    ensemble: EnsemblePredictor,
    save_dir: str,
    ensemble_name: str = "ensemble"
):
    """
    Salva ensemble de modelos.

    Args:
        ensemble: EnsemblePredictor
        save_dir: Diretório de save
        ensemble_name: Nome do ensemble
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # Save each model
    for i, model in enumerate(ensemble.models):
        model_path = save_dir / f"{ensemble_name}_model_{i}.pth"
        torch.save(model.state_dict(), model_path)

    # Save ensemble config
    config = {
        'num_models': ensemble.num_models,
        'weights': ensemble.weights.tolist(),
        'voting': ensemble.voting
    }

    config_path = save_dir / f"{ensemble_name}_config.json"
    import json
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    logger.info(f"Saved ensemble to {save_dir}")


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    # Create dummy models
    class DummyModel(nn.Module):
        def __init__(self, input_dim=30+512, output_dim=10):
            super().__init__()
            self.fc = nn.Linear(input_dim, output_dim)

        def forward(self, stat_feat, deep_feat):
            combined = torch.cat([stat_feat, deep_feat], dim=1)
            return self.fc(combined)

    models = [DummyModel() for _ in range(5)]

    # Create ensemble
    ensemble = EnsemblePredictor(models, voting="soft")

    # Test prediction
    stat_feat = torch.randn(4, 30)
    deep_feat = torch.randn(4, 512)

    pred = ensemble(stat_feat, deep_feat)
    print(f"Ensemble prediction shape: {pred.shape}")

    # Test with uncertainty
    mean, std = ensemble.predict_with_uncertainty(stat_feat, deep_feat)
    print(f"Mean shape: {mean.shape}, Std shape: {std.shape}")

    print("Ensemble predictor ready!")
