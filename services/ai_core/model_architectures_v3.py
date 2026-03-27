"""
Arquiteturas V3 com Attention Mechanisms avançados.

FASE 2.3 - Modelos com Attention
Integra:
- Cross-Attention entre stat e deep features
- Multi-Head Attention para modelagem rica
- Adaptive Fusion para balanceamento inteligente
- Channel Attention para destacar features importantes

Benefícios esperados sobre V2:
- +5-10% accuracy adicional
- Melhor fusão de modalidades
- Mais robusto a ruído
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

from .attention_layers import (
    SelfAttention,
    CrossAttention,
    ChannelAttention,
    MultiHeadAttention,
    AdaptiveFusion
)


class AttentionPresetClassifier(nn.Module):
    """
    Classificador de presets com Cross-Attention avançado.

    Usa Cross-Attention para permitir que stat e deep features
    atendam uma para a outra, capturando interações complexas.

    Arquitetura:
    - Stat branch: stat_dim -> 64 -> 32 (com channel attention)
    - Deep branch: deep_dim -> 128 -> 32 (com channel attention)
    - Cross-Attention: entre stat e deep
    - Fusion: attention_out -> 32 -> num_presets
    """

    def __init__(
        self,
        stat_features_dim: int,
        deep_features_dim: int,
        num_presets: int,
        dropout: float = 0.4
    ):
        """
        Inicializa o classificador com attention.

        Args:
            stat_features_dim: Dimensão das stat features
            deep_features_dim: Dimensão das deep features
            num_presets: Número de presets a classificar
            dropout: Taxa de dropout
        """
        super(AttentionPresetClassifier, self).__init__()

        # Stat branch com channel attention
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU()
        )
        self.stat_channel_attn = ChannelAttention(32, reduction_ratio=4)

        # Deep branch com channel attention
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 32),
            nn.BatchNorm1d(32),
            nn.ReLU()
        )
        self.deep_channel_attn = ChannelAttention(32, reduction_ratio=4)

        # Cross-Attention entre stat e deep
        self.cross_attention = CrossAttention(
            stat_dim=32,
            deep_dim=32,
            output_dim=32,
            dropout=dropout
        )

        # Fusion final (cross_attention retorna 64 dims: 32 + 32)
        self.fusion = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(dropout * 1.25),
            nn.Linear(32, num_presets)
        )

    def forward(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            stat_features: Statistical features [batch, stat_dim]
            deep_features: Deep features [batch, deep_dim]

        Returns:
            Logits para classificação [batch, num_presets]
        """
        # Process stat features
        stat_out = self.stat_branch(stat_features)
        stat_out = self.stat_channel_attn(stat_out)

        # Process deep features
        deep_out = self.deep_branch(deep_features)
        deep_out = self.deep_channel_attn(deep_out)

        # Cross-Attention
        fused = self.cross_attention(stat_out, deep_out)

        # Classification
        logits = self.fusion(fused)

        return logits


