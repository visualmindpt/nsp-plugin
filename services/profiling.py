"""
services/profiling.py

Camada de inferência para o módulo Auto-Profiling. Consome os artefactos
produzidos em train/profiling/train_profiles.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

APP_ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = APP_ROOT / "models" / "profiles"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _latest_artifact() -> Path:
    if not PROFILES_DIR.exists():
        raise FileNotFoundError("Nenhum artefacto de perfis encontrado (corre train/profiling/train_profiles.py).")
    artifacts = sorted(PROFILES_DIR.glob("profiles_*.joblib"))
    if not artifacts:
        raise FileNotFoundError("Pasta models/profiles está vazia.")
    return artifacts[-1]


@dataclass
class ProfilePrediction:
    label: str
    confidence: float
    distance: float
    artifact_path: Path


class StyleProfileEngine:
    def __init__(self, artifact_path: Optional[Path] = None) -> None:
        self.artifact_path = artifact_path or _latest_artifact()
        payload = joblib.load(self.artifact_path)
        self.scaler = payload["scaler"]
        self.model = payload["model"]
        self.record_ids = payload.get("record_ids", [])
        logging.info("Perfil carregado a partir de %s", self.artifact_path)

    def assign(self, feature_vector: np.ndarray) -> ProfilePrediction:
        if feature_vector.ndim == 1:
            feature_vector = feature_vector.reshape(1, -1)
        scaled = self.scaler.transform(feature_vector)
        label_idx = int(self.model.predict(scaled)[0])
        distances = self.model.transform(scaled)[0]
        distance = float(distances[label_idx])
        confidence = float(1.0 / (1.0 + distance))
        return ProfilePrediction(
            label=f"profile_{label_idx}",
            confidence=confidence,
            distance=distance,
            artifact_path=self.artifact_path,
        )


__all__ = ["StyleProfileEngine", "ProfilePrediction"]
