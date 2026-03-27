# -*- coding: utf-8 -*-
"""
Dataset Quality Analyzer
Analisa qualidade do dataset e fornece insights

Data: 16 Novembro 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import imagehash
from PIL import Image
import rawpy
import numpy as np
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class DatasetQualityAnalyzer:
    """Analisa qualidade do dataset Lightroom"""

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)

        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset não encontrado: {dataset_path}")

        self.df = pd.read_csv(dataset_path)
        self.issues = []
        self.recommendations = []
        self.metrics = {}

    def analyze(self) -> Dict:
        """Executa análise completa"""

        logger.info("🔍 Iniciando análise de qualidade do dataset...")

        # Análises
        self._check_size()
        self._check_balance()
        self._check_diversity()
        self._check_duplicates()
        self._check_missing_values()
        self._check_slider_distribution()
        self._check_rating_distribution()

        # Calcular score final
        score = self._calculate_quality_score()

        return {
            'score': score,
            'grade': self._get_grade(score),
            'issues': self.issues,
            'recommendations': self.recommendations,
            'metrics': self.metrics,
            'summary': self._generate_summary()
        }

    def _check_size(self):
        """Verifica tamanho do dataset"""
        num_samples = len(self.df)
        self.metrics['num_samples'] = num_samples

        if num_samples < 30:
            self.issues.append("❌ Dataset MUITO pequeno (< 30 fotos)")
            self.recommendations.append("Adicione pelo menos 30 fotos para treino básico")
        elif num_samples < 50:
            self.issues.append("⚠️ Dataset pequeno (< 50 fotos)")
            self.recommendations.append("Use Transfer Learning (CLIP) para melhores resultados")
        elif num_samples < 100:
            self.issues.append("⚠️ Dataset moderado (< 100 fotos)")
            self.recommendations.append("Transfer Learning recomendado")
        else:
            self.recommendations.append("✅ Tamanho de dataset adequado")

    def _check_balance(self):
        """Verifica balanceamento de classes"""
        if 'preset_name' not in self.df.columns:
            self.metrics['has_presets'] = False
            return

        self.metrics['has_presets'] = True
        class_counts = self.df['preset_name'].value_counts()
        self.metrics['num_classes'] = len(class_counts)
        self.metrics['class_distribution'] = class_counts.to_dict()

        # Verificar desbalanceamento
        max_count = class_counts.max()
        min_count = class_counts.min()
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

        self.metrics['imbalance_ratio'] = imbalance_ratio

        if imbalance_ratio > 10:
            self.issues.append(f"❌ Dataset MUITO desbalanceado (ratio: {imbalance_ratio:.1f})")
            self.recommendations.append("Adicione mais fotos das classes minoritárias")
        elif imbalance_ratio > 5:
            self.issues.append(f"⚠️ Dataset desbalanceado (ratio: {imbalance_ratio:.1f})")
            self.recommendations.append("Considere balancear as classes ou usar class weights")
        else:
            self.recommendations.append("✅ Dataset bem balanceado")

    def _check_diversity(self):
        """Verifica diversidade de ajustes"""
        # Sliders principais
        main_sliders = ['exposure', 'contrast', 'highlights', 'shadows',
                       'whites', 'blacks', 'vibrance', 'saturation']

        available_sliders = [s for s in main_sliders if s in self.df.columns]

        if not available_sliders:
            self.issues.append("❌ Sem sliders no dataset")
            return

        # Calcular variância dos sliders
        variances = {}
        for slider in available_sliders:
            var = self.df[slider].var()
            variances[slider] = var

        self.metrics['slider_variances'] = variances

        # Sliders com pouca variação
        low_variance = [s for s, v in variances.items() if v < 10]

        if len(low_variance) > len(available_sliders) * 0.5:
            self.issues.append("⚠️ Muitos sliders com pouca variação")
            self.recommendations.append("Aumente a diversidade de ajustes nas fotos")
        else:
            self.recommendations.append("✅ Boa diversidade de ajustes")

    def _check_duplicates(self):
        """Verifica duplicatas aproximadas (perceptual hash)"""
        if 'image_path' not in self.df.columns:
            logger.warning("Coluna 'image_path' não encontrada, pulando verificação de duplicatas")
            return

        logger.info("Verificando duplicatas (pode demorar)...")

        hashes = {}
        duplicates = []
        processed = 0
        errors = 0

        for idx, row in self.df.iterrows():
            img_path = row['image_path']

            if not Path(img_path).exists():
                errors += 1
                continue

            try:
                img_hash = self._compute_image_hash(img_path)

                # Procurar similares (distance < 5)
                for existing_hash, existing_idx in hashes.items():
                    if img_hash - existing_hash < 5:
                        duplicates.append((idx, existing_idx))

                hashes[img_hash] = idx
                processed += 1
            except Exception as e:
                logger.warning(f"Erro ao processar {img_path}: {e}")
                errors += 1

        self.metrics['num_duplicates'] = len(duplicates)
        self.metrics['images_processed_for_duplicates'] = processed
        self.metrics['errors_processing_images'] = errors

        if len(duplicates) > 0:
            self.issues.append(f"⚠️ {len(duplicates)} possíveis duplicatas encontradas")
            self.recommendations.append("Revise e remova duplicatas para melhorar qualidade")
        else:
            self.recommendations.append("✅ Sem duplicatas detectadas")

        if errors > 0:
            self.issues.append(f"⚠️ {errors} imagens não puderam ser processadas")

    def _compute_image_hash(self, img_path: str):
        """
        Calcula perceptual hash considerando RAWs e formatos comuns.
        Usa rawpy para .ARW/.DNG/etc e PIL para restantes.
        """
        path = Path(img_path)
        suffix = path.suffix.lower()

        try:
            if suffix in {'.arw', '.dng', '.nef', '.cr2', '.cr3', '.orf', '.rw2'}:
                with rawpy.imread(str(path)) as raw:
                    img = raw.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=True, output_bps=8)
                    img = Image.fromarray(img)
            else:
                img = Image.open(str(path)).convert('RGB')
        except Exception as e:
            logger.warning(f"Erro ao carregar {img_path} para hash: {e}")
            raise

        try:
            return imagehash.average_hash(img)
        finally:
            img.close()

    def _check_missing_values(self):
        """Verifica valores faltantes"""
        missing = self.df.isnull().sum()
        missing = missing[missing > 0]

        if len(missing) > 0:
            self.metrics['missing_values'] = missing.to_dict()
            self.issues.append(f"⚠️ {len(missing)} colunas com valores faltantes")
            self.recommendations.append("Preencha valores faltantes ou use skip_missing=True")

    def _check_slider_distribution(self):
        """Verifica distribuição dos valores dos sliders"""
        slider_cols = [col for col in self.df.columns
                      if col not in ['image_path', 'preset_name', 'rating']]

        # Detectar sliders que nunca são usados (sempre 0)
        unused_sliders = []
        for col in slider_cols:
            if col in self.df.columns and self.df[col].abs().max() < 0.1:  # Praticamente zero
                unused_sliders.append(col)

        self.metrics['unused_sliders'] = unused_sliders
        self.metrics['total_sliders'] = len(slider_cols)
        self.metrics['used_sliders'] = len(slider_cols) - len(unused_sliders)

        if len(unused_sliders) > 0:
            self.recommendations.append(
                f"ℹ️ {len(unused_sliders)} sliders nunca usados: {', '.join(unused_sliders[:3])}..."
            )

    def _check_rating_distribution(self):
        """Verifica distribuição de ratings"""
        if 'rating' not in self.df.columns:
            return

        rating_counts = self.df['rating'].value_counts().sort_index()
        self.metrics['rating_distribution'] = rating_counts.to_dict()
        self.metrics['has_ratings'] = True

        # Verificar se tem ratings diversificados
        if len(rating_counts) < 2:
            self.issues.append("⚠️ Todas as fotos têm o mesmo rating")
            self.recommendations.append("Adicione ratings variados para treino de culling")
        else:
            self.recommendations.append("✅ Ratings diversificados")

    def _calculate_quality_score(self) -> float:
        """Calcula score de qualidade (0-100)"""
        score = 100.0

        # Penalizações
        num_samples = self.metrics.get('num_samples', 0)

        # Tamanho do dataset
        if num_samples < 30:
            score -= 30
        elif num_samples < 50:
            score -= 15
        elif num_samples < 100:
            score -= 5

        # Balanceamento
        if self.metrics.get('has_presets', False):
            imbalance = self.metrics.get('imbalance_ratio', 1)
            if imbalance > 10:
                score -= 20
            elif imbalance > 5:
                score -= 10

        # Duplicatas
        num_dupes = self.metrics.get('num_duplicates', 0)
        if num_dupes > 0:
            score -= min(20, num_dupes * 2)

        # Missing values
        if 'missing_values' in self.metrics:
            score -= min(10, len(self.metrics['missing_values']) * 2)

        # Diversidade de sliders
        used_ratio = self.metrics.get('used_sliders', 1) / max(self.metrics.get('total_sliders', 1), 1)
        if used_ratio < 0.5:
            score -= 10

        return max(0, min(100, score))

    def _get_grade(self, score: float) -> str:
        """Converte score em grade"""
        if score >= 90:
            return "A - Excelente"
        elif score >= 80:
            return "B - Muito Bom"
        elif score >= 70:
            return "C - Bom"
        elif score >= 60:
            return "D - Razoável"
        else:
            return "F - Precisa Melhorias"

    def _generate_summary(self) -> str:
        """Gera resumo executivo"""
        score = self._calculate_quality_score()
        grade = self._get_grade(score)
        num_samples = self.metrics.get('num_samples', 0)
        num_issues = len(self.issues)

        summary = f"""📊 **Análise de Qualidade do Dataset**

**Score:** {score:.1f}/100 ({grade})
**Amostras:** {num_samples}
**Problemas Identificados:** {num_issues}

"""

        if score >= 80:
            summary += "✅ Dataset de alta qualidade! Pronto para treino.\n"
        elif score >= 60:
            summary += "⚠️ Dataset razoável. Revise as recomendações.\n"
        else:
            summary += "❌ Dataset precisa de melhorias significativas.\n"

        return summary
