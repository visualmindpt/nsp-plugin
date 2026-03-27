"""
Automatic Feature Selection
Seleção automática de features mais relevantes para treino

Features:
- SelectKBest com múltiplas scoring functions
- RFE (Recursive Feature Elimination)
- Análise de importância de features
- Seleção automática do número ótimo de features
- Visualizações e reports

Ganhos:
- Remove features redundantes ou não informativas
- Reduz overfitting
- Acelera treino
- Melhora generalização

Data: 21 Novembro 2025
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import matplotlib.pyplot as plt
from sklearn.feature_selection import (
    SelectKBest,
    f_classif,
    f_regression,
    mutual_info_classif,
    mutual_info_regression,
    RFE
)
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class FeatureSelector:
    """
    Seletor automático de features

    Métodos disponíveis:
    - SelectKBest: Seleção univariada baseada em scores estatísticos
    - RFE: Eliminação recursiva de features
    - Feature Importance: Baseado em Random Forest
    - Correlation Analysis: Remove features altamente correlacionadas
    """

    def __init__(self, method: str = "auto", task: str = "classification"):
        """
        Args:
            method: Método de seleção ('selectkbest', 'rfe', 'importance', 'correlation', 'auto')
            task: Tipo de tarefa ('classification' ou 'regression')
        """
        self.method = method
        self.task = task
        self.selected_features = None
        self.feature_scores = None
        self.feature_rankings = None

        logger.info(f"FeatureSelector inicializado: method={method}, task={task}")

    def select_k_best(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        k: int = 50,
        score_func: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        SelectKBest: Seleciona as k melhores features baseado em scores univariados

        Args:
            X: Features (DataFrame)
            y: Target
            k: Número de features a selecionar
            score_func: Função de scoring ('f_test', 'mutual_info', None=auto)

        Returns:
            Tupla de (X_selected, feature_scores)
        """
        logger.info(f"SelectKBest: Selecionando top {k} features de {X.shape[1]}")

        # Escolher scoring function
        if score_func is None:
            score_func = "f_test"  # Default

        if self.task == "classification":
            if score_func == "f_test":
                scorer = f_classif
            elif score_func == "mutual_info":
                scorer = mutual_info_classif
            else:
                scorer = f_classif
        else:  # regression
            if score_func == "f_test":
                scorer = f_regression
            elif score_func == "mutual_info":
                scorer = mutual_info_regression
            else:
                scorer = f_regression

        # Ajustar k ao número de features disponíveis
        k = min(k, X.shape[1])

        # Aplicar SelectKBest
        selector = SelectKBest(score_func=scorer, k=k)
        X_selected = selector.fit_transform(X, y)

        # Obter scores
        scores = selector.scores_
        feature_names = X.columns.tolist()

        # Criar dict de scores
        self.feature_scores = {
            feature_names[i]: float(scores[i]) if not np.isnan(scores[i]) else 0.0
            for i in range(len(feature_names))
        }

        # Features selecionadas
        selected_mask = selector.get_support()
        self.selected_features = [feature_names[i] for i, selected in enumerate(selected_mask) if selected]

        # Retornar DataFrame com features selecionadas
        X_selected_df = pd.DataFrame(X_selected, columns=self.selected_features)

        logger.info(f"SelectKBest: {len(self.selected_features)} features selecionadas")
        return X_selected_df, self.feature_scores

    def recursive_feature_elimination(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        n_features: int = 50,
        step: int = 5
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        RFE: Eliminação recursiva de features

        Args:
            X: Features
            y: Target
            n_features: Número de features a manter
            step: Número de features a remover em cada iteração

        Returns:
            Tupla de (X_selected, feature_rankings)
        """
        logger.info(f"RFE: Eliminando recursivamente até {n_features} features")

        # Ajustar n_features
        n_features = min(n_features, X.shape[1])

        # Criar estimador
        if self.task == "classification":
            estimator = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        else:
            estimator = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)

        # Aplicar RFE
        rfe = RFE(estimator=estimator, n_features_to_select=n_features, step=step)
        X_selected = rfe.fit_transform(X, y)

        # Obter rankings
        rankings = rfe.ranking_
        feature_names = X.columns.tolist()

        # Criar dict de rankings (1 = melhor)
        self.feature_rankings = {
            feature_names[i]: int(rankings[i])
            for i in range(len(feature_names))
        }

        # Features selecionadas (ranking = 1)
        selected_mask = rfe.support_
        self.selected_features = [feature_names[i] for i, selected in enumerate(selected_mask) if selected]

        # Retornar DataFrame
        X_selected_df = pd.DataFrame(X_selected, columns=self.selected_features)

        logger.info(f"RFE: {len(self.selected_features)} features selecionadas")
        return X_selected_df, self.feature_rankings

    def feature_importance_selection(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        threshold: float = 0.01,
        n_estimators: int = 100
    ) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Seleção baseada em importância de features (Random Forest)

        Args:
            X: Features
            y: Target
            threshold: Importância mínima (0-1)
            n_estimators: Número de árvores

        Returns:
            Tupla de (X_selected, feature_importances)
        """
        logger.info(f"Feature Importance: threshold={threshold}")

        # Treinar Random Forest
        if self.task == "classification":
            rf = RandomForestClassifier(n_estimators=n_estimators, random_state=42, n_jobs=-1)
        else:
            rf = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1)

        rf.fit(X, y)

        # Obter importâncias
        importances = rf.feature_importances_
        feature_names = X.columns.tolist()

        # Criar dict
        self.feature_scores = {
            feature_names[i]: float(importances[i])
            for i in range(len(feature_names))
        }

        # Selecionar features acima do threshold
        self.selected_features = [
            feature_names[i]
            for i in range(len(feature_names))
            if importances[i] >= threshold
        ]

        # Se muito poucas features, selecionar pelo menos as top 20
        if len(self.selected_features) < 20:
            sorted_features = sorted(
                self.feature_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            self.selected_features = [f[0] for f in sorted_features[:min(20, len(sorted_features))]]

        # Retornar DataFrame
        X_selected_df = X[self.selected_features]

        logger.info(f"Feature Importance: {len(self.selected_features)} features selecionadas")
        return X_selected_df, self.feature_scores

    def correlation_selection(
        self,
        X: pd.DataFrame,
        threshold: float = 0.95
    ) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Remove features altamente correlacionadas

        Args:
            X: Features
            threshold: Correlação máxima (0-1)

        Returns:
            Tupla de (X_selected, correlation_info)
        """
        logger.info(f"Correlation Selection: threshold={threshold}")

        # Calcular matriz de correlação
        corr_matrix = X.corr().abs()

        # Identificar pares de features com correlação > threshold
        upper_triangle = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )

        # Features a remover (uma de cada par)
        to_drop = [
            column for column in upper_triangle.columns
            if any(upper_triangle[column] > threshold)
        ]

        # Features a manter
        self.selected_features = [col for col in X.columns if col not in to_drop]

        # Info de correlação
        correlation_info = {
            "dropped_features": to_drop,
            "kept_features": self.selected_features,
            "num_dropped": len(to_drop),
            "num_kept": len(self.selected_features)
        }

        # Retornar DataFrame
        X_selected_df = X[self.selected_features]

        logger.info(f"Correlation Selection: Removidas {len(to_drop)} features correlacionadas")
        return X_selected_df, correlation_info

    def auto_select(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        target_features: Optional[int] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Seleção automática: combina múltiplos métodos

        Pipeline:
        1. Remove features altamente correlacionadas (>0.95)
        2. SelectKBest para reduzir a ~100 features
        3. RFE para chegar ao número target

        Args:
            X: Features
            y: Target
            target_features: Número alvo de features (None=auto)

        Returns:
            Tupla de (X_selected, selection_info)
        """
        logger.info("Auto Select: Iniciando pipeline de seleção automática")

        # Determinar target_features se não especificado
        if target_features is None:
            # Heurística: sqrt(num_features) limitado entre 30-100
            target_features = min(100, max(30, int(np.sqrt(X.shape[1]))))

        logger.info(f"Target features: {target_features}")

        selection_info = {
            "original_features": X.shape[1],
            "target_features": target_features,
            "steps": []
        }

        # Step 1: Remover correlações altas
        X_step1, corr_info = self.correlation_selection(X, threshold=0.95)
        selection_info["steps"].append({
            "step": 1,
            "method": "correlation",
            "features_before": X.shape[1],
            "features_after": X_step1.shape[1],
            "removed": corr_info["num_dropped"]
        })

        # Step 2: SelectKBest (se ainda houver muitas features)
        if X_step1.shape[1] > target_features * 2:
            k_best = min(target_features * 2, X_step1.shape[1])
            X_step2, scores = self.select_k_best(X_step1, y, k=k_best)
            selection_info["steps"].append({
                "step": 2,
                "method": "selectkbest",
                "features_before": X_step1.shape[1],
                "features_after": X_step2.shape[1],
                "k": k_best
            })
        else:
            X_step2 = X_step1

        # Step 3: RFE para número final
        if X_step2.shape[1] > target_features:
            X_final, rankings = self.recursive_feature_elimination(
                X_step2, y, n_features=target_features
            )
            selection_info["steps"].append({
                "step": 3,
                "method": "rfe",
                "features_before": X_step2.shape[1],
                "features_after": X_final.shape[1],
                "n_features": target_features
            })
        else:
            X_final = X_step2
            self.selected_features = X_step2.columns.tolist()

        selection_info["final_features"] = len(self.selected_features)
        selection_info["selected_features"] = self.selected_features
        selection_info["reduction_ratio"] = len(self.selected_features) / X.shape[1]

        logger.info(f"Auto Select: {X.shape[1]} → {len(self.selected_features)} features")
        logger.info(f"Redução: {(1 - selection_info['reduction_ratio']) * 100:.1f}%")

        return X_final, selection_info

    def plot_feature_scores(
        self,
        output_path: Optional[Path] = None,
        top_n: int = 30
    ) -> Optional[plt.Figure]:
        """
        Plota scores de features

        Args:
            output_path: Caminho para salvar (None=mostra)
            top_n: Número de features a mostrar

        Returns:
            Figure do matplotlib
        """
        if self.feature_scores is None:
            logger.warning("Nenhum score de feature disponível")
            return None

        # Ordenar por score
        sorted_features = sorted(
            self.feature_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        features = [f[0] for f in sorted_features]
        scores = [f[1] for f in sorted_features]

        # Criar plot
        fig, ax = plt.subplots(figsize=(12, 8))
        y_pos = np.arange(len(features))

        ax.barh(y_pos, scores, align='center')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(features, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel('Score', fontsize=12)
        ax.set_title(f'Top {top_n} Feature Scores', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)

        plt.tight_layout()

        if output_path:
            fig.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"Plot salvo em {output_path}")

        return fig

    def get_selection_report(self) -> Dict[str, Any]:
        """
        Retorna report de seleção

        Returns:
            Dict com informações da seleção
        """
        if self.selected_features is None:
            return {"status": "No selection performed"}

        report = {
            "method": self.method,
            "task": self.task,
            "num_selected": len(self.selected_features),
            "selected_features": self.selected_features,
        }

        if self.feature_scores is not None:
            report["feature_scores"] = self.feature_scores
            # Top 10 features
            sorted_features = sorted(
                self.feature_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            report["top_10_features"] = [f[0] for f in sorted_features]

        if self.feature_rankings is not None:
            report["feature_rankings"] = self.feature_rankings

        return report


def select_features_for_training(
    features_df: pd.DataFrame,
    labels: np.ndarray,
    method: str = "auto",
    task: str = "classification",
    target_features: Optional[int] = None,
    output_dir: Optional[Path] = None
) -> Tuple[pd.DataFrame, List[str], Dict[str, Any]]:
    """
    Helper function para seleção de features no pipeline de treino

    Args:
        features_df: DataFrame com features
        labels: Array com labels
        method: Método de seleção
        task: Tipo de tarefa
        target_features: Número alvo de features
        output_dir: Diretório para salvar reports

    Returns:
        Tupla de (features_selected, feature_names, selection_report)
    """
    selector = FeatureSelector(method=method, task=task)

    # Executar seleção baseado no método
    if method == "auto":
        X_selected, info = selector.auto_select(features_df, labels, target_features)
    elif method == "selectkbest":
        k = target_features or min(50, features_df.shape[1])
        X_selected, info = selector.select_k_best(features_df, labels, k=k)
    elif method == "rfe":
        n_features = target_features or min(50, features_df.shape[1])
        X_selected, info = selector.recursive_feature_elimination(features_df, labels, n_features=n_features)
    elif method == "importance":
        X_selected, info = selector.feature_importance_selection(features_df, labels)
    elif method == "correlation":
        X_selected, info = selector.correlation_selection(features_df)
    else:
        raise ValueError(f"Método desconhecido: {method}")

    # Gerar report
    report = selector.get_selection_report()
    report["method_info"] = info

    # Salvar plot se output_dir especificado
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Plot de scores
        if selector.feature_scores:
            plot_path = output_dir / "feature_scores.png"
            selector.plot_feature_scores(output_path=plot_path, top_n=30)

        # Report JSON
        import json
        report_path = output_dir / "feature_selection_report.json"
        with open(report_path, 'w') as f:
            # Converter numpy types para tipos nativos
            json_report = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in report.items()}
            json.dump(json_report, f, indent=2)
        logger.info(f"Report salvo em {report_path}")

    return X_selected, selector.selected_features, report


if __name__ == "__main__":
    # Teste do feature selector
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("FEATURE SELECTOR - Teste")
    print("=" * 60)

    # Criar dataset sintético
    from sklearn.datasets import make_classification

    X, y = make_classification(
        n_samples=1000,
        n_features=100,
        n_informative=20,
        n_redundant=30,
        n_repeated=10,
        random_state=42
    )

    feature_names = [f"feature_{i}" for i in range(X.shape[1])]
    X_df = pd.DataFrame(X, columns=feature_names)

    print(f"\nDataset: {X_df.shape[0]} samples, {X_df.shape[1]} features")

    # Teste 1: Auto Select
    print("\n1. Auto Select...")
    selector = FeatureSelector(method="auto", task="classification")
    X_selected, info = selector.auto_select(X_df, y, target_features=30)

    print(f"   Features selecionadas: {X_selected.shape[1]}")
    print(f"   Redução: {(1 - info['reduction_ratio']) * 100:.1f}%")
    print(f"   Steps: {len(info['steps'])}")

    # Teste 2: Report
    print("\n2. Report:")
    report = selector.get_selection_report()
    print(f"   Top 10 features: {report.get('top_10_features', [])[:5]}...")

    print("\n✅ Teste completo!")
