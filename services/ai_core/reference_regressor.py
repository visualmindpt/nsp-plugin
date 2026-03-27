"""
ReferenceRegressor — rede neuronal para o modo Reference Match.

Input:
  - stat_features  [B, stat_dim]   — features estatísticas da foto a editar
  - deep_features  [B, deep_dim]   — deep features (ResNet18) da foto a editar
  - style_vector   [B, style_dim]  — fingerprint visual da foto de referência

Output:
  - params [B, num_params] — parâmetros Lightroom absolutos (não deltas)

Diferença face ao OptimizedRefinementRegressor:
  - Recebe style_vector em vez de preset_id embedding
  - Prediz valores absolutos, não deltas sobre um centro de cluster
  - Sem dependência de preset_centers — é completamente independente do
    modo Style Learner
"""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import Optional


class ReferenceRegressor(nn.Module):
    """
    Regressor que prediz parâmetros Lightroom absolutos a partir de
    (features da foto, style fingerprint da referência).
    """

    def __init__(
        self,
        stat_features_dim: int,
        deep_features_dim: int,
        style_fingerprint_dim: int = 128,
        num_params: int = 60,
        width_factor: float = 1.0,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        w = max(1, int(width_factor))

        # Ramo das features estatísticas
        self.stat_branch = nn.Sequential(
            nn.Linear(stat_features_dim, 64 * w),
            nn.LayerNorm(64 * w),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64 * w, 64 * w),
            nn.GELU(),
        )

        # Ramo das deep features
        self.deep_branch = nn.Sequential(
            nn.Linear(deep_features_dim, 128 * w),
            nn.LayerNorm(128 * w),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128 * w, 64 * w),
            nn.GELU(),
        )

        # Ramo do style fingerprint
        self.style_branch = nn.Sequential(
            nn.Linear(style_fingerprint_dim, 128 * w),
            nn.LayerNorm(128 * w),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128 * w, 64 * w),
            nn.GELU(),
        )

        fusion_dim = 64 * w * 3  # concatenação dos 3 ramos

        # Mecanismo de atenção sobre os 3 ramos
        self.attention = nn.Sequential(
            nn.Linear(fusion_dim, 3),
            nn.Softmax(dim=-1),
        )

        # MLP de fusão
        self.fusion = nn.Sequential(
            nn.Linear(fusion_dim, 128 * w),
            nn.LayerNorm(128 * w),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128 * w, 64 * w),
            nn.GELU(),
            nn.Dropout(dropout / 2),
        )

        # Cabeça de output com skip connection
        self.head = nn.Linear(64 * w, num_params)
        self.skip = nn.Linear(fusion_dim, num_params)

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(
        self,
        stat_features: torch.Tensor,
        deep_features: torch.Tensor,
        style_vector: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            stat_features:  [B, stat_dim]
            deep_features:  [B, deep_dim]
            style_vector:   [B, style_dim]

        Returns:
            params: [B, num_params] — valores absolutos dos parâmetros Lightroom
        """
        s = self.stat_branch(stat_features)   # [B, 64w]
        d = self.deep_branch(deep_features)   # [B, 64w]
        y = self.style_branch(style_vector)   # [B, 64w]

        fused = torch.cat([s, d, y], dim=-1)  # [B, 192w]

        # Atenção: peso por ramo
        attn_weights = self.attention(fused)  # [B, 3]
        s_w = attn_weights[:, 0:1]
        d_w = attn_weights[:, 1:2]
        y_w = attn_weights[:, 2:3]
        fused_attended = torch.cat([s * s_w, d * d_w, y * y_w], dim=-1)

        # Fusão
        out = self.fusion(fused_attended)  # [B, 64w]

        # Output com skip connection
        params = self.head(out) + self.skip(fused_attended)
        return params
