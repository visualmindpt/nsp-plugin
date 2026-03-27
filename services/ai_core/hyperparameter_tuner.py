"""
Hyperparameter Tuning Automático com Optuna.

FASE 3.3 - Automated Hyperparameter Optimization
Implementa:
- Bayesian optimization: Mais eficiente que grid/random search
- Multi-objective optimization: Balanceia accuracy e speed
- Pruning: Para early stopping de trials ruins
- Distributed optimization: Suporte para paralelização

Parâmetros otimizados:
- Learning rate, batch size, dropout rates
- Layer sizes, weight decay
- Scheduler parameters
- Augmentation parameters
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import optuna
from optuna.trial import Trial
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import numpy as np
from typing import Dict, Optional, Callable, Tuple, List
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class HyperparameterTuner:
    """
    Tuner automático de hyperparâmetros usando Optuna.

    Usa Bayesian optimization para encontrar os melhores
    hyperparâmetros de forma eficiente.
    """

    def __init__(
        self,
        model_class: type,
        train_dataset,
        val_dataset,
        device: str = 'cuda',
        study_name: str = "hyperparameter_optimization",
        storage: Optional[str] = None,
        direction: str = 'maximize'
    ):
        """
        Inicializa hyperparameter tuner.

        Args:
            model_class: Classe do modelo a otimizar
            train_dataset: Dataset de treino
            val_dataset: Dataset de validação
            device: Device ('cuda', 'cpu')
            study_name: Nome do estudo Optuna
            storage: Database para persistir estudos (opcional)
            direction: 'maximize' para accuracy, 'minimize' para loss
        """
        self.model_class = model_class
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.device = device
        self.study_name = study_name
        self.direction = direction

        # Create Optuna study
        sampler = TPESampler(seed=42)
        pruner = MedianPruner(n_startup_trials=5, n_warmup_steps=10)

        self.study = optuna.create_study(
            study_name=study_name,
            direction=direction,
            sampler=sampler,
            pruner=pruner,
            storage=storage,
            load_if_exists=True
        )

        logger.info(f"Initialized Hyperparameter Tuner: {study_name}")
        logger.info(f"Direction: {direction}")

    def define_search_space(self, trial: Trial) -> Dict:
        """
        Define espaço de busca de hyperparâmetros.

        Args:
            trial: Optuna trial

        Returns:
            Dicionário com hyperparâmetros
        """
        # Learning rate (log scale)
        lr = trial.suggest_float('lr', 1e-5, 1e-2, log=True)

        # Batch size (categorical)
        batch_size = trial.suggest_categorical('batch_size', [8, 16, 32, 64])

        # Optimizer
        optimizer_name = trial.suggest_categorical('optimizer', ['adam', 'adamw', 'sgd'])

        # Weight decay
        weight_decay = trial.suggest_float('weight_decay', 1e-6, 1e-2, log=True)

        # Dropout rates
        dropout_stat = trial.suggest_float('dropout_stat', 0.1, 0.6)
        dropout_deep = trial.suggest_float('dropout_deep', 0.1, 0.6)
        dropout_fusion = trial.suggest_float('dropout_fusion', 0.1, 0.6)

        # Layer sizes
        stat_hidden = trial.suggest_categorical('stat_hidden', [32, 64, 128])
        deep_hidden = trial.suggest_categorical('deep_hidden', [64, 128, 256])
        fusion_hidden = trial.suggest_categorical('fusion_hidden', [32, 64, 128])

        # Scheduler
        scheduler_type = trial.suggest_categorical('scheduler', ['cosine', 'step', 'onecycle'])

        # Augmentation
        stat_noise_std = trial.suggest_float('stat_noise_std', 0.01, 0.15)
        deep_dropout_prob = trial.suggest_float('deep_dropout_prob', 0.05, 0.25)

        params = {
            'lr': lr,
            'batch_size': batch_size,
            'optimizer': optimizer_name,
            'weight_decay': weight_decay,
            'dropout_stat': dropout_stat,
            'dropout_deep': dropout_deep,
            'dropout_fusion': dropout_fusion,
            'stat_hidden': stat_hidden,
            'deep_hidden': deep_hidden,
            'fusion_hidden': fusion_hidden,
            'scheduler': scheduler_type,
            'stat_noise_std': stat_noise_std,
            'deep_dropout_prob': deep_dropout_prob
        }

        return params

    def objective(
        self,
        trial: Trial,
        num_epochs: int = 50,
        early_stopping_patience: int = 10
    ) -> float:
        """
        Função objetivo para Optuna.

        Args:
            trial: Optuna trial
            num_epochs: Número de epochs
            early_stopping_patience: Paciência para early stopping

        Returns:
            Métrica de validação
        """
        # Get hyperparameters
        params = self.define_search_space(trial)

        # Create model with suggested hyperparameters
        # Note: This is a simplified example. Adapt to your model architecture.
        model_kwargs = {
            'stat_features_dim': 30,  # Adjust based on your data
            'deep_features_dim': 512,  # Adjust based on your data
            'num_presets': 10,  # Adjust based on your data
            'dropout': params['dropout_fusion']
        }

        model = self.model_class(**model_kwargs).to(self.device)

        # Create DataLoaders
        train_loader = DataLoader(
            self.train_dataset,
            batch_size=params['batch_size'],
            shuffle=True,
            num_workers=0
        )

        val_loader = DataLoader(
            self.val_dataset,
            batch_size=params['batch_size'],
            shuffle=False,
            num_workers=0
        )

        # Setup optimizer
        if params['optimizer'] == 'adam':
            optimizer = optim.Adam(
                model.parameters(),
                lr=params['lr'],
                weight_decay=params['weight_decay']
            )
        elif params['optimizer'] == 'adamw':
            optimizer = optim.AdamW(
                model.parameters(),
                lr=params['lr'],
                weight_decay=params['weight_decay']
            )
        else:  # sgd
            optimizer = optim.SGD(
                model.parameters(),
                lr=params['lr'],
                weight_decay=params['weight_decay'],
                momentum=0.9
            )

        # Setup scheduler
        if params['scheduler'] == 'cosine':
            scheduler = optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=num_epochs
            )
        elif params['scheduler'] == 'step':
            scheduler = optim.lr_scheduler.StepLR(
                optimizer,
                step_size=num_epochs // 3,
                gamma=0.1
            )
        else:  # onecycle
            scheduler = optim.lr_scheduler.OneCycleLR(
                optimizer,
                max_lr=params['lr'] * 10,
                epochs=num_epochs,
                steps_per_epoch=len(train_loader)
            )

        # Loss function
        criterion = nn.CrossEntropyLoss()

        # Training loop
        best_val_acc = 0
        patience_counter = 0

        for epoch in range(num_epochs):
            # Train
            model.train()
            train_loss = 0.0

            for batch in train_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                labels = batch['label'].to(self.device)

                optimizer.zero_grad()
                outputs = model(stat_feat, deep_feat)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

                if params['scheduler'] == 'onecycle':
                    scheduler.step()

            # Validation
            model.eval()
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                for batch in val_loader:
                    stat_feat = batch['stat_features'].to(self.device)
                    deep_feat = batch['deep_features'].to(self.device)
                    labels = batch['label'].to(self.device)

                    outputs = model(stat_feat, deep_feat)
                    _, predicted = outputs.max(1)
                    val_total += labels.size(0)
                    val_correct += predicted.eq(labels).sum().item()

            val_acc = val_correct / val_total

            # Report intermediate value
            trial.report(val_acc, epoch)

            # Pruning
            if trial.should_prune():
                raise optuna.TrialPruned()

            # Early stopping
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break

            # Step scheduler
            if params['scheduler'] != 'onecycle':
                scheduler.step()

        return best_val_acc

    def run_optimization(
        self,
        n_trials: int = 100,
        timeout: Optional[int] = None,
        n_jobs: int = 1
    ) -> Dict:
        """
        Executa otimização de hyperparâmetros.

        Args:
            n_trials: Número de trials
            timeout: Timeout em segundos (opcional)
            n_jobs: Número de jobs paralelos

        Returns:
            Melhores hyperparâmetros
        """
        logger.info(f"Starting optimization: {n_trials} trials")

        self.study.optimize(
            self.objective,
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            show_progress_bar=True
        )

        logger.info("Optimization completed!")

        # Get best trial
        best_trial = self.study.best_trial
        best_params = best_trial.params
        best_value = best_trial.value

        logger.info(f"Best value: {best_value:.4f}")
        logger.info(f"Best params: {best_params}")

        return {
            'best_params': best_params,
            'best_value': best_value,
            'n_trials': len(self.study.trials)
        }

    def get_best_params(self) -> Dict:
        """
        Retorna melhores hyperparâmetros encontrados.

        Returns:
            Dicionário com melhores parâmetros
        """
        if len(self.study.trials) == 0:
            raise ValueError("No trials completed yet")

        return self.study.best_params

    def save_study(self, output_path: str):
        """
        Salva estudo para análise posterior.

        Args:
            output_path: Caminho do arquivo
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save best params
        best_params = self.study.best_params
        best_value = self.study.best_value

        study_data = {
            'study_name': self.study_name,
            'n_trials': len(self.study.trials),
            'best_value': best_value,
            'best_params': best_params,
            'all_trials': [
                {
                    'number': t.number,
                    'value': t.value,
                    'params': t.params,
                    'state': str(t.state)
                }
                for t in self.study.trials
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(study_data, f, indent=2)

        logger.info(f"Saved study to {output_path}")

    def plot_optimization_history(self, output_path: Optional[str] = None):
        """
        Plota histórico de otimização.

        Args:
            output_path: Caminho para salvar plot (opcional)
        """
        try:
            from optuna.visualization import plot_optimization_history, plot_param_importances

            # Optimization history
            fig1 = plot_optimization_history(self.study)
            if output_path:
                fig1.write_html(str(Path(output_path).parent / "optimization_history.html"))

            # Parameter importances
            fig2 = plot_param_importances(self.study)
            if output_path:
                fig2.write_html(str(Path(output_path).parent / "param_importances.html"))

            logger.info("Generated optimization plots")

        except ImportError:
            logger.warning("plotly not installed. Skipping visualization.")


class MultiObjectiveTuner(HyperparameterTuner):
    """
    Tuner multi-objetivo: Otimiza accuracy E velocidade.

    Encontra parâmetros que balanceiam qualidade e performance.
    """

    def __init__(self, *args, **kwargs):
        """Inicializa multi-objective tuner."""
        # Override direction for multi-objective
        kwargs['direction'] = None  # Will be set in create_study

        super().__init__(*args, **kwargs)

        # Recreate study for multi-objective
        sampler = TPESampler(seed=42)
        pruner = MedianPruner(n_startup_trials=5, n_warmup_steps=10)

        self.study = optuna.create_study(
            study_name=self.study_name,
            directions=['maximize', 'minimize'],  # Maximize accuracy, minimize time
            sampler=sampler,
            pruner=pruner,
            storage=kwargs.get('storage'),
            load_if_exists=True
        )

        logger.info("Initialized Multi-Objective Tuner")

    def objective(
        self,
        trial: Trial,
        num_epochs: int = 50,
        early_stopping_patience: int = 10
    ) -> Tuple[float, float]:
        """
        Multi-objective objective function.

        Returns:
            (accuracy, inference_time)
        """
        import time

        # Get accuracy from parent objective
        accuracy = super().objective(trial, num_epochs, early_stopping_patience)

        # Measure inference time
        params = self.define_search_space(trial)

        model_kwargs = {
            'stat_features_dim': 30,
            'deep_features_dim': 512,
            'num_presets': 10,
            'dropout': params['dropout_fusion']
        }

        model = self.model_class(**model_kwargs).to(self.device)
        model.eval()

        # Benchmark
        stat_feat = torch.randn(1, 30).to(self.device)
        deep_feat = torch.randn(1, 512).to(self.device)

        num_iterations = 100
        start = time.time()

        with torch.no_grad():
            for _ in range(num_iterations):
                _ = model(stat_feat, deep_feat)

        inference_time = (time.time() - start) / num_iterations * 1000  # ms

        return accuracy, inference_time


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    # This is a placeholder. In real usage, you'd provide actual datasets.
    print("Hyperparameter Tuner ready!")
    print("Usage:")
    print("  tuner = HyperparameterTuner(model_class, train_dataset, val_dataset)")
    print("  results = tuner.run_optimization(n_trials=100)")
    print("  best_params = tuner.get_best_params()")
