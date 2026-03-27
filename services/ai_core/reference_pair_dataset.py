"""
ReferencePairDataset — Dataset PyTorch para o treino do modo Reference Match.

Cada amostra é um triplo:
  - features estatísticas da foto a editar  (stat_dim,)
  - deep features da foto a editar          (deep_dim,)
  - style fingerprint da foto de referência (style_dim,)  ← novo
  - parâmetros Lightroom alvo (valores absolutos)         (num_params,)

Os pares são construídos pelo script train/train_reference_model.py antes de
instanciar este dataset: para cada foto P no catálogo, cria-se uma amostra por
cada outra foto R da mesma sessão (mesmo dia de captura).
"""

from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset


class ReferencePairDataset(Dataset):
    """
    Dataset de pares (foto_nova, referência) para treinar o ReferenceRegressor.

    Args:
        photo_stat_features:  [N, stat_dim]  — features estatísticas da foto a editar
        photo_deep_features:  [N, deep_dim]  — deep features da foto a editar
        reference_fingerprints: [N, style_dim] — fingerprint do JPEG editado de referência
        target_params:        [N, num_params] — parâmetros Lightroom absolutos (ground truth)
    """

    def __init__(
        self,
        photo_stat_features: np.ndarray,
        photo_deep_features: np.ndarray,
        reference_fingerprints: np.ndarray,
        target_params: np.ndarray,
    ) -> None:
        assert len(photo_stat_features) == len(photo_deep_features) == \
               len(reference_fingerprints) == len(target_params), (
            "Todos os arrays devem ter o mesmo número de amostras."
        )
        self.stat = torch.tensor(photo_stat_features, dtype=torch.float32)
        self.deep = torch.tensor(photo_deep_features, dtype=torch.float32)
        self.style = torch.tensor(reference_fingerprints, dtype=torch.float32)
        self.params = torch.tensor(target_params, dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.stat)

    def __getitem__(self, idx: int) -> dict:
        return {
            'stat_features': self.stat[idx],
            'deep_features': self.deep[idx],
            'style_fingerprint': self.style[idx],
            'target_params': self.params[idx],
        }
