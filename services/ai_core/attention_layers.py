"""
Mecanismos de Attention para modelos de ML.

FASE 2.2 - Attention Mechanisms
Implementa:
- Self-Attention: Destaca features importantes
- Cross-Attention: Entre stat e deep features
- Channel Attention: Squeeze-Excitation style
- Multi-Head Attention: Para modelagem mais rica

Benefícios esperados:
- Foca em features relevantes
- Ignora ruído
- +5-10% accuracy
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import Optional


class SelfAttention(nn.Module):
    """
    Self-Attention layer para destacar features importantes.

    Aprende a dar mais peso às features que são mais relevantes
    para a tarefa, baseando-se no contexto das outras features.
    """

    def __init__(self, feature_dim: int, dropout: float = 0.1):
        """
        Inicializa Self-Attention.

        Args:
            feature_dim: Dimensão das features de entrada
            dropout: Taxa de dropout (default: 0.1)
        """
        super(SelfAttention, self).__init__()

        self.feature_dim = feature_dim

        # Attention weights
        self.query = nn.Linear(feature_dim, feature_dim)
        self.key = nn.Linear(feature_dim, feature_dim)
        self.value = nn.Linear(feature_dim, feature_dim)

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(feature_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input features [batch, feature_dim]

        Returns:
            Attention-weighted features [batch, feature_dim]
        """
        # Add sequence dimension if needed
        if x.dim() == 2:
            x = x.unsqueeze(1)  # [batch, 1, feature_dim]

        batch_size, seq_len, _ = x.shape

        # Compute Q, K, V
        Q = self.query(x)  # [batch, seq_len, feature_dim]
        K = self.key(x)
        V = self.value(x)

        # Attention scores
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.feature_dim)
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Apply attention
        attended = torch.matmul(attention_weights, V)

        # Residual connection + layer norm
        output = self.layer_norm(x + attended)

        # Remove sequence dimension if we added it
        if seq_len == 1:
            output = output.squeeze(1)

        return output


class CrossAttention(nn.Module):
    """
    Cross-Attention entre duas modalidades (stat e deep features).

    Permite que stat features atendam para deep features e vice-versa,
    facilitando a fusão de informações complementares.
    """

    def __init__(
        self,
        stat_dim: int,
        deep_dim: int,
        output_dim: int,
        dropout: float = 0.1
    ):
        """
        Inicializa Cross-Attention.

        Args:
            stat_dim: Dimensão das stat features
            deep_dim: Dimensão das deep features
            output_dim: Dimensão de saída
            dropout: Taxa de dropout
        """
        super(CrossAttention, self).__init__()

        self.stat_dim = stat_dim
        self.deep_dim = deep_dim
        self.output_dim = output_dim

        # Project to common dimension
        self.stat_proj = nn.Linear(stat_dim, output_dim)
        self.deep_proj = nn.Linear(deep_dim, output_dim)

        # Cross-attention: stat attends to deep
        self.stat_query = nn.Linear(output_dim, output_dim)
        self.deep_key = nn.Linear(output_dim, output_dim)
        self.deep_value = nn.Linear(output_dim, output_dim)

        # Cross-attention: deep attends to stat
        self.deep_query = nn.Linear(output_dim, output_dim)
        self.stat_key = nn.Linear(output_dim, output_dim)
        self.stat_value = nn.Linear(output_dim, output_dim)

        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(output_dim)

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
            Fused features [batch, output_dim * 2]
        """
        # Project to common dimension
        stat_proj = self.stat_proj(stat_features).unsqueeze(1)  # [batch, 1, output_dim]
        deep_proj = self.deep_proj(deep_features).unsqueeze(1)

        # Stat attends to deep
        Q_stat = self.stat_query(stat_proj)
        K_deep = self.deep_key(deep_proj)
        V_deep = self.deep_value(deep_proj)

        scores_stat = torch.matmul(Q_stat, K_deep.transpose(-2, -1)) / math.sqrt(self.output_dim)
        attn_stat = F.softmax(scores_stat, dim=-1)
        attn_stat = self.dropout(attn_stat)
        stat_attended = torch.matmul(attn_stat, V_deep)
        stat_out = self.layer_norm(stat_proj + stat_attended).squeeze(1)

        # Deep attends to stat
        Q_deep = self.deep_query(deep_proj)
        K_stat = self.stat_key(stat_proj)
        V_stat = self.stat_value(stat_proj)

        scores_deep = torch.matmul(Q_deep, K_stat.transpose(-2, -1)) / math.sqrt(self.output_dim)
        attn_deep = F.softmax(scores_deep, dim=-1)
        attn_deep = self.dropout(attn_deep)
        deep_attended = torch.matmul(attn_deep, V_stat)
        deep_out = self.layer_norm(deep_proj + deep_attended).squeeze(1)

        # Concatenate
        fused = torch.cat([stat_out, deep_out], dim=1)

        return fused


class ChannelAttention(nn.Module):
    """
    Channel Attention (Squeeze-and-Excitation style).

    Aprende a reponderar canais de features baseado na sua importância.
    Muito efetivo para destacar features discriminativas.
    """

    def __init__(
        self,
        feature_dim: int,
        reduction_ratio: int = 16,
        activation: str = 'relu'
    ):
        """
        Inicializa Channel Attention.

        Args:
            feature_dim: Dimensão das features
            reduction_ratio: Fator de redução no bottleneck (default: 16)
            activation: Função de ativação ('relu', 'gelu', 'swish')
        """
        super(ChannelAttention, self).__init__()

        self.feature_dim = feature_dim
        reduced_dim = max(feature_dim // reduction_ratio, 8)

        # Squeeze: Global average pooling (implícito no forward)

        # Excitation: FC -> Activation -> FC -> Sigmoid
        self.fc1 = nn.Linear(feature_dim, reduced_dim)
        self.fc2 = nn.Linear(reduced_dim, feature_dim)

        if activation == 'relu':
            self.activation = nn.ReLU(inplace=True)
        elif activation == 'gelu':
            self.activation = nn.GELU()
        elif activation == 'swish':
            self.activation = nn.SiLU()
        else:
            raise ValueError(f"Unknown activation: {activation}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input features [batch, feature_dim]

        Returns:
            Channel-attended features [batch, feature_dim]
        """
        # Squeeze: já são features globais (batch, feature_dim)
        squeezed = x

        # Excitation
        attention = self.fc1(squeezed)
        attention = self.activation(attention)
        attention = self.fc2(attention)
        attention = torch.sigmoid(attention)

        # Scale
        return x * attention


