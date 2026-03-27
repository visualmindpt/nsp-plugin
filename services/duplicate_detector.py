# -*- coding: utf-8 -*-
"""
Duplicate Detection
Detecta fotos duplicadas ou muito similares usando perceptual hashing

Data: 16 Novembro 2025
"""

import imagehash
from PIL import Image
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """Grupo de imagens duplicadas"""
    representative: str  # Imagem representativa do grupo
    duplicates: List[str]  # Outras imagens no grupo
    hash_value: str  # Hash perceptual
    similarity_threshold: int  # Limiar usado


class DuplicateDetector:
    """
    Detector de duplicatas usando Perceptual Hashing

    Métodos suportados:
    - Average Hash (aHash): Rápido, bom para redimensionamentos
    - Perceptual Hash (pHash): Melhor para rotações e alterações de cor
    - Difference Hash (dHash): Rápido, bom para gradientes
    - Wavelet Hash (wHash): Melhor para detectar alterações sutis
    """

    def __init__(
        self,
        hash_method: str = "average",
        hash_size: int = 8
    ):
        """
        Args:
            hash_method: Método de hashing (average, perceptual, difference, wavelet)
            hash_size: Tamanho do hash (padrão: 8)
        """
        self.hash_method = hash_method
        self.hash_size = hash_size

        # Selecionar função de hash
        self.hash_func = self._get_hash_function()

        logger.info(f"🔍 Duplicate Detector inicializado ({hash_method} hash)")

    def _get_hash_function(self):
        """Retorna a função de hash apropriada"""
        hash_functions = {
            'average': lambda img: imagehash.average_hash(img, self.hash_size),
            'perceptual': lambda img: imagehash.phash(img, self.hash_size),
            'difference': lambda img: imagehash.dhash(img, self.hash_size),
            'wavelet': lambda img: imagehash.whash(img, self.hash_size),
        }

        if self.hash_method not in hash_functions:
            logger.warning(f"Método '{self.hash_method}' inválido. Usando 'average'.")
            return hash_functions['average']

        return hash_functions[self.hash_method]

    def compute_hash(self, image_path: str) -> Optional[imagehash.ImageHash]:
        """
        Computa hash de uma imagem

        Args:
            image_path: Caminho da imagem

        Returns:
            ImageHash ou None se erro
        """
        try:
            img = Image.open(image_path)
            return self.hash_func(img)
        except Exception as e:
            logger.error(f"Erro ao processar {image_path}: {e}")
            return None

    def find_duplicates(
        self,
        image_paths: List[str],
        threshold: int = 5,
        progress_callback: Optional[callable] = None
    ) -> List[DuplicateGroup]:
        """
        Encontra grupos de imagens duplicadas

        Args:
            image_paths: Lista de caminhos de imagens
            threshold: Limiar de diferença de hash (0-64)
                      0 = identical, 5 = very similar, 10 = similar, >10 = different
            progress_callback: Função de callback para progresso (opcional)

        Returns:
            Lista de grupos de duplicatas
        """
        logger.info(f"🔍 Procurando duplicatas em {len(image_paths)} imagens...")
        logger.info(f"   Método: {self.hash_method} | Threshold: {threshold}")

        # Computar hashes
        hashes = {}
        errors = 0

        for i, image_path in enumerate(image_paths):
            img_hash = self.compute_hash(image_path)

            if img_hash is not None:
                hashes[image_path] = img_hash
            else:
                errors += 1

            # Progress callback
            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, len(image_paths))

        logger.info(f"✅ {len(hashes)} hashes computados ({errors} erros)")

        # Encontrar grupos de duplicatas
        duplicate_groups = []
        processed = set()

        for img_path, img_hash in hashes.items():
            if img_path in processed:
                continue

            # Encontrar todas as imagens similares a esta
            group_members = [img_path]

            for other_path, other_hash in hashes.items():
                if other_path == img_path or other_path in processed:
                    continue

                # Calcular diferença de hash (Hamming distance)
                distance = img_hash - other_hash

                if distance <= threshold:
                    group_members.append(other_path)
                    processed.add(other_path)

            # Se encontrou duplicatas, criar grupo
            if len(group_members) > 1:
                group = DuplicateGroup(
                    representative=img_path,
                    duplicates=group_members[1:],
                    hash_value=str(img_hash),
                    similarity_threshold=threshold
                )
                duplicate_groups.append(group)
                processed.add(img_path)

        logger.info(f"📊 Encontrados {len(duplicate_groups)} grupos de duplicatas")
        total_duplicates = sum(len(g.duplicates) for g in duplicate_groups)
        logger.info(f"   Total de duplicatas: {total_duplicates}")

        return duplicate_groups

    def find_similar_pairs(
        self,
        image_paths: List[str],
        threshold: int = 5
    ) -> List[Tuple[str, str, int]]:
        """
        Encontra pares de imagens similares

        Args:
            image_paths: Lista de caminhos
            threshold: Limiar de similaridade

        Returns:
            Lista de tuplas (image1, image2, distance)
        """
        logger.info(f"🔍 Procurando pares similares em {len(image_paths)} imagens...")

        # Computar hashes
        hashes = {}
        for image_path in image_paths:
            img_hash = self.compute_hash(image_path)
            if img_hash is not None:
                hashes[image_path] = img_hash

        # Encontrar pares
        similar_pairs = []

        image_list = list(hashes.keys())
        for i in range(len(image_list)):
            for j in range(i + 1, len(image_list)):
                img1 = image_list[i]
                img2 = image_list[j]

                distance = hashes[img1] - hashes[img2]

                if distance <= threshold:
                    similar_pairs.append((img1, img2, distance))

        logger.info(f"✅ Encontrados {len(similar_pairs)} pares similares")

        return similar_pairs

    def remove_duplicates_from_dataset(
        self,
        dataset_csv: str,
        output_csv: str,
        image_path_column: str = 'image_path',
        threshold: int = 5,
        keep_strategy: str = 'first'
    ) -> Dict[str, any]:
        """
        Remove duplicatas de um dataset CSV

        Args:
            dataset_csv: Caminho do CSV de entrada
            output_csv: Caminho do CSV de saída
            image_path_column: Nome da coluna com paths
            threshold: Limiar de similaridade
            keep_strategy: Estratégia para escolher qual manter ('first', 'last', 'best_quality')

        Returns:
            Dict com estatísticas
        """
        logger.info(f"🧹 Removendo duplicatas de: {dataset_csv}")

        # Carregar dataset
        df = pd.read_csv(dataset_csv)
        original_size = len(df)

        if image_path_column not in df.columns:
            raise ValueError(f"Coluna '{image_path_column}' não encontrada")

        # Encontrar duplicatas
        image_paths = df[image_path_column].tolist()
        duplicate_groups = self.find_duplicates(image_paths, threshold=threshold)

        # Determinar quais remover
        to_remove = set()

        for group in duplicate_groups:
            # Estratégia: manter representative, remover duplicates
            if keep_strategy == 'first':
                # Manter o primeiro (representative)
                to_remove.update(group.duplicates)
            elif keep_strategy == 'last':
                # Manter o último
                to_remove.add(group.representative)
                to_remove.update(group.duplicates[:-1])
            elif keep_strategy == 'best_quality':
                # Escolher baseado em alguma métrica de qualidade
                # (não implementado - requer metadados de qualidade)
                logger.warning("Estratégia 'best_quality' não implementada. Usando 'first'.")
                to_remove.update(group.duplicates)

        # Filtrar dataset
        df_clean = df[~df[image_path_column].isin(to_remove)]

        # Salvar
        df_clean.to_csv(output_csv, index=False)

        stats = {
            'original_size': original_size,
            'cleaned_size': len(df_clean),
            'removed_count': len(to_remove),
            'duplicate_groups': len(duplicate_groups),
            'output_file': output_csv
        }

        logger.info(f"✅ Dataset limpo salvo em: {output_csv}")
        logger.info(f"   Original: {original_size} | Limpo: {len(df_clean)} | Removidos: {len(to_remove)}")

        return stats

    def generate_duplicate_report(
        self,
        duplicate_groups: List[DuplicateGroup],
        output_file: str
    ):
        """
        Gera relatório HTML com duplicatas

        Args:
            duplicate_groups: Lista de grupos
            output_file: Caminho do arquivo HTML de saída
        """
        logger.info(f"📝 Gerando relatório de duplicatas: {output_file}")

        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "    <meta charset='utf-8'>",
            "    <title>Relatório de Duplicatas</title>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 20px; }",
            "        .group { border: 1px solid #ccc; margin: 20px 0; padding: 15px; }",
            "        .group h3 { margin-top: 0; }",
            "        .images { display: flex; flex-wrap: wrap; gap: 10px; }",
            "        .image-container { text-align: center; }",
            "        .image-container img { max-width: 200px; max-height: 200px; }",
            "        .representative { border: 3px solid green; }",
            "        .duplicate { border: 3px solid orange; }",
            "    </style>",
            "</head>",
            "<body>",
            f"    <h1>Relatório de Duplicatas</h1>",
            f"    <p>Total de grupos: {len(duplicate_groups)}</p>",
            f"    <p>Total de duplicatas: {sum(len(g.duplicates) for g in duplicate_groups)}</p>",
            "    <hr>",
        ]

        for i, group in enumerate(duplicate_groups, 1):
            html_lines.append(f"    <div class='group'>")
            html_lines.append(f"        <h3>Grupo {i}</h3>")
            html_lines.append(f"        <p>Hash: {group.hash_value}</p>")
            html_lines.append(f"        <p>Threshold: {group.similarity_threshold}</p>")
            html_lines.append(f"        <div class='images'>")

            # Imagem representativa
            html_lines.append(f"            <div class='image-container representative'>")
            html_lines.append(f"                <img src='file://{group.representative}' alt='Representative'>")
            html_lines.append(f"                <p><strong>Representative</strong></p>")
            html_lines.append(f"                <p><small>{Path(group.representative).name}</small></p>")
            html_lines.append(f"            </div>")

            # Duplicatas
            for dup_path in group.duplicates:
                html_lines.append(f"            <div class='image-container duplicate'>")
                html_lines.append(f"                <img src='file://{dup_path}' alt='Duplicate'>")
                html_lines.append(f"                <p><strong>Duplicate</strong></p>")
                html_lines.append(f"                <p><small>{Path(dup_path).name}</small></p>")
                html_lines.append(f"            </div>")

            html_lines.append(f"        </div>")
            html_lines.append(f"    </div>")

        html_lines.extend([
            "</body>",
            "</html>"
        ])

        # Salvar
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_lines))

        logger.info(f"✅ Relatório salvo em: {output_file}")


