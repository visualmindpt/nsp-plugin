"""
Arquiteturas de modelos otimizadas para dataset pequeno (260 fotos).

FASE 1 - Otimizações:
- Redução de parâmetros em ~50%
- Attention mechanism para focar em features relevantes
- BatchNorm para estabilizar treino
- Dropout mais agressivo (0.4-0.5) para combater overfitting
- Skip connections no regressor
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class AttentionLayer(nn.Module):
    """Camada de atenção para destacar features mais relevantes."""

    def __init__(self, feature_dim: int):
        super(AttentionLayer, self).__init__()
        self.attention = nn.Sequential(
            nn.Linear(feature_dim, feature_dim // 2),
            nn.Tanh(),
            nn.Linear(feature_dim // 2, feature_dim),
            nn.Softmax(dim=1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attention_weights = self.attention(x)
        return x * attention_weights


class OptimizedPresetClassifier(nn.Module):
    """
    Classificador de presets otimizado para datasets pequenos.

    Melhorias em relação ao modelo original:
    - Redução de parâmetros: Stat branch (128,64 -> 64,32), Deep branch (256,64 -> 128,32)
    - Attention mechanism na camada de fusão
    - BatchNorm para estabilizar treino
    - Dropout mais agressivo (0.4-0.5)

    Parâmetros reduzidos em ~50% comparado com PresetClassifier original.
    """

    def __init__(self, stat_features_dim: int, deep_features_dim: int, num_presets: int, width_factor: float = 1.0):
        super(OptimizedPresetClassifier, self).__init__()

        def s(v: int) -> int:
            return max(4, int(v * width_factor))

        # Branch para features estatísticas (reduzida: 128,64 -> 64,32)
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, s(64)),
            nn.BatchNorm1d(s(64)),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(s(64), s(32)),
            nn.BatchNorm1d(s(32)),
            nn.ReLU(),
            nn.Dropout(0.4)
        )

        # Branch para deep features (reduzida: 256,64 -> 128,32)
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, s(128)),
            nn.BatchNorm1d(s(128)),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(s(128), s(32)),
            nn.BatchNorm1d(s(32)),
            nn.ReLU(),
            nn.Dropout(0.4)
        )

        # Attention para destacar features importantes
        self.attention = AttentionLayer(s(64))

        # Fusão (64 -> 32 -> num_presets)
        self.fusion = nn.Sequential(
            nn.Linear(s(64), s(32)),
            nn.BatchNorm1d(s(32)),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(s(32), num_presets)
        )

    def forward(self, stat_features: torch.Tensor, deep_features: torch.Tensor) -> torch.Tensor:
        """
        Forward pass do classificador.

        Args:
            stat_features: Features estatísticas da imagem [batch, stat_dim]
            deep_features: Deep features da imagem [batch, deep_dim]

        Returns:
            Logits para classificação de presets [batch, num_presets]
        """
        stat_out = self.stat_branch(stat_features)
        deep_out = self.deep_branch(deep_features)

        # Concatenar e aplicar attention
        combined = torch.cat([stat_out, deep_out], dim=1)
        combined = self.attention(combined)

        # Classificação final
        output = self.fusion(combined)
        return output


class OptimizedRefinementRegressor(nn.Module):
    """
    Regressor de refinamento otimizado para datasets pequenos.

    Melhorias em relação ao modelo original:
    - Redução de parâmetros: Stat (128,64 -> 64,32), Deep (256,64 -> 128,32)
    - Preset embedding menor (32 -> 16)
    - Skip connections para melhor gradiente flow
    - BatchNorm em todas as camadas
    - Dropout mais agressivo (0.4-0.5)

    Parâmetros reduzidos em ~50% comparado com RefinementRegressor original.
    """

    def __init__(self, stat_features_dim: int, deep_features_dim: int,
                 num_presets: int, num_params: int, width_factor: float = 1.0):
        super(OptimizedRefinementRegressor, self).__init__()

        def s(v: int) -> int:
            return max(4, int(v * width_factor))

        # Embedding do preset reduzido (32 -> 16)
        self.preset_embedding = nn.Embedding(num_presets, s(16))

        # Stat branch reduzida (128,64 -> 64,32)
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, s(64)),
            nn.BatchNorm1d(s(64)),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(s(64), s(32)),
            nn.BatchNorm1d(s(32)),
            nn.ReLU(),
            nn.Dropout(0.4)
        )

        # Deep branch reduzida (256,64 -> 128,32)
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, s(128)),
            nn.BatchNorm1d(s(128)),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(s(128), s(32)),
            nn.BatchNorm1d(s(32)),
            nn.ReLU(),
            nn.Dropout(0.4)
        )

        # Fusão: stat + deep + preset_emb
        fusion_dim = s(32) + s(32) + s(16)
        self.fusion_1 = nn.Sequential(
            nn.Linear(fusion_dim, s(64)),
            nn.BatchNorm1d(s(64)),
            nn.ReLU(),
            nn.Dropout(0.5)
        )

        self.fusion_2 = nn.Sequential(
            nn.Linear(s(64), s(32)),
            nn.BatchNorm1d(s(32)),
            nn.ReLU(),
            nn.Dropout(0.4)
        )

        # Output layer
        self.output = nn.Linear(s(32), num_params)

        # Skip connection weights
        self.skip_connection = nn.Linear(fusion_dim, s(32))

    def forward(self, stat_features: torch.Tensor, deep_features: torch.Tensor,
                preset_id: torch.Tensor) -> torch.Tensor:
        """
        Forward pass do regressor.

        Args:
            stat_features: Features estatísticas da imagem [batch, stat_dim]
            deep_features: Deep features da imagem [batch, deep_dim]
            preset_id: ID do preset selecionado [batch]

        Returns:
            Deltas preditos para cada parâmetro [batch, num_params]
        """
        # Embedding do preset
        preset_emb = self.preset_embedding(preset_id)

        # Processar features
        stat_out = self.stat_branch(stat_features)
        deep_out = self.deep_branch(deep_features)

        # Concatenar tudo
        combined = torch.cat([stat_out, deep_out, preset_emb], dim=1)

        # Skip connection
        skip = self.skip_connection(combined)

        # Camadas de fusão com residual
        x = self.fusion_1(combined)
        x = self.fusion_2(x)

        # Adicionar skip connection
        x = x + skip

        # Predizer deltas
        deltas = self.output(x)

        return deltas


def count_parameters(model: nn.Module) -> int:
    """
    Conta o número de parâmetros treináveis no modelo.

    Args:
        model: Modelo PyTorch

    Returns:
        Número total de parâmetros treináveis
    """
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def get_model_size_mb(model: nn.Module) -> float:
    """
    Calcula o tamanho do modelo em MB.

    Args:
        model: Modelo PyTorch

    Returns:
        Tamanho do modelo em megabytes
    """
    param_size = 0
    for param in model.parameters():
        param_size += param.nelement() * param.element_size()

    buffer_size = 0
    for buffer in model.buffers():
        buffer_size += buffer.nelement() * buffer.element_size()

    size_mb = (param_size + buffer_size) / 1024 / 1024
    return size_mb
