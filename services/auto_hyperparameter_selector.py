# -*- coding: utf-8 -*-
"""
Automatic Hyperparameter Selection
Seleciona automaticamente os melhores hiperparâmetros baseado no dataset

Data: 16 Novembro 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class AutoHyperparameterSelector:
    """Seleciona automaticamente hiperparâmetros baseado em características do dataset"""

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)

        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset não encontrado: {dataset_path}")

        self.df = pd.read_csv(dataset_path)
        self.recommendations = {}
        self.reasoning = {}

    def select_hyperparameters(self, model_type: str = "classifier") -> Dict[str, Any]:
        """
        Seleciona hiperparâmetros automaticamente

        Args:
            model_type: Tipo de modelo ("classifier", "regressor", "clip", "culling")

        Returns:
            Dicionário com hiperparâmetros recomendados
        """
        logger.info(f"🔍 Analisando dataset para seleção de hiperparâmetros ({model_type})...")

        # Análise do dataset
        analysis = self._analyze_dataset()

        # Selecionar hiperparâmetros baseado no tipo de modelo
        if model_type == "classifier":
            params = self._select_classifier_params(analysis)
        elif model_type == "regressor":
            params = self._select_regressor_params(analysis)
        elif model_type == "clip":
            params = self._select_clip_params(analysis)
        elif model_type == "culling":
            params = self._select_culling_params(analysis)
        else:
            raise ValueError(f"Tipo de modelo inválido: {model_type}")

        return {
            'hyperparameters': params,
            'reasoning': self.reasoning,
            'dataset_analysis': analysis
        }

    def _analyze_dataset(self) -> Dict[str, Any]:
        """Analisa características do dataset"""
        num_samples = len(self.df)

        # Verificar se tem presets
        has_presets = 'preset_name' in self.df.columns and self.df['preset_name'].notna().any()

        # Contar classes (se aplicável)
        num_classes = 0
        samples_per_class = []
        imbalance_ratio = 1.0

        if has_presets:
            class_counts = self.df['preset_name'].value_counts()
            num_classes = len(class_counts)
            samples_per_class = class_counts.tolist()
            max_count = class_counts.max()
            min_count = class_counts.min()
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

        # Verificar se tem ratings
        has_ratings = 'rating' in self.df.columns and self.df['rating'].notna().any()

        # Analisar sliders (features)
        slider_cols = [col for col in self.df.columns
                      if col not in ['image_path', 'preset_name', 'rating']]
        num_features = len(slider_cols)

        # Calcular variância dos sliders
        feature_variances = []
        for col in slider_cols:
            if col in self.df.columns:
                feature_variances.append(self.df[col].var())

        avg_variance = np.mean(feature_variances) if feature_variances else 0

        # Verificar valores faltantes
        missing_percentage = (self.df.isnull().sum().sum() / (num_samples * len(self.df.columns))) * 100

        return {
            'num_samples': num_samples,
            'has_presets': has_presets,
            'num_classes': num_classes,
            'samples_per_class': samples_per_class,
            'imbalance_ratio': imbalance_ratio,
            'has_ratings': has_ratings,
            'num_features': num_features,
            'avg_feature_variance': avg_variance,
            'missing_percentage': missing_percentage,
            'dataset_size_category': self._categorize_dataset_size(num_samples),
            'balance_category': self._categorize_balance(imbalance_ratio),
        }

    def _categorize_dataset_size(self, num_samples: int) -> str:
        """Categoriza tamanho do dataset"""
        if num_samples < 50:
            return "very_small"
        elif num_samples < 100:
            return "small"
        elif num_samples < 500:
            return "medium"
        elif num_samples < 1000:
            return "large"
        else:
            return "very_large"

    def _categorize_balance(self, ratio: float) -> str:
        """Categoriza balanceamento"""
        if ratio <= 2:
            return "excellent"
        elif ratio <= 5:
            return "good"
        elif ratio <= 10:
            return "moderate"
        else:
            return "poor"

    def _select_classifier_params(self, analysis: Dict) -> Dict[str, Any]:
        """Seleciona hiperparâmetros para classificador de presets"""
        params = {}

        # Epochs baseado no tamanho do dataset
        size_cat = analysis['dataset_size_category']
        if size_cat == "very_small":
            params['epochs'] = 200
            self.reasoning['epochs'] = "Dataset muito pequeno: mais epochs para aprender"
        elif size_cat == "small":
            params['epochs'] = 150
            self.reasoning['epochs'] = "Dataset pequeno: epochs aumentados"
        elif size_cat == "medium":
            params['epochs'] = 100
            self.reasoning['epochs'] = "Dataset médio: epochs padrão"
        else:
            params['epochs'] = 80
            self.reasoning['epochs'] = "Dataset grande: menos epochs necessários"

        # Batch size baseado no tamanho
        num_samples = analysis['num_samples']
        if num_samples < 50:
            params['batch_size'] = 8
            self.reasoning['batch_size'] = "Dataset pequeno: batch pequeno para melhor gradiente"
        elif num_samples < 200:
            params['batch_size'] = 16
            self.reasoning['batch_size'] = "Dataset médio: batch moderado"
        elif num_samples < 500:
            params['batch_size'] = 32
            self.reasoning['batch_size'] = "Dataset razoável: batch padrão"
        else:
            params['batch_size'] = 64
            self.reasoning['batch_size'] = "Dataset grande: batch maior para eficiência"

        # Learning rate baseado no tamanho e balanceamento
        if size_cat in ["very_small", "small"]:
            params['learning_rate'] = 0.0005
            self.reasoning['learning_rate'] = "LR reduzido para dataset pequeno"
        else:
            params['learning_rate'] = 0.001
            self.reasoning['learning_rate'] = "LR padrão para dataset adequado"

        # Patience baseado no tamanho
        if size_cat == "very_small":
            params['patience'] = 30
            self.reasoning['patience'] = "Alta patience para dataset pequeno (evitar early stopping prematuro)"
        elif size_cat == "small":
            params['patience'] = 20
            self.reasoning['patience'] = "Patience moderada"
        else:
            params['patience'] = 15
            self.reasoning['patience'] = "Patience padrão"

        # Dropout baseado no tamanho (regularização)
        if size_cat in ["very_small", "small"]:
            params['dropout'] = 0.4
            self.reasoning['dropout'] = "Dropout alto para prevenir overfitting em dataset pequeno"
        else:
            params['dropout'] = 0.2
            self.reasoning['dropout'] = "Dropout padrão"

        # Weight decay (L2 regularization)
        if size_cat in ["very_small", "small"]:
            params['weight_decay'] = 0.01
            self.reasoning['weight_decay'] = "Weight decay aumentado para regularização"
        else:
            params['weight_decay'] = 0.001
            self.reasoning['weight_decay'] = "Weight decay padrão"

        # Class weights se desbalanceado
        balance_cat = analysis['balance_category']
        if balance_cat in ["moderate", "poor"]:
            params['use_class_weights'] = True
            self.reasoning['use_class_weights'] = f"Dataset {balance_cat} balanceado: usar class weights"
        else:
            params['use_class_weights'] = False
            self.reasoning['use_class_weights'] = "Dataset bem balanceado: sem necessidade de weights"

        # Mixup alpha
        if size_cat in ["very_small", "small"]:
            params['mixup_alpha'] = 0.3
            self.reasoning['mixup_alpha'] = "Mixup para aumentar dados sintéticos"
        else:
            params['mixup_alpha'] = 0.2
            self.reasoning['mixup_alpha'] = "Mixup leve para regularização"

        return params

    def _select_regressor_params(self, analysis: Dict) -> Dict[str, Any]:
        """Seleciona hiperparâmetros para regressor de refinamento"""
        params = {}

        size_cat = analysis['dataset_size_category']

        # Epochs
        if size_cat == "very_small":
            params['epochs'] = 150
            self.reasoning['epochs'] = "Dataset pequeno: mais epochs"
        elif size_cat == "small":
            params['epochs'] = 120
            self.reasoning['epochs'] = "Dataset pequeno: epochs aumentados"
        else:
            params['epochs'] = 100
            self.reasoning['epochs'] = "Epochs padrão"

        # Batch size
        num_samples = analysis['num_samples']
        if num_samples < 50:
            params['batch_size'] = 8
            self.reasoning['batch_size'] = "Batch pequeno para dataset pequeno"
        elif num_samples < 200:
            params['batch_size'] = 16
            self.reasoning['batch_size'] = "Batch moderado"
        else:
            params['batch_size'] = 32
            self.reasoning['batch_size'] = "Batch padrão"

        # Learning rate
        if size_cat in ["very_small", "small"]:
            params['learning_rate'] = 0.0003
            self.reasoning['learning_rate'] = "LR reduzido para dataset pequeno"
        else:
            params['learning_rate'] = 0.0005
            self.reasoning['learning_rate'] = "LR padrão para regressão"

        # Patience
        params['patience'] = 20 if size_cat in ["very_small", "small"] else 15
        self.reasoning['patience'] = "Patience ajustada ao tamanho do dataset"

        # Dropout
        if size_cat in ["very_small", "small"]:
            params['dropout'] = 0.3
            self.reasoning['dropout'] = "Dropout aumentado para regularização"
        else:
            params['dropout'] = 0.15
            self.reasoning['dropout'] = "Dropout leve"

        # Weight decay
        params['weight_decay'] = 0.001
        self.reasoning['weight_decay'] = "Weight decay padrão para regressão"

        return params

    def _select_clip_params(self, analysis: Dict) -> Dict[str, Any]:
        """Seleciona hiperparâmetros para Transfer Learning com CLIP"""
        params = {}

        size_cat = analysis['dataset_size_category']
        has_presets = analysis['has_presets']

        # Modelo CLIP
        if size_cat in ["very_small", "small"]:
            params['model_name'] = "clip"  # ViT-B/32 - mais leve
            self.reasoning['model_name'] = "CLIP ViT-B/32: melhor para datasets pequenos"
        else:
            params['model_name'] = "clip"  # Pode usar ViT-L/14 se tiver recursos
            self.reasoning['model_name'] = "CLIP ViT-B/32: boa performance geral"

        # Epochs - CLIP converge mais rápido
        if size_cat == "very_small":
            params['epochs'] = 50
            self.reasoning['epochs'] = "Dataset muito pequeno: mais epochs para transfer learning"
        elif size_cat == "small":
            params['epochs'] = 40
            self.reasoning['epochs'] = "Dataset pequeno: epochs adequados"
        else:
            params['epochs'] = 30
            self.reasoning['epochs'] = "Transfer learning converge rápido em datasets maiores"

        # Batch size - CLIP precisa de memória
        num_samples = analysis['num_samples']
        if num_samples < 50:
            params['batch_size'] = 4
            self.reasoning['batch_size'] = "Batch pequeno para memória GPU limitada"
        elif num_samples < 100:
            params['batch_size'] = 8
            self.reasoning['batch_size'] = "Batch moderado"
        else:
            params['batch_size'] = 16
            self.reasoning['batch_size'] = "Batch adequado para CLIP"

        # Learning rate - Transfer learning precisa de LR menor
        params['learning_rate'] = 0.0001
        self.reasoning['learning_rate'] = "LR baixo para fine-tuning de modelo pré-treinado"

        # Freeze backbone
        if size_cat == "very_small":
            params['freeze_backbone'] = True
            self.reasoning['freeze_backbone'] = "Congelar backbone em dataset muito pequeno"
        else:
            params['freeze_backbone'] = False
            self.reasoning['freeze_backbone'] = "Fine-tuning completo em dataset adequado"

        # Patience
        params['patience'] = 10
        self.reasoning['patience'] = "Patience reduzida: transfer learning converge rápido"

        # Dropout
        if size_cat in ["very_small", "small"]:
            params['dropout'] = 0.4
            self.reasoning['dropout'] = "Dropout alto para prevenir overfitting"
        else:
            params['dropout'] = 0.2
            self.reasoning['dropout'] = "Dropout padrão"

        # Weight decay
        params['weight_decay'] = 0.001
        self.reasoning['weight_decay'] = "Weight decay padrão para transfer learning"

        # Modo (classificação vs regressão)
        if has_presets:
            params['mode'] = 'classification'
            self.reasoning['mode'] = "Dataset tem presets identificados: modo classificação"
        else:
            params['mode'] = 'regression'
            self.reasoning['mode'] = "Dataset sem presets: modo regressão direta"

        return params

    def _select_culling_params(self, analysis: Dict) -> Dict[str, Any]:
        """Seleciona hiperparâmetros para Smart Culling"""
        params = {}

        size_cat = analysis['dataset_size_category']
        has_ratings = analysis['has_ratings']

        if not has_ratings:
            raise ValueError("Dataset não tem ratings. Culling requer coluna 'rating'.")

        # Modelo
        params['model_name'] = "dinov2"
        self.reasoning['model_name'] = "DINOv2: melhor para avaliação estética"

        # Epochs
        if size_cat == "very_small":
            params['epochs'] = 60
            self.reasoning['epochs'] = "Dataset pequeno: mais epochs"
        elif size_cat == "small":
            params['epochs'] = 50
            self.reasoning['epochs'] = "Dataset pequeno: epochs aumentados"
        else:
            params['epochs'] = 40
            self.reasoning['epochs'] = "Epochs padrão para culling"

        # Batch size
        num_samples = analysis['num_samples']
        if num_samples < 100:
            params['batch_size'] = 4
            self.reasoning['batch_size'] = "Batch pequeno para dataset pequeno"
        elif num_samples < 300:
            params['batch_size'] = 8
            self.reasoning['batch_size'] = "Batch moderado"
        else:
            params['batch_size'] = 16
            self.reasoning['batch_size'] = "Batch adequado"

        # Learning rate
        params['learning_rate'] = 0.0001
        self.reasoning['learning_rate'] = "LR baixo para fine-tuning DINOv2"

        # Patience
        params['patience'] = 10
        self.reasoning['patience'] = "Patience padrão para transfer learning"

        # Dropout
        if size_cat in ["very_small", "small"]:
            params['dropout'] = 0.4
            self.reasoning['dropout'] = "Dropout alto para dataset pequeno"
        else:
            params['dropout'] = 0.3
            self.reasoning['dropout'] = "Dropout moderado"

        # Weight decay
        params['weight_decay'] = 0.001
        self.reasoning['weight_decay'] = "Weight decay padrão"

        return params

    def generate_report(self, model_type: str = "classifier") -> str:
        """
        Gera relatório detalhado da seleção de hiperparâmetros

        Args:
            model_type: Tipo de modelo

        Returns:
            String com relatório formatado
        """
        result = self.select_hyperparameters(model_type)

        params = result['hyperparameters']
        reasoning = result['reasoning']
        analysis = result['dataset_analysis']

        report_lines = []

        report_lines.append("=" * 80)
        report_lines.append("🎯 SELEÇÃO AUTOMÁTICA DE HIPERPARÂMETROS")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Análise do dataset
        report_lines.append("📊 ANÁLISE DO DATASET:")
        report_lines.append("-" * 80)
        report_lines.append(f"  Total de amostras: {analysis['num_samples']}")
        report_lines.append(f"  Categoria de tamanho: {analysis['dataset_size_category'].upper()}")

        if analysis['has_presets']:
            report_lines.append(f"  Número de classes: {analysis['num_classes']}")
            report_lines.append(f"  Balanceamento: {analysis['balance_category'].upper()} (ratio: {analysis['imbalance_ratio']:.2f})")

        if analysis['has_ratings']:
            report_lines.append(f"  Ratings disponíveis: SIM")

        report_lines.append(f"  Features: {analysis['num_features']}")
        report_lines.append(f"  Missing values: {analysis['missing_percentage']:.2f}%")
        report_lines.append("")

        # Hiperparâmetros recomendados
        report_lines.append("⚙️ HIPERPARÂMETROS RECOMENDADOS:")
        report_lines.append("-" * 80)

        for param_name, param_value in params.items():
            reason = reasoning.get(param_name, "N/A")
            report_lines.append(f"  {param_name}: {param_value}")
            report_lines.append(f"    ↳ {reason}")
            report_lines.append("")

        report_lines.append("=" * 80)
        report_lines.append("💡 Use estes valores na UI ou passe via argumentos de linha de comando")
        report_lines.append("=" * 80)

        return "\n".join(report_lines)


def main():
    """Função de teste"""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python auto_hyperparameter_selector.py <dataset.csv> [model_type]")
        print("model_type: classifier, regressor, clip, culling")
        sys.exit(1)

    dataset_path = sys.argv[1]
    model_type = sys.argv[2] if len(sys.argv) > 2 else "classifier"

    selector = AutoHyperparameterSelector(dataset_path)
    print(selector.generate_report(model_type))


if __name__ == "__main__":
    main()