def detect_duplicates_in_lightroom_catalog(
    catalog_csv: str,
    threshold: int = 5,
    remove_duplicates: bool = False,
    output_csv: Optional[str] = None,
    report_html: Optional[str] = None
) -> Dict[str, any]:
    """
    Função helper para detectar duplicatas em catálogo Lightroom

    Args:
        catalog_csv: Caminho do CSV do catálogo
        threshold: Limiar de similaridade
        remove_duplicates: Se True, remove duplicatas
        output_csv: Caminho de saída para dataset limpo (se remove_duplicates=True)
        report_html: Caminho para relatório HTML (opcional)

    Returns:
        Dict com estatísticas e grupos
    """
    detector = DuplicateDetector(hash_method='average')

    # Carregar dataset
    df = pd.read_csv(catalog_csv)
    image_paths = df['image_path'].tolist()

    # Encontrar duplicatas
    duplicate_groups = detector.find_duplicates(image_paths, threshold=threshold)

    # Gerar relatório HTML (se especificado)
    if report_html:
        detector.generate_duplicate_report(duplicate_groups, report_html)

    # Remover duplicatas (se especificado)
    stats = None
    if remove_duplicates:
        if not output_csv:
            output_csv = catalog_csv.replace('.csv', '_no_duplicates.csv')

        stats = detector.remove_duplicates_from_dataset(
            catalog_csv,
            output_csv,
            threshold=threshold
        )

    return {
        'duplicate_groups': duplicate_groups,
        'num_groups': len(duplicate_groups),
        'total_duplicates': sum(len(g.duplicates) for g in duplicate_groups),
        'stats': stats
    }


