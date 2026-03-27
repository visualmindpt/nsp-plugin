# -*- coding: utf-8 -*-
"""
Scene Classification usando CLIP
Classifica automaticamente cenas de fotografia

Data: 16 Novembro 2025
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass

# Import CLIP (se disponível)
try:
    from services.ai_core.modern_feature_extractor import ModernFeatureExtractor
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    logging.warning("CLIP não disponível. Scene Classification requer CLIP.")

logger = logging.getLogger(__name__)


@dataclass
class SceneCategory:
    """Categoria de cena"""
    name: str
    description: str
    prompts: List[str]  # Prompts de texto para CLIP


# Categorias de cena para fotografia
SCENE_CATEGORIES = [
    SceneCategory(
        name="portrait",
        description="Retrato/Pessoa",
        prompts=[
            "a portrait photo of a person",
            "a headshot photograph",
            "a close-up portrait",
            "a person's face"
        ]
    ),
    SceneCategory(
        name="landscape",
        description="Paisagem/Natureza",
        prompts=[
            "a landscape photograph",
            "a nature scene",
            "mountains and sky",
            "outdoor scenery"
        ]
    ),
    SceneCategory(
        name="urban",
        description="Urbano/Arquitetura",
        prompts=[
            "an urban photograph",
            "city architecture",
            "buildings and streets",
            "cityscape photo"
        ]
    ),
    SceneCategory(
        name="food",
        description="Comida/Gastronomia",
        prompts=[
            "food photography",
            "a dish on a table",
            "culinary photograph",
            "restaurant food"
        ]
    ),
    SceneCategory(
        name="product",
        description="Produto/Objeto",
        prompts=[
            "product photography",
            "commercial product shot",
            "an object on white background",
            "studio product photo"
        ]
    ),
    SceneCategory(
        name="wildlife",
        description="Vida Selvagem/Animais",
        prompts=[
            "wildlife photography",
            "an animal in nature",
            "bird photograph",
            "wild animal photo"
        ]
    ),
    SceneCategory(
        name="event",
        description="Evento/Social",
        prompts=[
            "event photography",
            "a social gathering",
            "party photograph",
            "wedding photo"
        ]
    ),
    SceneCategory(
        name="sports",
        description="Desporto/Ação",
        prompts=[
            "sports photography",
            "action shot",
            "athletic movement",
            "sports event photo"
        ]
    ),
    SceneCategory(
        name="abstract",
        description="Abstrato/Arte",
        prompts=[
            "abstract photography",
            "artistic composition",
            "creative abstract photo",
            "experimental photography"
        ]
    ),
    SceneCategory(
        name="night",
        description="Noturna/Low Light",
        prompts=[
            "night photography",
            "low light scene",
            "nighttime photograph",
            "evening sky photo"
        ]
    ),
]


class SceneClassifier:
    """Classificador de cenas usando CLIP zero-shot"""

    def __init__(
        self,
        model_name: str = "clip",
        device: Optional[str] = None,
        categories: Optional[List[SceneCategory]] = None
    ):
        """
        Args:
            model_name: Nome do modelo CLIP
            device: Dispositivo (cuda/cpu/mps)
            categories: Lista de categorias customizadas (opcional)
        """
        if not CLIP_AVAILABLE:
            raise ImportError("CLIP não disponível. Instale: pip install transformers torch")

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.categories = categories or SCENE_CATEGORIES

        logger.info(f"🎬 Inicializando Scene Classifier ({model_name})...")

        # Carregar CLIP
        self.extractor = ModernFeatureExtractor(
            model_name=model_name,
            device=str(self.device)
        )

        # Pré-computar embeddings de texto para todas as categorias
        self._precompute_text_embeddings()

        logger.info(f"✅ Scene Classifier pronto! {len(self.categories)} categorias")

    def _precompute_text_embeddings(self):
        """Pré-computa embeddings de texto para todas as categorias"""
        logger.info("📝 Pré-computando embeddings de texto...")

        self.category_embeddings = {}

        for category in self.categories:
            # Computar embeddings para todos os prompts da categoria
            embeddings = []

            for prompt in category.prompts:
                # Usar método de extração de features (assumindo que aceita texto)
                # NOTA: Isso depende da implementação do ModernFeatureExtractor
                # Se não suportar texto, usar transformers diretamente
                try:
                    # Tentar extrair features de texto
                    embedding = self._extract_text_features(prompt)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.warning(f"Erro ao processar prompt '{prompt}': {e}")

            if embeddings:
                # Média dos embeddings dos prompts
                category_embedding = np.mean(embeddings, axis=0)
                # Normalizar
                category_embedding = category_embedding / np.linalg.norm(category_embedding)
                self.category_embeddings[category.name] = category_embedding

        logger.info(f"✅ {len(self.category_embeddings)} categorias processadas")

    def _extract_text_features(self, text: str) -> np.ndarray:
        """
        Extrai features de texto usando CLIP

        NOTA: ModernFeatureExtractor pode não suportar texto diretamente.
        Nesse caso, usar transformers diretamente.
        """
        # Implementação alternativa usando transformers diretamente
        from transformers import CLIPProcessor, CLIPModel

        if not hasattr(self, '_clip_model'):
            self._clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self._clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            self._clip_model.to(self.device)
            self._clip_model.eval()

        inputs = self._clip_processor(text=[text], return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            text_features = self._clip_model.get_text_features(**inputs)

        return text_features.cpu().numpy()[0]

    def classify_image(
        self,
        image_path: str,
        top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Classifica uma imagem

        Args:
            image_path: Caminho da imagem
            top_k: Número de categorias top a retornar

        Returns:
            Lista de tuplas (category_name, confidence)
        """
        # Carregar imagem
        image = Image.open(image_path).convert('RGB')

        # Extrair features da imagem
        image_features = self.extractor.extract_features(image)

        # Normalizar
        image_features = image_features / np.linalg.norm(image_features)

        # Calcular similaridade com todas as categorias
        similarities = {}

        for category_name, category_embedding in self.category_embeddings.items():
            # Similaridade cosseno
            similarity = np.dot(image_features, category_embedding)
            similarities[category_name] = float(similarity)

        # Ordenar por similaridade
        sorted_categories = sorted(
            similarities.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_categories[:top_k]

    def classify_batch(
        self,
        image_paths: List[str],
        top_k: int = 3
    ) -> List[List[Tuple[str, float]]]:
        """
        Classifica múltiplas imagens

        Args:
            image_paths: Lista de caminhos de imagens
            top_k: Número de categorias top a retornar

        Returns:
            Lista de resultados de classificação
        """
        results = []

        for i, image_path in enumerate(image_paths):
            try:
                result = self.classify_image(image_path, top_k=top_k)
                results.append(result)

                if (i + 1) % 10 == 0:
                    logger.info(f"Processadas {i + 1}/{len(image_paths)} imagens...")

            except Exception as e:
                logger.error(f"Erro ao processar {image_path}: {e}")
                results.append([])

        return results

    def get_category_distribution(
        self,
        image_paths: List[str]
    ) -> Dict[str, int]:
        """
        Obtém distribuição de categorias em um conjunto de imagens

        Args:
            image_paths: Lista de caminhos de imagens

        Returns:
            Dicionário {category_name: count}
        """
        logger.info(f"📊 Analisando {len(image_paths)} imagens...")

        category_counts = {cat.name: 0 for cat in self.categories}

        for i, image_path in enumerate(image_paths):
            try:
                # Classificar (pegar apenas top 1)
                results = self.classify_image(image_path, top_k=1)

                if results:
                    top_category = results[0][0]
                    category_counts[top_category] += 1

                if (i + 1) % 50 == 0:
                    logger.info(f"Processadas {i + 1}/{len(image_paths)}...")

            except Exception as e:
                logger.error(f"Erro ao processar {image_path}: {e}")

        return category_counts

    def add_scene_tags_to_dataset(
        self,
        dataset_csv: str,
        output_csv: str,
        image_path_column: str = 'image_path',
        top_k: int = 1
    ):
        """
        Adiciona tags de cena a um dataset CSV

        Args:
            dataset_csv: Caminho do CSV de entrada
            output_csv: Caminho do CSV de saída
            image_path_column: Nome da coluna com paths das imagens
            top_k: Número de tags a adicionar
        """
        import pandas as pd

        logger.info(f"📝 Adicionando scene tags ao dataset: {dataset_csv}")

        # Carregar dataset
        df = pd.read_csv(dataset_csv)

        if image_path_column not in df.columns:
            raise ValueError(f"Coluna '{image_path_column}' não encontrada no dataset")

        # Classificar todas as imagens
        image_paths = df[image_path_column].tolist()
        classifications = self.classify_batch(image_paths, top_k=top_k)

        # Adicionar colunas ao dataframe
        for k in range(top_k):
            scene_col = f'scene_category_{k+1}' if top_k > 1 else 'scene_category'
            confidence_col = f'scene_confidence_{k+1}' if top_k > 1 else 'scene_confidence'

            scenes = []
            confidences = []

            for classification in classifications:
                if len(classification) > k:
                    scenes.append(classification[k][0])
                    confidences.append(classification[k][1])
                else:
                    scenes.append(None)
                    confidences.append(0.0)

            df[scene_col] = scenes
            df[confidence_col] = confidences

        # Salvar
        df.to_csv(output_csv, index=False)
        logger.info(f"✅ Dataset com scene tags salvo em: {output_csv}")

        # Estatísticas
        if 'scene_category' in df.columns:
            distribution = df['scene_category'].value_counts()
            logger.info("📊 Distribuição de cenas:")
            for scene, count in distribution.items():
                logger.info(f"   {scene}: {count}")


def classify_lightroom_catalog(
    catalog_csv: str,
    output_csv: Optional[str] = None
) -> Dict[str, int]:
    """
    Função helper para classificar imagens de um catálogo Lightroom

    Args:
        catalog_csv: Caminho do CSV do catálogo
        output_csv: Caminho de saída (opcional)

    Returns:
        Distribuição de categorias
    """
    classifier = SceneClassifier()

    import pandas as pd
    df = pd.read_csv(catalog_csv)

    if 'image_path' not in df.columns:
        raise ValueError("CSV deve conter coluna 'image_path'")

    image_paths = df['image_path'].tolist()

    # Obter distribuição
    distribution = classifier.get_category_distribution(image_paths)

    # Adicionar tags ao dataset (se output especificado)
    if output_csv:
        classifier.add_scene_tags_to_dataset(
            catalog_csv,
            output_csv,
            image_path_column='image_path',
            top_k=3
        )

    return distribution


if __name__ == "__main__":
    # Exemplo de uso
    print("=" * 80)
    print("SCENE CLASSIFIER - Exemplo de Uso")
    print("=" * 80)
    print()

    print("# Classificar uma imagem")
    print("-" * 80)
    print("""
from services.scene_classifier import SceneClassifier

classifier = SceneClassifier()
results = classifier.classify_image("photo.jpg", top_k=3)

for category, confidence in results:
    print(f"{category}: {confidence:.2%}")
    """)

    print()
    print("# Adicionar scene tags a dataset")
    print("-" * 80)
    print("""
from services.scene_classifier import classify_lightroom_catalog

distribution = classify_lightroom_catalog(
    "data/lightroom_dataset.csv",
    "data/lightroom_dataset_with_scenes.csv"
)

print("Distribuição de cenas:")
for scene, count in distribution.items():
    print(f"  {scene}: {count}")
    """)

    print()
    print("Categorias disponíveis:")
    print("-" * 80)
    for cat in SCENE_CATEGORIES:
        print(f"  • {cat.name}: {cat.description}")

    print()
    print("=" * 80)
