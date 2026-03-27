"""
Sistema de estatísticas para análise de dataset.

Fornece métricas detalhadas sobre:
- Tamanho do dataset
- Distribuição de presets
- Estatísticas de feedback
- Completude dos dados
- Diversidade das imagens
- Balanceamento de classes
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)


class DatasetStatistics:
    """
    Calcula e armazena estatísticas detalhadas do dataset.

    Útil para entender a qualidade dos dados e identificar problemas
    antes do treino.
    """

    def __init__(self, dataset_path: Optional[Path] = None):
        """
        Inicializa o sistema de estatísticas.

        Args:
            dataset_path: Caminho para o ficheiro CSV do dataset
        """
        self.dataset_path = dataset_path
        self.dataset: Optional[pd.DataFrame] = None
        self.stats: Dict[str, Any] = {}

        if dataset_path and Path(dataset_path).exists():
            self.dataset = pd.read_csv(dataset_path)

    def compute_stats(self) -> Dict[str, Any]:
        """
        Calcula todas as estatísticas do dataset.

        Returns:
            Dicionário com todas as estatísticas
        """
        if self.dataset is None:
            logger.error("Dataset não carregado. Impossível calcular estatísticas.")
            return {}

        self.stats = {
            'dataset_size': self._compute_dataset_size(),
            'presets': self._count_presets(),
            'feedback': self._get_feedback_stats(),
            'completeness': self._compute_completeness(),
            'diversity': self._compute_diversity(),
            'balance': self._compute_balance()
        }

        return self.stats

    def _compute_dataset_size(self) -> Dict[str, int]:
        """Calcula o tamanho do dataset."""
        return {
            'total_images': len(self.dataset),
            'total_features': len(self.dataset.columns),
            'missing_values': int(self.dataset.isna().sum().sum())
        }

    def _count_presets(self) -> Dict[str, Any]:
        """
        Conta a distribuição de presets.

        Returns:
            Dicionário com contagem e percentagens por preset
        """
        if 'preset_cluster' not in self.dataset.columns:
            return {'available': False}

        preset_counts = self.dataset['preset_cluster'].value_counts().to_dict()
        total = len(self.dataset)

        preset_percentages = {
            str(k): {
                'count': int(v),
                'percentage': round(v / total * 100, 2)
            }
            for k, v in preset_counts.items()
        }

        return {
            'available': True,
            'num_presets': len(preset_counts),
            'distribution': preset_percentages,
            'min_samples': int(min(preset_counts.values())),
            'max_samples': int(max(preset_counts.values())),
            'avg_samples': round(np.mean(list(preset_counts.values())), 2)
        }

    def _get_feedback_stats(self) -> Dict[str, Any]:
        """
        Estatísticas de feedback de usuários (se disponível).

        Returns:
            Estatísticas de feedback
        """
        feedback_cols = [col for col in self.dataset.columns if 'feedback' in col.lower()]

        if not feedback_cols:
            return {'available': False}

        stats = {
            'available': True,
            'feedback_columns': feedback_cols,
            'total_feedback_entries': 0
        }

        for col in feedback_cols:
            non_null = self.dataset[col].notna().sum()
            stats[col] = {
                'entries': int(non_null),
                'percentage': round(non_null / len(self.dataset) * 100, 2)
            }
            stats['total_feedback_entries'] += int(non_null)

        return stats

    def _compute_completeness(self) -> Dict[str, Any]:
        """
        Analisa a completude do dataset.

        Returns:
            Métricas de completude
        """
        total_cells = self.dataset.shape[0] * self.dataset.shape[1]
        missing_cells = self.dataset.isna().sum().sum()
        completeness_ratio = (total_cells - missing_cells) / total_cells

        # Identificar colunas com muitos missing values
        missing_by_col = self.dataset.isna().sum()
        problematic_cols = missing_by_col[missing_by_col > len(self.dataset) * 0.1].to_dict()

        return {
            'completeness_ratio': round(completeness_ratio, 4),
            'completeness_percentage': round(completeness_ratio * 100, 2),
            'total_cells': int(total_cells),
            'missing_cells': int(missing_cells),
            'problematic_columns': {k: int(v) for k, v in problematic_cols.items()}
        }

    def _compute_diversity(self) -> Dict[str, Any]:
        """
        Analisa a diversidade das imagens baseado em features estatísticas.

        Returns:
            Métricas de diversidade
        """
        # Identificar colunas de features estatísticas (excluir metadata)
        exclude_cols = ['image_path', 'preset_cluster', 'rating']
        stat_cols = [col for col in self.dataset.columns
                     if col not in exclude_cols and not col.startswith('delta_')]

        if not stat_cols:
            return {'available': False}

        # Selecionar apenas colunas numéricas
        numeric_data = self.dataset[stat_cols].select_dtypes(include=[np.number])

        if numeric_data.empty:
            return {'available': False}

        # Calcular variância média (indicador de diversidade)
        variances = numeric_data.var()
        avg_variance = variances.mean()

        # Calcular coeficiente de variação médio
        means = numeric_data.mean()
        cv = (numeric_data.std() / means.replace(0, np.nan)).mean()

        # Features com baixa variância (possível problema)
        low_variance_threshold = 0.01
        low_variance_features = variances[variances < low_variance_threshold].to_dict()

        return {
            'available': True,
            'avg_variance': round(avg_variance, 4),
            'coefficient_of_variation': round(cv, 4),
            'num_features_analyzed': len(numeric_data.columns),
            'low_variance_features': {k: round(v, 6) for k, v in low_variance_features.items()},
            'diversity_score': self._calculate_diversity_score(numeric_data)
        }

    def _calculate_diversity_score(self, data: pd.DataFrame) -> float:
        """
        Calcula um score de diversidade (0-1).

        Args:
            data: DataFrame com features numéricas

        Returns:
            Score de diversidade (0 = baixa, 1 = alta)
        """
        # Normalizar dados
        normalized = (data - data.min()) / (data.max() - data.min() + 1e-8)

        # Calcular distância euclidiana média entre amostras
        from scipy.spatial.distance import pdist

        # Limitar a 1000 amostras para performance
        sample_data = normalized.sample(min(1000, len(normalized)))

        distances = pdist(sample_data.values)
        avg_distance = np.mean(distances)

        # Normalizar para 0-1 (assumindo max teórico de sqrt(num_features))
        max_theoretical_distance = np.sqrt(len(data.columns))
        diversity_score = min(avg_distance / max_theoretical_distance, 1.0)

        return round(diversity_score, 4)

    def _compute_balance(self) -> Dict[str, Any]:
        """
        Analisa o balanceamento de classes/presets.

        Returns:
            Métricas de balanceamento
        """
        if 'preset_cluster' not in self.dataset.columns:
            return {'available': False}

        preset_counts = self.dataset['preset_cluster'].value_counts()

        if len(preset_counts) == 0:
            return {'available': False}

        # Calcular imbalance ratio
        max_count = preset_counts.max()
        min_count = preset_counts.min()
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

        # Calcular Gini coefficient (0 = perfeitamente balanceado, 1 = totalmente desbalanceado)
        sorted_counts = np.sort(preset_counts.values)
        n = len(sorted_counts)
        index = np.arange(1, n + 1)
        gini = (2 * np.sum(index * sorted_counts)) / (n * np.sum(sorted_counts)) - (n + 1) / n

        # Classificação do balanceamento
        if imbalance_ratio < 1.5:
            balance_level = "Excelente"
        elif imbalance_ratio < 3.0:
            balance_level = "Bom"
        elif imbalance_ratio < 5.0:
            balance_level = "Moderado"
        else:
            balance_level = "Desbalanceado"

        return {
            'available': True,
            'imbalance_ratio': round(imbalance_ratio, 2),
            'gini_coefficient': round(gini, 4),
            'balance_level': balance_level,
            'max_class_size': int(max_count),
            'min_class_size': int(min_count),
            'recommendation': self._get_balance_recommendation(imbalance_ratio)
        }

    def _get_balance_recommendation(self, imbalance_ratio: float) -> str:
        """
        Retorna recomendação baseada no imbalance ratio.

        Args:
            imbalance_ratio: Rácio de desbalanceamento

        Returns:
            Recomendação textual
        """
        if imbalance_ratio < 1.5:
            return "Dataset bem balanceado. Nenhuma ação necessária."
        elif imbalance_ratio < 3.0:
            return "Balanceamento aceitável. Considere usar class weights no treino."
        elif imbalance_ratio < 5.0:
            return "Desbalanceamento moderado. Recomenda-se usar class weights e data augmentation."
        else:
            return "Desbalanceamento significativo. Use class weights, data augmentation e considere SMOTE."

    def generate_report(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Gera relatório completo em JSON.

        Args:
            output_path: Caminho para guardar o relatório JSON (opcional)

        Returns:
            Dicionário com relatório completo
        """
        if not self.stats:
            self.compute_stats()

        report = {
            'dataset_path': str(self.dataset_path) if self.dataset_path else None,
            'statistics': self.stats,
            'warnings': self._generate_warnings(),
            'recommendations': self._generate_recommendations()
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Relatório guardado em {output_path}")

        return report

    def _generate_warnings(self) -> List[str]:
        """Gera lista de warnings baseado nas estatísticas."""
        warnings = []

        # Warning sobre tamanho do dataset
        size = self.stats.get('dataset_size', {}).get('total_images', 0)
        if size < 100:
            warnings.append(f"Dataset muito pequeno ({size} imagens). Risco alto de overfitting.")
        elif size < 500:
            warnings.append(f"Dataset pequeno ({size} imagens). Use data augmentation agressivo.")

        # Warning sobre balanceamento
        balance = self.stats.get('balance', {})
        if balance.get('available') and balance.get('imbalance_ratio', 1) > 3:
            warnings.append(f"Classes desbalanceadas (ratio: {balance['imbalance_ratio']}).")

        # Warning sobre completude
        completeness = self.stats.get('completeness', {})
        if completeness.get('completeness_percentage', 100) < 90:
            warnings.append(f"Dataset incompleto ({completeness['completeness_percentage']:.1f}% completo).")

        # Warning sobre diversidade
        diversity = self.stats.get('diversity', {})
        if diversity.get('available') and diversity.get('diversity_score', 1) < 0.3:
            warnings.append("Baixa diversidade no dataset. Imagens muito similares.")

        return warnings

    def _generate_recommendations(self) -> List[str]:
        """Gera lista de recomendações baseado nas estatísticas."""
        recommendations = []

        size = self.stats.get('dataset_size', {}).get('total_images', 0)

        if size < 500:
            recommendations.append("Use data augmentation agressivo (noise, mixup, dropout)")
            recommendations.append("Use regularização forte (dropout 0.4-0.5, weight decay)")
            recommendations.append("Reduza complexidade dos modelos")
            recommendations.append("Use OneCycleLR para melhor convergência")

        balance = self.stats.get('balance', {})
        if balance.get('available') and balance.get('imbalance_ratio', 1) > 2:
            recommendations.append("Use class weights no loss function")
            recommendations.append("Considere oversampling das classes minoritárias")

        diversity = self.stats.get('diversity', {})
        if diversity.get('available') and diversity.get('diversity_score', 1) < 0.4:
            recommendations.append("Adicione imagens mais diversas ao dataset")
            recommendations.append("Considere diferentes cenários de iluminação e composição")

        return recommendations

    def print_summary(self) -> None:
        """Imprime um resumo das estatísticas no terminal."""
        if not self.stats:
            self.compute_stats()

        print("\n" + "=" * 70)
        print("ANÁLISE DO DATASET")
        print("=" * 70)

        # Tamanho
        size = self.stats.get('dataset_size', {})
        print(f"\nTamanho:")
        print(f"  Total de imagens: {size.get('total_images', 0)}")
        print(f"  Total de features: {size.get('total_features', 0)}")
        print(f"  Valores faltantes: {size.get('missing_values', 0)}")

        # Presets
        presets = self.stats.get('presets', {})
        if presets.get('available'):
            print(f"\nPresets:")
            print(f"  Número de presets: {presets.get('num_presets', 0)}")
            print(f"  Min amostras por preset: {presets.get('min_samples', 0)}")
            print(f"  Max amostras por preset: {presets.get('max_samples', 0)}")
            print(f"  Média amostras por preset: {presets.get('avg_samples', 0)}")

        # Balanceamento
        balance = self.stats.get('balance', {})
        if balance.get('available'):
            print(f"\nBalanceamento:")
            print(f"  Nível: {balance.get('balance_level', 'N/A')}")
            print(f"  Imbalance ratio: {balance.get('imbalance_ratio', 0)}")
            print(f"  Recomendação: {balance.get('recommendation', 'N/A')}")

        # Diversidade
        diversity = self.stats.get('diversity', {})
        if diversity.get('available'):
            print(f"\nDiversidade:")
            print(f"  Score: {diversity.get('diversity_score', 0)}")
            print(f"  Features analisadas: {diversity.get('num_features_analyzed', 0)}")

        # Completude
        completeness = self.stats.get('completeness', {})
        print(f"\nCompletude:")
        print(f"  Percentagem completa: {completeness.get('completeness_percentage', 0):.2f}%")

        # Warnings
        warnings = self._generate_warnings()
        if warnings:
            print(f"\nAVISOS ({len(warnings)}):")
            for warning in warnings:
                print(f"  - {warning}")

        # Recomendações
        recommendations = self._generate_recommendations()
        if recommendations:
            print(f"\nRECOMENDAÇÕES ({len(recommendations)}):")
            for rec in recommendations:
                print(f"  - {rec}")

        print("\n" + "=" * 70)
