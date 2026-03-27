"""
Data augmentation para datasets pequenos de features de imagens.

Técnicas implementadas:
- Ruído gaussiano em features estatísticas
- Feature dropout para deep features
- Mixup de deltas para criar exemplos sintéticos
"""

import torch
import numpy as np
from torch.utils.data import Dataset
from typing import Optional, Tuple


def augment_stat_features(features: torch.Tensor, noise_std: float = 0.05) -> torch.Tensor:
    """
    Adiciona ruído gaussiano às features estatísticas.

    O ruído simula pequenas variações naturais nas estatísticas da imagem,
    ajudando o modelo a generalizar melhor.

    Args:
        features: Features estatísticas [batch, feature_dim]
        noise_std: Desvio padrão do ruído gaussiano (padrão: 0.05)

    Returns:
        Features aumentadas com ruído gaussiano
    """
    if features.shape[0] == 0:
        return features

    noise = torch.randn_like(features) * noise_std
    augmented = features + noise

    return augmented


def augment_deep_features(features: torch.Tensor, dropout_prob: float = 0.1) -> torch.Tensor:
    """
    Aplica feature dropout nas deep features.

    Aleatoriamente zera algumas features para forçar o modelo a não
    depender excessivamente de features específicas.

    Args:
        features: Deep features [batch, feature_dim]
        dropout_prob: Probabilidade de zerar cada feature (padrão: 0.1)

    Returns:
        Features com dropout aplicado
    """
    if features.shape[0] == 0:
        return features

    # Criar máscara de dropout
    mask = torch.bernoulli(torch.ones_like(features) * (1 - dropout_prob))

    # Escalar para manter a magnitude esperada
    augmented = features * mask / (1 - dropout_prob)

    return augmented


def mixup_deltas(deltas1: torch.Tensor, deltas2: torch.Tensor,
                 alpha: float = 0.3) -> torch.Tensor:
    """
    Aplica mixup entre dois conjuntos de deltas.

    Cria exemplos sintéticos interpolando entre pares de exemplos.
    Isso aumenta a diversidade do dataset e ajuda na regularização.

    Args:
        deltas1: Primeiro conjunto de deltas [batch, num_params]
        deltas2: Segundo conjunto de deltas [batch, num_params]
        alpha: Parâmetro da distribuição Beta (padrão: 0.3)

    Returns:
        Deltas interpolados
    """
    if deltas1.shape[0] == 0 or deltas2.shape[0] == 0:
        return deltas1

    # Sample lambda da distribuição Beta
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1.0

    # Interpolar
    mixed_deltas = lam * deltas1 + (1 - lam) * deltas2

    return mixed_deltas


class DataAugmentationDataset(Dataset):
    """
    Dataset wrapper que aplica data augmentation on-the-fly.

    Envolve um dataset existente e aplica augmentation durante o treino.
    Suporta augmentation de features estatísticas, deep features e deltas.
    """

    def __init__(self,
                 base_dataset: Dataset,
                 augment_stat: bool = True,
                 augment_deep: bool = True,
                 augment_deltas: bool = False,
                 stat_noise_std: float = 0.05,
                 deep_dropout_prob: float = 0.1,
                 mixup_alpha: float = 0.3):
        """
        Inicializa o dataset com augmentation.

        Args:
            base_dataset: Dataset original (LightroomDataset)
            augment_stat: Se True, aplica ruído em features estatísticas
            augment_deep: Se True, aplica dropout em deep features
            augment_deltas: Se True, aplica mixup nos deltas (apenas para regressor)
            stat_noise_std: Desvio padrão do ruído para stat features
            deep_dropout_prob: Probabilidade de dropout para deep features
            mixup_alpha: Parâmetro alpha para mixup
        """
        self.base_dataset = base_dataset
        self.augment_stat = augment_stat
        self.augment_deep = augment_deep
        self.augment_deltas = augment_deltas
        self.stat_noise_std = stat_noise_std
        self.deep_dropout_prob = deep_dropout_prob
        self.mixup_alpha = mixup_alpha

    def __len__(self) -> int:
        return len(self.base_dataset)

    def __getitem__(self, idx: int) -> dict:
        """
        Obtém um exemplo com augmentation aplicado.

        Args:
            idx: Índice do exemplo

        Returns:
            Dicionário com features aumentadas e labels originais
        """
        sample = self.base_dataset[idx]

        # Copiar para não modificar o original
        augmented_sample = {}

        # Augment stat features
        if self.augment_stat:
            stat_features = sample['stat_features'].unsqueeze(0)  # Add batch dim
            stat_features = augment_stat_features(stat_features, self.stat_noise_std)
            augmented_sample['stat_features'] = stat_features.squeeze(0)  # Remove batch dim
        else:
            augmented_sample['stat_features'] = sample['stat_features']

        # Augment deep features
        if self.augment_deep:
            deep_features = sample['deep_features'].unsqueeze(0)  # Add batch dim
            deep_features = augment_deep_features(deep_features, self.deep_dropout_prob)
            augmented_sample['deep_features'] = deep_features.squeeze(0)  # Remove batch dim
        else:
            augmented_sample['deep_features'] = sample['deep_features']

        # Labels não são aumentados
        augmented_sample['label'] = sample['label']

        # Deltas (se existirem)
        if 'deltas' in sample:
            if self.augment_deltas and len(self.base_dataset) > 1:
                # Escolher um índice aleatório diferente para mixup
                mix_idx = np.random.randint(0, len(self.base_dataset))
                while mix_idx == idx and len(self.base_dataset) > 1:
                    mix_idx = np.random.randint(0, len(self.base_dataset))

                mix_sample = self.base_dataset[mix_idx]
                deltas1 = sample['deltas'].unsqueeze(0)
                deltas2 = mix_sample['deltas'].unsqueeze(0)
                mixed_deltas = mixup_deltas(deltas1, deltas2, self.mixup_alpha)
                augmented_sample['deltas'] = mixed_deltas.squeeze(0)
            else:
                augmented_sample['deltas'] = sample['deltas']

        return augmented_sample


class BatchMixupCollator:
    """
    Collator que aplica mixup a nível de batch.

    Mais eficiente que aplicar mixup por amostra.
    Útil para treino do regressor.
    """

    def __init__(self, mixup_alpha: float = 0.3, mixup_prob: float = 0.5):
        """
        Inicializa o collator.

        Args:
            mixup_alpha: Parâmetro alpha da distribuição Beta
            mixup_prob: Probabilidade de aplicar mixup em cada batch
        """
        self.mixup_alpha = mixup_alpha
        self.mixup_prob = mixup_prob

    def __call__(self, batch: list) -> dict:
        """
        Coloca samples em batch e aplica mixup se necessário.

        Args:
            batch: Lista de samples do dataset

        Returns:
            Batch com mixup aplicado (se aplicável)
        """
        # Stack samples normalmente
        stat_features = torch.stack([s['stat_features'] for s in batch])
        deep_features = torch.stack([s['deep_features'] for s in batch])
        labels = torch.stack([s['label'] for s in batch])

        result = {
            'stat_features': stat_features,
            'deep_features': deep_features,
            'label': labels
        }

        # Se tiver deltas, aplicar mixup com probabilidade
        if 'deltas' in batch[0]:
            deltas = torch.stack([s['deltas'] for s in batch])

            if np.random.random() < self.mixup_prob:
                # Shuffle para criar pares aleatórios
                indices = torch.randperm(len(batch))
                deltas_shuffled = deltas[indices]

                # Aplicar mixup
                deltas = mixup_deltas(deltas, deltas_shuffled, self.mixup_alpha)

            result['deltas'] = deltas

        return result
