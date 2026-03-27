"""
services/inference.py

Camada de inferência utilizada pelo plugin em produção. Carrega os modelos
LightGBM e NN, prepara as features com PCA + EXIF escalado e expõe métodos
para prever sliders a partir de um caminho de imagem e respetivos metadados.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional

# Reduzir verbosidade da biblioteca transformers (suprimir avisos sobre image processor)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

import joblib
import numpy as np
import onnxruntime as ort # New import
import torch # Added import
from PIL import Image, UnidentifiedImageError

# Suprimir avisos da biblioteca transformers sobre slow image processor
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

from sentence_transformers import SentenceTransformer

from slider_config import ALL_SLIDERS as ALL_SLIDER_CONFIGS # Import ALL_SLIDERS from slider_config
ALL_SLIDER_NAMES = [s["python_name"] for s in ALL_SLIDER_CONFIGS] # Extract names

try:
    import rawpy
except ImportError:  # pragma: no cover - optional
    rawpy = None

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


MODEL_NAME = "clip-ViT-B-32"
MODEL_LOCAL_DIR = APP_ROOT / "models" / MODEL_NAME
EXIF_KEYS = ["iso", "width", "height"]


def _load_image(path: str) -> Image.Image:
    try:
        img = Image.open(path)
        return img.convert("RGB")
    except FileNotFoundError:
        raise
    except (UnidentifiedImageError, OSError) as pil_error:
        if rawpy is None:
            raise pil_error
        with rawpy.imread(path) as raw:
            rgb = raw.postprocess()
        return Image.fromarray(rgb)


class NSPInferenceEngine:
    def __init__(
        self,
        model_dir: Optional[Path] = None,
    ) -> None:
        self.model_dir = model_dir or (APP_ROOT / "models")
        self.ann_dir = self.model_dir / "ann"

        # Autodetectar o melhor dispositivo disponível para CLIP
        self.clip_device = torch.device('mps' if torch.backends.mps.is_available() and torch.backends.mps.is_built() else 'cpu')
        logging.info(f"Motor de inferência CLIP a utilizar o dispositivo: {self.clip_device}")

        # Componentes partilhados
        self.clip_model = self._load_clip_model(device=self.clip_device)
        self.pca = joblib.load(self.model_dir / "pca_model.pkl")
        self.exif_scaler = joblib.load(self.model_dir / "exif_scaler.pkl")

        # Neural network (ONNX Runtime)
        self.ort_session: Optional[ort.InferenceSession] = None
        self.target_mean: Optional[np.ndarray] = None
        self.target_std: Optional[np.ndarray] = None
        onnx_path = self.ann_dir / "multi_output_nn.onnx"
        if onnx_path.exists():
            self.target_mean = np.load(self.ann_dir / "targets_mean.npy")
            self.target_std = np.load(self.ann_dir / "targets_std.npy")
            self.ort_session = ort.InferenceSession(str(onnx_path))
            logging.info(f"Modelo ONNX carregado com sucesso de {onnx_path}")
        else:
            logging.warning(f"Modelo ONNX não encontrado em {onnx_path}. A inferência da NN não estará disponível.")

    # --- Feature preparation -------------------------------------------------
    def encode_image(self, image_path: str) -> np.ndarray:
        image = _load_image(image_path)
        embedding = self.clip_model.encode([image], convert_to_numpy=True)[0]
        return embedding

    def _build_features(self, image_path: str, exif: Dict[str, float]) -> np.ndarray:
        embedding = self.encode_image(image_path)
        embedding_pca = self.pca.transform(embedding.reshape(1, -1))

        exif_values = np.array([[float(exif.get(k, 0.0)) for k in EXIF_KEYS]], dtype=np.float32)
        exif_scaled = self.exif_scaler.transform(exif_values)

        return np.concatenate([embedding_pca, exif_scaled], axis=1)

    @staticmethod
    def _candidate_clip_paths():
        if MODEL_LOCAL_DIR.exists():
            yield MODEL_LOCAL_DIR
            snapshots_root = MODEL_LOCAL_DIR / "models--sentence-transformers--clip-ViT-B-32" / "snapshots"
            if snapshots_root.exists():
                for snapshot in sorted((p for p in snapshots_root.iterdir() if p.is_dir()), reverse=True):
                    yield snapshot

    @classmethod
    def _load_clip_model(cls, device: torch.device) -> SentenceTransformer:
        """Tenta carregar o modelo CLIP do bundle local antes de recorrer à internet."""
        for candidate in cls._candidate_clip_paths():
            logging.info("A carregar SentenceTransformer a partir de %s", candidate)
            try:
                model = SentenceTransformer(
                    str(candidate),
                    cache_folder=str(candidate),
                    device=str(device),
                )
                model.to(device)  # Ensure model is on the correct device
                return model
            except Exception as exc:  # pragma: no cover
                logging.error("Falha ao carregar modelo local em %s (%s).", candidate, exc)
        logging.warning(
            "Modelo CLIP local não encontrado em %s (incluindo snapshots). A tentar transferência online (necessita de internet).",
            MODEL_LOCAL_DIR,
        )
        try:
            # A cache folder deve ser o diretório 'models', não o subdiretório específico do modelo
            models_dir = APP_ROOT / 'models'
            model = SentenceTransformer(
                MODEL_NAME,
                cache_folder=str(models_dir),
                device=str(device),
            )
            model.to(device)  # Ensure model is on the correct device
            return model
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível carregar o modelo {MODEL_NAME}. "
                "Garante que tens ligação à internet ou copia os ficheiros para models/clip-ViT-B-32."
            ) from exc

    # --- Predictions ---------------------------------------------------------


    def predict_nn(self, image_path: str, exif: Dict[str, float]) -> Dict[str, float]:
        if self.ort_session is None or self.target_mean is None or self.target_std is None:
            raise RuntimeError("Modelo ONNX da rede neural ou estatísticas em falta.")
        
        features_np = self._build_features(image_path, exif).astype(np.float32) # Ensure float32
        
        # Get input name from ONNX session
        input_name = self.ort_session.get_inputs()[0].name
        
        # Run ONNX inference
        ort_inputs = {input_name: features_np}
        ort_outputs = self.ort_session.run(None, ort_inputs) # None for all outputs
        
        predictions_normalized = ort_outputs[0]
        
        # Denormalize and map to sliders
        predictions = predictions_normalized * self.target_std + self.target_mean
        return {slider: float(predictions[0, idx]) for idx, slider in enumerate(ALL_SLIDER_NAMES)}


def load_engine() -> NSPInferenceEngine:
    """Helper para reutilização no servidor FastAPI."""
    return NSPInferenceEngine()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Teste rápido do motor de inferência.")
    parser.add_argument("--image", required=True, help="Caminho para a imagem.")
    parser.add_argument("--exif", required=True, help="JSON com ISO/width/height.")
    args = parser.parse_args()

    engine = NSPInferenceEngine()
    exif_payload = json.loads(args.exif)
    print(engine.predict_nn(args.image, exif_payload))