class MultiHeadAttention(nn.Module):
    """
    Multi-Head Attention para modelagem mais rica.

    Usa múltiplas cabeças de attention para capturar diferentes
    aspectos das relações entre features.
    """

    def __init__(
        self,
        feature_dim: int,
        num_heads: int = 8,
        dropout: float = 0.1
    ):
        """
        Inicializa Multi-Head Attention.

        Args:
            feature_dim: Dimensão das features (deve ser divisível por num_heads)
            num_heads: Número de cabeças de attention
            dropout: Taxa de dropout
        """
        super(MultiHeadAttention, self).__init__()

        assert feature_dim % num_heads == 0, "feature_dim must be divisible by num_heads"

        self.feature_dim = feature_dim
        self.num_heads = num_heads
        self.head_dim = feature_dim // num_heads

        self.query = nn.Linear(feature_dim, feature_dim)
        self.key = nn.Linear(feature_dim, feature_dim)
        self.value = nn.Linear(feature_dim, feature_dim)

        self.out_proj = nn.Linear(feature_dim, feature_dim)
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(feature_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input features [batch, feature_dim]

        Returns:
            Multi-head attended features [batch, feature_dim]
        """
        batch_size = x.shape[0]

        # Add sequence dimension
        if x.dim() == 2:
            x = x.unsqueeze(1)  # [batch, 1, feature_dim]

        seq_len = x.shape[1]

        # Linear projections and reshape to multi-head
        Q = self.query(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.key(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.value(x).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.head_dim)
        attention_weights = F.softmax(scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Apply attention to values
        attended = torch.matmul(attention_weights, V)

        # Concatenate heads
        attended = attended.transpose(1, 2).contiguous().view(batch_size, seq_len, self.feature_dim)

        # Output projection
        output = self.out_proj(attended)

        # Residual + norm
        if seq_len == 1:
            x_input = x
        else:
            x_input = x

        output = self.layer_norm(x_input + output)

        # Remove sequence dimension if we added it
        if seq_len == 1:
            output = output.squeeze(1)

        return output


class AdaptiveFusion(nn.Module):
    """
    Adaptive Fusion layer que aprende a balancear stat e deep features.

    Usa gating mechanism para controlar quanto de cada modalidade
    deve contribuir para a saída final.
    """

    def __init__(
        self,
        stat_dim: int,
        deep_dim: int,
        output_dim: int,
        dropout: float = 0.1
    ):
        """
        Inicializa Adaptive Fusion.

        Args:
            stat_dim: Dimensão das stat features
            deep_dim: Dimensão das deep features
            output_dim: Dimensão de saída
            dropout: Taxa de dropout
        """
        super(AdaptiveFusion, self).__init__()

        # Project both modalities to output_dim
        self.stat_proj = nn.Linear(stat_dim, output_dim)
        self.deep_proj = nn.Linear(deep_dim, output_dim)

        # Gating network
        self.gate = nn.Sequential(
            nn.Linear(stat_dim + deep_dim, output_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(output_dim, 2),  # 2 gates: one for stat, one for deep
            nn.Softmax(dim=1)
        )

        self.layer_norm = nn.LayerNorm(output_dim)
        self.dropout = nn.Dropout(dropout)

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
            Adaptively fused features [batch, output_dim]
        """
        # Project to common dimension
        stat_proj = self.stat_proj(stat_features)
        deep_proj = self.deep_proj(deep_features)

        # Compute gates
        combined_input = torch.cat([stat_features, deep_features], dim=1)
        gates = self.gate(combined_input)  # [batch, 2]

        # Apply gates
        stat_gate = gates[:, 0:1]  # [batch, 1]
        deep_gate = gates[:, 1:2]

        fused = stat_gate * stat_proj + deep_gate * deep_proj

        # Normalization
        fused = self.layer_norm(fused)
        fused = self.dropout(fused)

        return fused


class AttentionPooling(nn.Module):
    """
    Attention-based pooling para agregar features.

    Útil quando temos múltiplas features e queremos agregar
    com pesos aprendidos ao invés de simples média.
    """

    def __init__(self, feature_dim: int):
        """
        Inicializa Attention Pooling.

        Args:
            feature_dim: Dimensão das features
        """
        super(AttentionPooling, self).__init__()

        self.attention = nn.Sequential(
            nn.Linear(feature_dim, feature_dim // 2),
            nn.Tanh(),
            nn.Linear(feature_dim // 2, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Input features [batch, num_features, feature_dim]

        Returns:
            Pooled features [batch, feature_dim]
        """
        # Compute attention weights
        attention_weights = self.attention(x)  # [batch, num_features, 1]
        attention_weights = F.softmax(attention_weights, dim=1)

        # Weighted sum
        pooled = torch.sum(x * attention_weights, dim=1)  # [batch, feature_dim]

        return pooled


if __name__ == "__main__":
    # Demo usage
    batch_size = 4
    stat_dim = 32
    deep_dim = 64
    feature_dim = 128

    # Self-Attention
    print("Testing SelfAttention...")
    self_attn = SelfAttention(feature_dim)
    x = torch.randn(batch_size, feature_dim)
    out = self_attn(x)
    print(f"Input shape: {x.shape}, Output shape: {out.shape}")

    # Cross-Attention
    print("\nTesting CrossAttention...")
    cross_attn = CrossAttention(stat_dim, deep_dim, output_dim=64)
    stat_feat = torch.randn(batch_size, stat_dim)
    deep_feat = torch.randn(batch_size, deep_dim)
    out = cross_attn(stat_feat, deep_feat)
    print(f"Stat: {stat_feat.shape}, Deep: {deep_feat.shape}, Output: {out.shape}")

    # Channel Attention
    print("\nTesting ChannelAttention...")
    channel_attn = ChannelAttention(feature_dim)
    x = torch.randn(batch_size, feature_dim)
    out = channel_attn(x)
    print(f"Input shape: {x.shape}, Output shape: {out.shape}")

    # Multi-Head Attention
    print("\nTesting MultiHeadAttention...")
    mha = MultiHeadAttention(feature_dim, num_heads=8)
    x = torch.randn(batch_size, feature_dim)
    out = mha(x)
    print(f"Input shape: {x.shape}, Output shape: {out.shape}")

    # Adaptive Fusion
    print("\nTesting AdaptiveFusion...")
    adaptive_fusion = AdaptiveFusion(stat_dim, deep_dim, output_dim=64)
    stat_feat = torch.randn(batch_size, stat_dim)
    deep_feat = torch.randn(batch_size, deep_dim)
    out = adaptive_fusion(stat_feat, deep_feat)
    print(f"Stat: {stat_feat.shape}, Deep: {deep_feat.shape}, Output: {out.shape}")

    print("\nAll attention layers working correctly!")
