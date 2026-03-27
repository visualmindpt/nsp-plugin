"""
services/culling.py

Camada de inferência para o módulo Smart Culling. Reutiliza a arquitetura
treinada em `train/train_culling.py` e expõe utilitários para pontuar uma
ou várias imagens.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image, UnidentifiedImageError

try:
    import rawpy
except ImportError:  # pragma: no cover
    rawpy = None

APP_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = APP_ROOT / "models" / "culling_model.pth"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _load_image(path: str, max_side: int = 512) -> Image.Image:
    try:
        img = Image.open(path)
    except FileNotFoundError:
        raise
    except (UnidentifiedImageError, OSError):
        if rawpy is None:
            raise
        with rawpy.imread(path) as raw:
            rgb = raw.postprocess()
        img = Image.fromarray(rgb)

    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.BILINEAR)
    return img.convert("RGB")


def _default_transform() -> T.Compose:
    return T.Compose(
        [
            T.Resize(256),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )


def _build_model(num_classes: int = 3) -> nn.Module:
    model = models.resnet34(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Linear(num_ftrs, 256),
        nn.ReLU(),
        nn.Dropout(0.4),
        nn.Linear(256, num_classes),
    )
    return model


@dataclass
class CullingResult:
    image_path: str
    keep_probability: float
    probabilities: List[float]
    predicted_label: int
    raw_score: float


class CullingEngine:
    def __init__(self, model_path: Optional[Path] = None, device: Optional[str] = None) -> None:
        self.model_path = Path(model_path or MODEL_PATH)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = self._load_model()
        self.transform = _default_transform()

    def _load_model(self) -> nn.Module:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Modelo de culling não encontrado em {self.model_path}. Treina-o com train/train_culling.py."
            )
        model = _build_model()
        state = torch.load(self.model_path, map_location=self.device)
        model.load_state_dict(state)
        model.to(self.device)
        model.eval()
        logging.info("Modelo de culling carregado de %s", self.model_path)
        return model

    @torch.inference_mode()
    def score_image(self, image_path: str) -> CullingResult:
        img = _load_image(image_path)
        tensor = self.transform(img).unsqueeze(0).to(self.device)
        logits = self.model(tensor)
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        keep_probability = float(probs[1]) if probs.size >= 2 else float(probs.max())
        predicted_label = int(np.argmax(probs))
        return CullingResult(
            image_path=image_path,
            keep_probability=keep_probability,
            probabilities=probs.tolist(),
            predicted_label=predicted_label,
            raw_score=float(logits.cpu().numpy()[0][predicted_label]),
        )

    def score_batch(self, image_paths: Iterable[str]) -> List[CullingResult]:
        results: List[CullingResult] = []
        for path in image_paths:
            try:
                results.append(self.score_image(path))
            except FileNotFoundError:
                logging.warning("Imagem não encontrada durante o culling: %s", path)
            except Exception as exc:  # pragma: no cover
                logging.error("Falha ao pontuar %s: %s", path, exc)
        return results


class DINOv2CullingModel(nn.Module):
    """
    Modelo de culling usando DINOv2 features
    (Mesma arquitetura usada no treino com train_culling_dinov2.py)
    """

    def __init__(self, dinov2_dim: int = 384):
        super().__init__()

        # Regression head
        self.head = nn.Sequential(
            nn.Linear(dinov2_dim, 512),
            nn.LayerNorm(512),
            nn.ReLU(),
            nn.Dropout(0.3),

            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.1),

            nn.Linear(128, 1),
            nn.Sigmoid()
        )

    def forward(self, features):
        return self.head(features)


class CullingPredictor:
    """
    Predictor de qualidade de fotos usando DINOv2 transfer learning

    Usa features pré-treinadas do DINOv2 (Meta AI) para avaliar
    qualidade técnica e estética de fotos.

    Output: Score 0-1 onde:
    - 0.9-1.0: Excelente (⭐⭐⭐)
    - 0.75-0.89: Muito Boa (⭐⭐)
    - 0.60-0.74: Boa (⭐)
    - 0.40-0.59: Razoável
    - 0.0-0.39: Fraca

    Usage:
        predictor = CullingPredictor(model_path="models/dinov2_culling_model.pth")
        score = predictor.predict_quality(image_path, exif_data)
        # score: 0-1 (multiplicar por 100 para escala 0-100)
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        device: str = "cpu",
        dinov2_model: str = "dinov2_vits14"
    ):
        """
        Inicializa o CullingPredictor

        Args:
            model_path: Caminho para modelo treinado (.pth)
            device: "cpu", "cuda", ou "mps"
            dinov2_model: Nome do modelo DINOv2 usado no treino
        """
        self.device = torch.device(device)
        self.model_path = Path(model_path) if model_path else APP_ROOT / "models" / "dinov2_culling_model.pth"

        # Feature dimensions
        # Mapa de dims para variantes (fallback para base dinov2)
        self.dinov2_dims = {
            'dinov2': 768,
            'dinov2_vits14': 384,
            'dinov2_vitb14': 768,
            'dinov2_vitl14': 1024,
            'dinov2_vitg14': 1536
        }

        self.dinov2_model_name = dinov2_model
        self.dinov2_dim = self.dinov2_dims.get(dinov2_model, 768)

        # Inicializar DINOv2 extractor
        try:
            from services.ai_core.modern_feature_extractor import ModernFeatureExtractor

            logging.info(f"Inicializando DINOv2 extractor ({dinov2_model})...")
            self.feature_extractor = ModernFeatureExtractor(
                model_name="dinov2",
                device=str(device)
            )

            # Se o extractor reporta feature_dim, alinhar dimensão
            if hasattr(self.feature_extractor, "feature_dim"):
                self.dinov2_dim = getattr(self.feature_extractor, "feature_dim", self.dinov2_dim)

            # Freeze feature extractor
            for param in self.feature_extractor.model.parameters():
                param.requires_grad = False

        except ImportError as e:
            logging.error(f"Erro ao importar ModernFeatureExtractor: {e}")
            logging.warning("DINOv2 não disponível. Usando fallback EXIF.")
            self.feature_extractor = None

        # Criar modelo
        self.model = DINOv2CullingModel(dinov2_dim=self.dinov2_dim).to(self.device)
        self.model.eval()

        # Carregar pesos se disponível
        if self.model_path.exists():
            self._load_model()
        else:
            logging.warning(f"Modelo não encontrado em {self.model_path}")
            logging.warning("Usando modelo não treinado (scores baseados em EXIF)")
            logging.info("💡 Treina o modelo: python train/train_culling_dinov2.py")

    def _load_model(self):
        """Carrega pesos do modelo treinado"""
        try:
            checkpoint = torch.load(self.model_path, map_location=self.device)

            # Verificar dimensões
            saved_dim = checkpoint.get('dinov2_dim', self.dinov2_dim)
            if saved_dim != self.dinov2_dim:
                logging.warning(
                    f"Dimensão do modelo salvo ({saved_dim}) != dimensão atual ({self.dinov2_dim}). "
                    f"Recriando modelo..."
                )
                self.dinov2_dim = saved_dim
                self.model = DINOv2CullingModel(dinov2_dim=saved_dim).to(self.device)

            # Carregar state dict
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()

            # Info
            best_val_pearson = checkpoint.get('best_val_pearson', 0)
            best_val_mae = checkpoint.get('best_val_mae', 0)
            epoch = checkpoint.get('epoch', 0)

            logging.info(f"✅ Modelo DINOv2 culling carregado de {self.model_path}")
            logging.info(f"   Época: {epoch}, Pearson: {best_val_pearson:.3f}, MAE: {best_val_mae:.2f}")

        except Exception as e:
            logging.error(f"Erro ao carregar modelo: {e}")
            logging.warning("Usando modelo não treinado")

    def predict_quality(self, image_path: str, exif: Optional[dict] = None) -> float:
        """
        Prediz qualidade de uma foto

        Args:
            image_path: Caminho para imagem
            exif: Metadados EXIF (opcional, usado como fallback)

        Returns:
            score: 0-1 (normalizado)
        """
        # Se não tem feature extractor, usar fallback EXIF
        if self.feature_extractor is None:
            return self._fallback_exif_score(exif or {})

        try:
            # Extrair features DINOv2
            with torch.no_grad():
                features = self.feature_extractor.extract_features(str(image_path))

                # Garantir que features estão no device correto
                if not isinstance(features, torch.Tensor):
                    features = torch.FloatTensor(features)

                features = features.to(self.device)

                # Predição
                score = self.model(features.unsqueeze(0))  # (1, 1)
                score = score.item()  # float 0-1

            return score

        except Exception as e:
            logging.error(f"Erro ao prever qualidade de {image_path}: {e}")

            # Fallback: usar EXIF
            if exif:
                return self._fallback_exif_score(exif)
            else:
                return 0.5  # Score neutro

    def _fallback_exif_score(self, exif: dict) -> float:
        """
        Score simplificado baseado em EXIF quando modelo falha

        Args:
            exif: Metadados EXIF

        Returns:
            score: 0-1
        """
        score = 0.5  # Base score

        # ISO (menor é melhor)
        iso = exif.get("iso", 0)
        if iso > 0:
            if iso <= 400:
                score += 0.2
            elif iso <= 1600:
                score += 0.1
            elif iso >= 6400:
                score -= 0.2

        # Abertura (faixa ótima)
        aperture = exif.get("aperture", 0)
        if aperture > 0:
            if 1.4 <= aperture <= 8.0:
                score += 0.1

        # Shutter speed (evitar muito lento)
        shutter = exif.get("shutterspeed", exif.get("shutter_speed", 0))
        if shutter > 0:
            if shutter >= 1 / 60:  # Mais rápido que 1/60s
                score += 0.1
            elif shutter < 1 / 30:  # Mais lento que 1/30s (risco de blur)
                score -= 0.1

        # Normalizar para 0-1
        score = max(0.0, min(1.0, score))

        return score


__all__ = ["CullingEngine", "CullingResult", "CullingPredictor", "DINOv2CullingModel"]
