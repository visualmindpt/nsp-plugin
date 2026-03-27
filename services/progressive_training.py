# -*- coding: utf-8 -*-
"""
Progressive Training (Curriculum Learning)
Treina modelo começando com exemplos fáceis e progredindo para difíceis

Data: 16 Novembro 2025
"""

import torch
import numpy as np
from typing import List, Tuple, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class ProgressiveTrainer:
    """
    Implementa Curriculum Learning / Progressive Training

    Conceito: Começar com exemplos "fáceis" e gradualmente introduzir exemplos "difíceis"

    Benefícios:
    - Convergência mais rápida (20-40%)
    - Melhor generalização
    - Menos overfitting
    - Maior estabilidade no treino
    """

    def __init__(
        self,
        difficulty_fn: Optional[Callable] = None,
        num_stages: int = 3,
        stage_epochs: List[int] = None
    ):
        """
        Args:
            difficulty_fn: Função que calcula dificuldade de cada amostra (0=fácil, 1=difícil)
                          Se None, usa estratégia baseada em loss
            num_stages: Número de estágios progressivos
            stage_epochs: Epochs por estágio (se None, divide igualmente)
        """
        self.difficulty_fn = difficulty_fn
        self.num_stages = num_stages
        self.stage_epochs = stage_epochs
        self.current_stage = 0

        logger.info(f"🎓 Progressive Training inicializado com {num_stages} estágios")

    def get_curriculum_schedule(self, total_epochs: int) -> List[Tuple[int, int, float]]:
        """
        Gera schedule de curriculum learning

        Args:
            total_epochs: Total de épocas de treino

        Returns:
            Lista de (start_epoch, end_epoch, difficulty_threshold)
        """
        if self.stage_epochs:
            epochs_per_stage = self.stage_epochs
        else:
            epochs_per_stage = [total_epochs // self.num_stages] * self.num_stages
            # Ajustar último estágio para cobrir epochs restantes
            epochs_per_stage[-1] += total_epochs - sum(epochs_per_stage)

        schedule = []
        current_epoch = 0

        for stage in range(self.num_stages):
            start_epoch = current_epoch
            end_epoch = current_epoch + epochs_per_stage[stage]

            # Threshold de dificuldade aumenta com cada estágio
            difficulty_threshold = (stage + 1) / self.num_stages

            schedule.append((start_epoch, end_epoch, difficulty_threshold))
            current_epoch = end_epoch

            logger.info(f"   Estágio {stage + 1}: Épocas {start_epoch}-{end_epoch}, "
                       f"Dificuldade máxima: {difficulty_threshold:.2f}")

        return schedule

    def filter_by_difficulty(
        self,
        dataset: torch.utils.data.Dataset,
        difficulty_scores: np.ndarray,
        threshold: float
    ) -> torch.utils.data.Subset:
        """
        Filtra dataset por dificuldade

        Args:
            dataset: Dataset original
            difficulty_scores: Score de dificuldade para cada amostra (0-1)
            threshold: Incluir apenas amostras com dificuldade <= threshold

        Returns:
            Subset do dataset
        """
        # Índices de amostras que atendem ao threshold
        indices = np.where(difficulty_scores <= threshold)[0].tolist()

        logger.info(f"   Usando {len(indices)}/{len(dataset)} amostras (threshold={threshold:.2f})")

        return torch.utils.data.Subset(dataset, indices)

    def compute_difficulty_from_losses(
        self,
        model: torch.nn.Module,
        dataloader: torch.utils.data.DataLoader,
        criterion: torch.nn.Module,
        device: str = "cpu"
    ) -> np.ndarray:
        """
        Calcula dificuldade de cada amostra baseado na loss

        Estratégia: Amostras com loss maior = mais difíceis

        Args:
            model: Modelo treinado
            dataloader: DataLoader
            criterion: Função de loss
            device: Device

        Returns:
            Array de difficulty scores (0-1) para cada amostra
        """
        model.eval()
        losses = []

        with torch.no_grad():
            for batch in dataloader:
                if isinstance(batch, dict):
                    if 'clip_features' in batch:
                        inputs = batch['clip_features'].to(device)
                        outputs = model(inputs)
                    elif 'images' in batch:
                        inputs = batch['images'].to(device)
                        outputs = model(inputs)
                    elif 'stat_features' in batch and 'deep_features' in batch:
                        stat_inputs = batch['stat_features'].to(device)
                        deep_inputs = batch['deep_features'].to(device)
                        outputs = model(stat_inputs, deep_inputs)
                    else:
                        raise KeyError("Batch dictionary missing expected feature keys for progressive training.")

                    if 'label' in batch:
                        labels = batch['label'].to(device)
                    elif 'labels' in batch:
                        labels = batch['labels'].to(device)
                    elif 'targets' in batch:
                        labels = batch['targets'].to(device)
                    else:
                        raise KeyError("Batch dictionary missing labels/targets for progressive training.")
                else:
                    inputs, labels = batch
                    inputs = inputs.to(device)
                    labels = labels.to(device)
                    outputs = model(inputs)

                # Calcular loss por amostra (sem redução)
                if isinstance(criterion, torch.nn.CrossEntropyLoss):
                    loss_fn = torch.nn.CrossEntropyLoss(reduction='none')
                elif isinstance(criterion, torch.nn.MSELoss):
                    loss_fn = torch.nn.MSELoss(reduction='none')
                else:
                    # Fallback: usar reduction='mean' e duplicar
                    batch_loss = criterion(outputs, labels).item()
                    losses.extend([batch_loss] * len(inputs))
                    continue

                batch_losses = loss_fn(outputs, labels)

                # Se loss tem múltiplas dimensões (ex: MSE com múltiplos outputs), fazer média
                if batch_losses.dim() > 1:
                    batch_losses = batch_losses.mean(dim=tuple(range(1, batch_losses.dim())))

                losses.extend(batch_losses.cpu().numpy().tolist())

        losses = np.array(losses)

        # Normalizar para 0-1 (min-max scaling)
        if losses.max() > losses.min():
            difficulty_scores = (losses - losses.min()) / (losses.max() - losses.min())
        else:
            difficulty_scores = np.zeros_like(losses)

        logger.info(f"📊 Difficulty scores: min={difficulty_scores.min():.3f}, "
                   f"max={difficulty_scores.max():.3f}, mean={difficulty_scores.mean():.3f}")

        return difficulty_scores


class ProgressiveDataLoader:
    """
    DataLoader que suporta Progressive Training
    """

    def __init__(
        self,
        dataset: torch.utils.data.Dataset,
        difficulty_scores: np.ndarray,
        batch_size: int = 32,
        shuffle: bool = True
    ):
        """
        Args:
            dataset: Dataset completo
            difficulty_scores: Difficulty score para cada amostra
            batch_size: Tamanho do batch
            shuffle: Shuffle dos dados
        """
        self.dataset = dataset
        self.difficulty_scores = difficulty_scores
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.current_threshold = 1.0  # Começar com todas as amostras

    def set_difficulty_threshold(self, threshold: float):
        """Define threshold de dificuldade atual"""
        self.current_threshold = threshold

    def get_dataloader(self) -> torch.utils.data.DataLoader:
        """
        Retorna DataLoader filtrado pelo threshold atual

        Returns:
            DataLoader com subset do dataset
        """
        # Filtrar índices
        indices = np.where(self.difficulty_scores <= self.current_threshold)[0].tolist()

        # Criar subset
        subset = torch.utils.data.Subset(self.dataset, indices)

        # Criar dataloader
        return torch.utils.data.DataLoader(
            subset,
            batch_size=self.batch_size,
            shuffle=self.shuffle,
            drop_last=True
        )


def progressive_training_example():
    """Exemplo de uso de Progressive Training"""
    print("=" * 80)
    print("PROGRESSIVE TRAINING - Exemplo de Uso")
    print("=" * 80)
    print()

    print("# 1. Calcular difficulty scores iniciais")
    print("-" * 80)
    print("""
from services.progressive_training import ProgressiveTrainer

trainer = ProgressiveTrainer(num_stages=3)

# Treinar modelo inicial rápido para calcular difficulty
initial_model = train_initial_model(train_loader, epochs=5)

# Calcular difficulty baseado em loss
difficulty_scores = trainer.compute_difficulty_from_losses(
    initial_model,
    train_loader,
    criterion,
    device='cuda'
)
    """)

    print()
    print("# 2. Criar schedule de curriculum")
    print("-" * 80)
    print("""
schedule = trainer.get_curriculum_schedule(total_epochs=30)

# Output:
#   Estágio 1: Épocas 0-10, Dificuldade máxima: 0.33
#   Estágio 2: Épocas 10-20, Dificuldade máxima: 0.67
#   Estágio 3: Épocas 20-30, Dificuldade máxima: 1.00
    """)

    print()
    print("# 3. Treinar progressivamente")
    print("-" * 80)
    print("""
for start_epoch, end_epoch, difficulty_threshold in schedule:
    print(f"Estágio: Épocas {start_epoch}-{end_epoch}, Threshold={difficulty_threshold}")

    # Filtrar dataset por dificuldade
    filtered_dataset = trainer.filter_by_difficulty(
        train_dataset,
        difficulty_scores,
        threshold=difficulty_threshold
    )

    # Criar DataLoader
    stage_loader = DataLoader(filtered_dataset, batch_size=32, shuffle=True)

    # Treinar neste estágio
    for epoch in range(start_epoch, end_epoch):
        train_epoch(model, stage_loader, criterion, optimizer)
    """)

    print()
    print("# 4. Usar ProgressiveDataLoader (mais simples)")
    print("-" * 80)
    print("""
from services.progressive_training import ProgressiveDataLoader

progressive_loader = ProgressiveDataLoader(
    train_dataset,
    difficulty_scores,
    batch_size=32
)

for epoch in range(30):
    # Atualizar threshold baseado na época
    progress = epoch / 30
    threshold = 0.3 + (0.7 * progress)  # 0.3 → 1.0

    progressive_loader.set_difficulty_threshold(threshold)
    dataloader = progressive_loader.get_dataloader()

    # Treinar
    train_epoch(model, dataloader, criterion, optimizer)
    """)

    print()
    print("=" * 80)


if __name__ == "__main__":
    progressive_training_example()
