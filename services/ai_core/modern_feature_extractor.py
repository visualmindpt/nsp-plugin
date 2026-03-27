"""
Modern Feature Extractor usando modelos pré-treinados de última geração.

FASE 2.1 - Transfer Learning Avançado
Suporta:
- CLIP ViT-B/32: Excelente para semântica visual (512 dims)
- DINOv2: Estado da arte para features visuais (768 dims)
- ConvNeXt V2: Bom compromisso velocidade/qualidade (1024 dims)

Benefícios esperados:
- Features 3-5x mais ricas que ResNet18
- Melhor compreensão de composição fotográfica
- +15-20% accuracy esperado
"""

import torch
import torch.nn as nn
from transformers import (
    CLIPVisionModel,
    CLIPProcessor,
    AutoModel,
    AutoImageProcessor,
    ConvNextV2Model
)
from PIL import Image
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Union, Literal
import logging
import pickle
from tqdm import tqdm

logger = logging.getLogger(__name__)

ModelType = Literal["clip", "dinov2", "convnext"]


class ModernFeatureExtractor:
    """
    Extrator de features usando modelos pré-treinados modernos.

    Características:
    - GPU acceleration (com fallback para CPU)
    - Caching de features extraídas
    - Batch processing para eficiência
    - Support para múltiplos modelos
    """

    def __init__(
        self,
        model_name: ModelType = "clip",
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        enable_caching: bool = True
    ):
        """
        Inicializa o extrator de features moderno.

        Args:
            model_name: Modelo a usar ("clip", "dinov2", "convnext")
            device: Device PyTorch ("cuda", "cpu", ou None para auto-detect)
            cache_dir: Diretório para cache de features (None = sem cache)
            enable_caching: Se True, usa cache para features já extraídas
        """
        self.model_name = model_name
        self.enable_caching = enable_caching

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Initializing {model_name} feature extractor on {self.device}")

        # Setup cache
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, np.ndarray] = {}

        # Load model and processor
        self._load_model()

    def _load_model(self):
        """Carrega o modelo e processador apropriado."""
        try:
            if self.model_name == "clip":
                self._load_clip()
            elif self.model_name == "dinov2":
                self._load_dinov2()
            elif self.model_name == "convnext":
                self._load_convnext()
            else:
                raise ValueError(f"Unknown model: {self.model_name}")

            self.model.eval()
            logger.info(f"Successfully loaded {self.model_name} model")

        except Exception as e:
            logger.error(f"Failed to load {self.model_name}: {e}")
            raise

    def _load_clip(self):
        """Carrega CLIP ViT-B/32."""
        model_id = "openai/clip-vit-base-patch32"
        self.processor = CLIPProcessor.from_pretrained(model_id)
        self.model = CLIPVisionModel.from_pretrained(model_id)
        self.model.to(self.device)
        self.feature_dim = 512

    def _load_dinov2(self):
        """Carrega DINOv2 base."""
        model_id = "facebook/dinov2-base"
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id)
        self.model.to(self.device)
        self.feature_dim = 768

    def _load_convnext(self):
        """Carrega ConvNeXt V2 base."""
        model_id = "facebook/convnextv2-base-22k-224"
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = ConvNextV2Model.from_pretrained(model_id)
        self.model.to(self.device)
        self.feature_dim = 1024

    def extract_features(
        self,
        image_path: Union[str, Path],
        use_cache: bool = True
    ) -> np.ndarray:
        """
        Extrai features de uma imagem.

        Args:
            image_path: Caminho para a imagem
            use_cache: Se True, usa cache (se disponível)

        Returns:
            Feature vector (numpy array)
        """
        image_path = Path(image_path)

        # Check cache
        if use_cache and self.enable_caching:
            cache_key = self._get_cache_key(image_path)

            # Memory cache
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Disk cache
            if self.cache_dir:
                cache_file = self.cache_dir / f"{cache_key}.pkl"
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        features = pickle.load(f)
                    self._cache[cache_key] = features
                    return features

        # Extract features
        try:
            image = Image.open(image_path).convert('RGB')
            features = self._extract_from_image(image)

            # Save to cache
            if use_cache and self.enable_caching:
                cache_key = self._get_cache_key(image_path)
                self._cache[cache_key] = features

                if self.cache_dir:
                    cache_file = self.cache_dir / f"{cache_key}.pkl"
                    with open(cache_file, 'wb') as f:
                        pickle.dump(features, f)

            return features

        except Exception as e:
            logger.error(f"Failed to extract features from {image_path}: {e}")
            raise

    def _extract_from_image(self, image: Image.Image) -> np.ndarray:
        """Extrai features de uma imagem PIL."""
        # Preprocess
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Extract
        with torch.no_grad():
            if self.model_name == "clip":
                outputs = self.model(**inputs)
                features = outputs.pooler_output
            elif self.model_name == "dinov2":
                outputs = self.model(**inputs)
                features = outputs.last_hidden_state[:, 0]  # CLS token
            elif self.model_name == "convnext":
                outputs = self.model(**inputs)
                features = outputs.pooler_output

        # Convert to numpy
        features = features.cpu().numpy().squeeze()
        return features

    def extract_batch(
        self,
        image_paths: list,
        batch_size: int = 8,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Extrai features de múltiplas imagens em batches.

        Args:
            image_paths: Lista de caminhos de imagens
            batch_size: Tamanho do batch
            show_progress: Se True, mostra barra de progresso

        Returns:
            Array de features [num_images, feature_dim]
        """
        all_features = []

        iterator = range(0, len(image_paths), batch_size)
        if show_progress:
            iterator = tqdm(iterator, desc=f"Extracting features ({self.model_name})")

        for i in iterator:
            batch_paths = image_paths[i:i + batch_size]

            # Check cache first
            batch_features = []
            uncached_indices = []
            uncached_paths = []

            for idx, path in enumerate(batch_paths):
                path = Path(path)
                cache_key = self._get_cache_key(path)

                if self.enable_caching and cache_key in self._cache:
                    batch_features.append(self._cache[cache_key])
                else:
                    batch_features.append(None)
                    uncached_indices.append(idx)
                    uncached_paths.append(path)

            # Extract uncached
            if uncached_paths:
                try:
                    images = [Image.open(p).convert('RGB') for p in uncached_paths]

                    # Batch process
                    inputs = self.processor(images=images, return_tensors="pt")
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}

                    with torch.no_grad():
                        if self.model_name == "clip":
                            outputs = self.model(**inputs)
                            features = outputs.pooler_output
                        elif self.model_name == "dinov2":
                            outputs = self.model(**inputs)
                            features = outputs.last_hidden_state[:, 0]
                        elif self.model_name == "convnext":
                            outputs = self.model(**inputs)
                            features = outputs.pooler_output

                    features = features.cpu().numpy()

                    # Fill in batch_features
                    for feat_idx, batch_idx in enumerate(uncached_indices):
                        feat = features[feat_idx]
                        batch_features[batch_idx] = feat

                        # Cache
                        if self.enable_caching:
                            cache_key = self._get_cache_key(uncached_paths[feat_idx])
                            self._cache[cache_key] = feat

                except Exception as e:
                    logger.warning(f"Batch extraction failed: {e}. Falling back to individual.")
                    for idx, path in zip(uncached_indices, uncached_paths):
                        batch_features[idx] = self.extract_features(path)

            all_features.extend(batch_features)

        return np.array(all_features)

    def _get_cache_key(self, image_path: Path) -> str:
        """Gera chave de cache única para imagem."""
        # Use path hash + model name
        path_str = str(image_path.resolve())
        return f"{self.model_name}_{hash(path_str)}"

    def clear_cache(self):
        """Limpa cache em memória e disco."""
        self._cache.clear()

        if self.cache_dir and self.cache_dir.exists():
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            logger.info("Cache cleared")

    def get_feature_dim(self) -> int:
        """Retorna dimensão das features."""
        return self.feature_dim

    def save_cache_to_disk(self):
        """Salva cache em memória para disco."""
        if not self.cache_dir:
            logger.warning("No cache directory configured")
            return

        for cache_key, features in self._cache.items():
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump(features, f)

        logger.info(f"Saved {len(self._cache)} cached features to disk")


def compare_extractors(
    image_paths: list,
    models: list = ["clip", "dinov2", "convnext"],
    output_path: Optional[str] = None
) -> Dict:
    """
    Compara diferentes extractors em termos de velocidade e feature quality.

    Args:
        image_paths: Lista de imagens para testar
        models: Lista de modelos a comparar
        output_path: Caminho para salvar resultados (opcional)

    Returns:
        Dicionário com estatísticas de cada modelo
    """
    import time

    results = {}

    for model_name in models:
        logger.info(f"\nTesting {model_name}...")

        extractor = ModernFeatureExtractor(
            model_name=model_name,
            enable_caching=False  # Disable for fair comparison
        )

        # Time extraction
        start = time.time()
        features = extractor.extract_batch(
            image_paths,
            batch_size=8,
            show_progress=True
        )
        elapsed = time.time() - start

        results[model_name] = {
            'feature_dim': extractor.get_feature_dim(),
            'total_time': elapsed,
            'time_per_image': elapsed / len(image_paths),
            'features_shape': features.shape,
            'feature_mean': features.mean(),
            'feature_std': features.std()
        }

        logger.info(f"{model_name} results:")
        logger.info(f"  Feature dim: {results[model_name]['feature_dim']}")
        logger.info(f"  Total time: {elapsed:.2f}s")
        logger.info(f"  Time per image: {elapsed/len(image_paths):.3f}s")

    if output_path:
        import json
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    # Example: Extract features from a single image
    extractor = ModernFeatureExtractor(
        model_name="clip",
        cache_dir="data/feature_cache"
    )

    # Single image
    # features = extractor.extract_features("path/to/image.jpg")
    # print(f"Feature shape: {features.shape}")

    # Batch extraction
    # image_paths = list(Path("data/images").glob("*.jpg"))
    # features = extractor.extract_batch(image_paths, batch_size=16)
    # print(f"Batch features shape: {features.shape}")