class AttentionRefinementRegressor(nn.Module):
    """
    Regressor de refinamento com Adaptive Fusion.

    Usa Adaptive Fusion para balancear inteligentemente
    stat features, deep features e preset embedding.

    Arquitetura:
    - Stat branch: stat_dim -> 64 -> 32
    - Deep branch: deep_dim -> 128 -> 32
    - Preset embedding: num_presets -> 16
    - Adaptive Fusion: aprende balanceamento ótimo
    - Multi-Head Attention: para modelagem rica
    - Output: fused -> 64 -> 32 -> num_params
    """

    def __init__(
        self,
        stat_features_dim: int,
        deep_features_dim: int,
        num_presets: int,
        num_params: int,
        dropout: float = 0.4
    ):
        """
        Inicializa o regressor com attention.

        Args:
            stat_features_dim: Dimensão das stat features
            deep_features_dim: Dimensão das deep features
            num_presets: Número de presets
            num_params: Número de parâmetros a prever
            dropout: Taxa de dropout
        """
        super(AttentionRefinementRegressor, self).__init__()

        # Preset embedding
        self.preset_embedding = nn.Embedding(num_presets, 16)

        # Stat branch
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU()
        )

        # Deep branch
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 32),
            nn.BatchNorm1d(32),
            nn.ReLU()
        )

        # Adaptive fusion entre stat e deep
        self.adaptive_fusion = AdaptiveFusion(
            stat_dim=32,
            deep_dim=32,
            output_dim=48,
            dropout=dropout
        )

        # Multi-head attention para modelagem rica
        # Input: fused(48) + preset_emb(16) = 64
        self.combine = nn.Linear(48 + 16, 64)
        self.mha = MultiHeadAttention(feature_dim=64, num_heads=8, dropout=dropout)

        # Output layers com skip connection
        self.output_fc1 = nn.Sequential(
            nn.Linear(64, 48),
            nn.BatchNorm1d(48),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        self.output_fc2 = nn.Linear(48, num_params)

        # Skip connection
        self.skip = nn.Linear(64, 48)

    def forward(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor,
        preset_id: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            stat_features: Statistical features [batch, stat_dim]
            deep_features: Deep features [batch, deep_dim]
            preset_id: ID do preset selecionado [batch]

        Returns:
            Deltas preditos [batch, num_params]
        """
        # Process branches
        stat_out = self.stat_branch(stat_features)
        deep_out = self.deep_branch(deep_features)

        # Adaptive fusion
        fused = self.adaptive_fusion(stat_out, deep_out)  # [batch, 48]

        # Add preset embedding
        preset_emb = self.preset_embedding(preset_id)  # [batch, 16]
        combined = torch.cat([fused, preset_emb], dim=1)  # [batch, 64]
        combined = self.combine(combined)

        # Multi-head attention
        attended = self.mha(combined)  # [batch, 64]

        # Skip connection
        skip = self.skip(attended)

        # Output with residual
        out = self.output_fc1(attended)
        out = out + skip
        deltas = self.output_fc2(out)

        return deltas


class MultiModalAttentionClassifier(nn.Module):
    """
    Classificador multi-modal com Self-Attention e Channel Attention.

    Modelo mais sofisticado que usa múltiplos mecanismos de attention
    para maximizar a extração de informação de ambas as modalidades.

    Melhor para datasets maiores (500+ fotos).
    """

    def __init__(
        self,
        stat_features_dim: int,
        deep_features_dim: int,
        num_presets: int,
        dropout: float = 0.4
    ):
        """
        Inicializa o classificador multi-modal.

        Args:
            stat_features_dim: Dimensão das stat features
            deep_features_dim: Dimensão das deep features
            num_presets: Número de presets
            dropout: Taxa de dropout
        """
        super(MultiModalAttentionClassifier, self).__init__()

        # Stat processing com self-attention
        self.stat_fc = nn.Sequential(
            nn.Linear(stat_features_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        self.stat_self_attn = SelfAttention(64, dropout=dropout)
        self.stat_channel_attn = ChannelAttention(64, reduction_ratio=8)

        # Deep processing com self-attention
        self.deep_fc = nn.Sequential(
            nn.Linear(deep_features_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        self.deep_self_attn = SelfAttention(128, dropout=dropout)
        self.deep_channel_attn = ChannelAttention(128, reduction_ratio=8)

        # Cross-modal attention
        self.cross_attn = CrossAttention(
            stat_dim=64,
            deep_dim=128,
            output_dim=64,
            dropout=dropout
        )

        # Final classification
        self.classifier = nn.Sequential(
            nn.Linear(128, 64),  # Cross-attn outputs 128 (64+64)
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout * 1.25),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, num_presets)
        )

    def forward(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            stat_features: Statistical features [batch, stat_dim]
            deep_features: Deep features [batch, deep_dim]

        Returns:
            Logits para classificação [batch, num_presets]
        """
        # Stat pathway
        stat = self.stat_fc(stat_features)
        stat = self.stat_self_attn(stat)
        stat = self.stat_channel_attn(stat)

        # Deep pathway
        deep = self.deep_fc(deep_features)
        deep = self.deep_self_attn(deep)
        deep = self.deep_channel_attn(deep)

        # Cross-modal fusion
        fused = self.cross_attn(stat, deep)

        # Classification
        logits = self.classifier(fused)

        return logits


def get_model_v3(
    model_type: str,
    stat_features_dim: int,
    deep_features_dim: int,
    num_presets: int,
    num_params: Optional[int] = None,
    dropout: float = 0.4
) -> nn.Module:
    """
    Factory function para criar modelos V3.

    Args:
        model_type: Tipo do modelo ("attention_classifier", "attention_regressor", "multimodal_classifier")
        stat_features_dim: Dimensão das stat features
        deep_features_dim: Dimensão das deep features
        num_presets: Número de presets
        num_params: Número de parâmetros (apenas para regressor)
        dropout: Taxa de dropout

    Returns:
        Modelo V3 inicializado
    """
    if model_type == "attention_classifier":
        return AttentionPresetClassifier(
            stat_features_dim=stat_features_dim,
            deep_features_dim=deep_features_dim,
            num_presets=num_presets,
            dropout=dropout
        )

    elif model_type == "attention_regressor":
        if num_params is None:
            raise ValueError("num_params required for regressor")

        return AttentionRefinementRegressor(
            stat_features_dim=stat_features_dim,
            deep_features_dim=deep_features_dim,
            num_presets=num_presets,
            num_params=num_params,
            dropout=dropout
        )

    elif model_type == "multimodal_classifier":
        return MultiModalAttentionClassifier(
            stat_features_dim=stat_features_dim,
            deep_features_dim=deep_features_dim,
            num_presets=num_presets,
            dropout=dropout
        )

    else:
        raise ValueError(f"Unknown model type: {model_type}")


def count_parameters(model: nn.Module) -> int:
    """Conta parâmetros treináveis."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def get_model_size_mb(model: nn.Module) -> float:
    """Calcula tamanho do modelo em MB."""
    param_size = sum(p.nelement() * p.element_size() for p in model.parameters())
    buffer_size = sum(b.nelement() * b.element_size() for b in model.buffers())
    return (param_size + buffer_size) / 1024 / 1024


if __name__ == "__main__":
    # Demo usage
    batch_size = 4
    stat_dim = 30
    deep_dim = 512
    num_presets = 10
    num_params = 15

    print("=" * 60)
    print("MODEL ARCHITECTURES V3 - ATTENTION MODELS")
    print("=" * 60)

    # Test AttentionPresetClassifier
    print("\n1. AttentionPresetClassifier")
    model = AttentionPresetClassifier(stat_dim, deep_dim, num_presets)
    stat_feat = torch.randn(batch_size, stat_dim)
    deep_feat = torch.randn(batch_size, deep_dim)
    output = model(stat_feat, deep_feat)
    print(f"   Output shape: {output.shape}")
    print(f"   Parameters: {count_parameters(model):,}")
    print(f"   Size: {get_model_size_mb(model):.2f} MB")

    # Test AttentionRefinementRegressor
    print("\n2. AttentionRefinementRegressor")
    model = AttentionRefinementRegressor(stat_dim, deep_dim, num_presets, num_params)
    preset_ids = torch.randint(0, num_presets, (batch_size,))
    output = model(stat_feat, deep_feat, preset_ids)
    print(f"   Output shape: {output.shape}")
    print(f"   Parameters: {count_parameters(model):,}")
    print(f"   Size: {get_model_size_mb(model):.2f} MB")

    # Test MultiModalAttentionClassifier
    print("\n3. MultiModalAttentionClassifier")
    model = MultiModalAttentionClassifier(stat_dim, deep_dim, num_presets)
    output = model(stat_feat, deep_feat)
    print(f"   Output shape: {output.shape}")
    print(f"   Parameters: {count_parameters(model):,}")
    print(f"   Size: {get_model_size_mb(model):.2f} MB")

    print("\n" + "=" * 60)
    print("All models working correctly!")
    print("=" * 60)