if __name__ == "__main__":
    # Exemplo de uso
    print("=" * 80)
    print("DUPLICATE DETECTOR - Exemplo de Uso")
    print("=" * 80)
    print()

    print("# 1. Detectar duplicatas")
    print("-" * 80)
    print("""
from services.duplicate_detector import DuplicateDetector

detector = DuplicateDetector(hash_method='average')

image_paths = ['photo1.jpg', 'photo2.jpg', 'photo3.jpg', ...]
duplicate_groups = detector.find_duplicates(image_paths, threshold=5)

for group in duplicate_groups:
    print(f"Representative: {group.representative}")
    print(f"Duplicates: {group.duplicates}")
    """)

    print()
    print("# 2. Remover duplicatas de dataset")
    print("-" * 80)
    print("""
from services.duplicate_detector import detect_duplicates_in_lightroom_catalog

result = detect_duplicates_in_lightroom_catalog(
    "data/lightroom_dataset.csv",
    threshold=5,
    remove_duplicates=True,
    output_csv="data/lightroom_dataset_clean.csv",
    report_html="duplicate_report.html"
)

print(f"Grupos de duplicatas: {result['num_groups']}")
print(f"Total removido: {result['total_duplicates']}")
    """)

    print()
    print("# 3. Thresholds recomendados")
    print("-" * 80)
    print("  • threshold=0  : Apenas imagens IDÊNTICAS")
    print("  • threshold=5  : Imagens MUITO SIMILARES (recomendado)")
    print("  • threshold=10 : Imagens SIMILARES")
    print("  • threshold=15 : Imagens PARECIDAS")
    print()

    print("=" * 80)
