# -*- coding: utf-8 -*-
"""
NSP Plugin V2 - Pipeline de Treino Otimizado

Interface Gradio para treino de modelos ML para o plugin Lightroom.
Versão otimizada com melhor logging, estatísticas de dataset e suporte para modelos V2.

Autor: NSP Plugin Team
Versão: 2.0
"""

import os
import re
import json
import joblib
import shutil
import subprocess
import sys
import threading
import logging
import queue
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr
import plotly.graph_objects as go
from slider_config import ALL_SLIDERS, ALL_SLIDER_NAMES

# Import das estatísticas de dataset
from services.dataset_stats import DatasetStatistics
from services.dataset_quality_analyzer import DatasetQualityAnalyzer
from services.auto_hyperparameter_selector import AutoHyperparameterSelector

# Import das funções de treino (V2 otimizado)
from train.train_models_v2 import (
    set_training_configs,
    extract_lightroom_data,
    identify_presets_and_deltas,
    extract_image_features,
    prepare_training_data,
    train_preset_classifier,
    train_refinement_regressor,
    run_full_training_pipeline,
    MODELS_DIR,
    OUTPUT_DATASET_PATH,
    OUTPUT_FEATURES_PATH,
    OUTPUT_DEEP_FEATURES_PATH,
    PARAM_IMPORTANCE as _PARAM_IMPORTANCE,
)

# Import dos scripts de Transfer Learning e Culling
try:
    from train import train_with_clip
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    logging.warning("CLIP não disponível. Instale dependências: pip install transformers torch torchvision")

try:
    from train import train_culling_dinov2
    CULLING_AVAILABLE = True
except ImportError:
    CULLING_AVAILABLE = False
    logging.warning("Culling não disponível. Instale dependências: pip install torch torchvision")

# --- Configuração ---
# PROJECT_ROOT already defined above when adding to sys.path
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Regex para parsing de MAE do output
SLIDER_MAE_RE = re.compile(r"^\s+([a-zA-Z_]+):\s+MAE\s+=\s+([0-9]+\.[0-9]+)$")

CATALOG_BUTTONS = []
slider_mae_values = {}

# --- Helpers ---
def create_log_file(prefix):
    """Cria ficheiro de log com timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return LOG_DIR / f"{prefix}_{timestamp}.log"


def append_log_line(log_path, text):
    """Adiciona linha ao ficheiro de log."""
    if not log_path:
        return
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text + ("\n" if not text.endswith("\n") else ""))


def save_scalers_local(scaler_stat, scaler_deep, scaler_deltas):
    """Guarda scalers no diretório de modelos V2 (mesmo formato do servidor)."""
    joblib.dump(scaler_stat, MODELS_DIR / 'scaler_stat.pkl')
    joblib.dump(scaler_deep, MODELS_DIR / 'scaler_deep.pkl')
    joblib.dump(scaler_deltas, MODELS_DIR / 'scaler_deltas.pkl')


def format_log_with_timestamp(message):
    """Adiciona timestamp a cada linha de log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"


def stream_logs_from_function(func, collector, log_path, logger_name=None, level=logging.INFO):
    """
    Executa func em background e emite logs em tempo real para o UI collector.
    Versão melhorada com timestamps e melhor formatação.
    """
    log_queue = queue.Queue()
    result_holder = {"value": None, "error": None}

    class QueueLogHandler(logging.Handler):
        def __init__(self, q):
            super().__init__()
            self.q = q

        def emit(self, record):
            try:
                msg = self.format(record)
                self.q.put_nowait(msg)
            except Exception:
                pass

    handler = QueueLogHandler(log_queue)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    target_logger = logging.getLogger() if logger_name is None else logging.getLogger(logger_name)
    target_logger.addHandler(handler)

    def worker():
        try:
            result_holder["value"] = func()
        except Exception as exc:
            result_holder["error"] = exc
        finally:
            log_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()

    try:
        while True:
            message = log_queue.get()
            if message is None:
                break
            collector.append(message)
            append_log_line(log_path, message)
            yield "\n".join(collector)
    finally:
        target_logger.removeHandler(handler)

    if result_holder["error"]:
        raise result_holder["error"]
    return result_holder["value"]


# Recomendações rápidas para auto-preencher hiperparâmetros
def apply_recommendation(kind: str):
    if kind == "aug":
        return (
            gr.update(value=0.12),  # noise agressivo
            gr.update(value=0.45),  # dropout
            gr.update(value=0.6),   # mixup
            gr.update(), gr.update(), gr.update()
        )
    if kind == "reg":
        return (
            gr.update(),           # noise
            gr.update(value=0.45), # dropout forte
            gr.update(value=0.5),  # mixup moderado
            gr.update(value=0.05), # wd clf
            gr.update(value=0.05), # wd ref
            gr.update()
        )
    if kind == "simple":
        return (
            gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(),
            gr.update(value=0.75)  # modelo mais compacto
        )
    if kind == "onecycle":
        return (gr.update(),) * 6
    return (gr.update(),) * 6


def _catalog_from_file(file_path):
    """Extrai caminho do catálogo do ficheiro carregado."""
    return file_path or ""


def _has_catalog_path(manual_path, uploaded_path):
    """Verifica se existe um caminho de catálogo válido."""
    if manual_path and manual_path.strip():
        return True
    return bool(uploaded_path)


def _catalog_button_updates(manual_path, uploaded_path):
    """Atualiza o estado interativo dos botões baseado na existência do catálogo."""
    has_catalog = _has_catalog_path(manual_path, uploaded_path)
    return [gr.update(interactive=has_catalog) for _ in CATALOG_BUTTONS]


def parse_mae_summary(lines, model_label):
    """
    Parse do output de treino para extrair valores MAE.

    Args:
        lines: Lista de linhas de log
        model_label: Label do modelo (e.g., "Refinador V2")

    Returns:
        Tupla (rows, overall_value) para a tabela de summary
    """
    rows = []

    global slider_mae_values
    current_mae_results = {}

    for line in lines:
        mae_match = SLIDER_MAE_RE.search(line)
        if mae_match:
            slider_name = mae_match.group(1)
            mae_value = float(mae_match.group(2))
            rows.append([model_label, slider_name, mae_value])
            current_mae_results[slider_name] = mae_value

    slider_mae_values.update(current_mae_results)

    overall_value = None
    if current_mae_results:
        overall_mae_val = sum(current_mae_results.values()) / len(current_mae_results)
        overall_value = f"{model_label} Overall MAE: {overall_mae_val:.3f}"

    if rows:
        return rows, overall_value
    return None, None


# --- Estatísticas do Dataset ---
def compute_dataset_statistics(catalog_path):
    """
    Calcula estatísticas do dataset.

    Args:
        catalog_path: Caminho para o catálogo Lightroom ou dataset CSV

    Returns:
        Tupla (summary_text, plot, json_report)
    """
    try:
        # Verificar se já existe dataset processado
        dataset_path = OUTPUT_DATASET_PATH

        if not dataset_path.exists():
            return (
                "⚠️ Dataset ainda não foi extraído. Execute primeiro a extração do catálogo.",
                None,
                "{}"
            )

        # Criar instância de estatísticas
        stats = DatasetStatistics(dataset_path)
        report = stats.compute_stats()

        # Gerar texto de resumo
        summary_lines = []
        summary_lines.append("📊 ESTATÍSTICAS DO DATASET\n")
        summary_lines.append("=" * 60 + "\n")

        # Tamanho
        size = report.get('dataset_size', {})
        summary_lines.append(f"📸 Total de Imagens: {size.get('total_images', 0)}")
        summary_lines.append(f"📋 Total de Features: {size.get('total_features', 0)}")
        summary_lines.append(f"❌ Valores Faltantes: {size.get('missing_values', 0)}\n")

        # Presets
        presets = report.get('presets', {})
        if presets.get('available'):
            summary_lines.append(f"🎨 Número de Presets: {presets.get('num_presets', 0)}")
            summary_lines.append(f"   Min/Max/Média amostras: {presets.get('min_samples', 0)}/{presets.get('max_samples', 0)}/{presets.get('avg_samples', 0):.1f}\n")

        # Balanceamento
        balance = report.get('balance', {})
        if balance.get('available'):
            summary_lines.append(f"⚖️ Balanceamento: {balance.get('balance_level', 'N/A')}")
            summary_lines.append(f"   Imbalance Ratio: {balance.get('imbalance_ratio', 0):.2f}")
            summary_lines.append(f"   💡 {balance.get('recommendation', '')}\n")

        # Completude
        completeness = report.get('completeness', {})
        summary_lines.append(f"✅ Completude: {completeness.get('completeness_percentage', 0):.2f}%\n")

        # Diversidade
        diversity = report.get('diversity', {})
        if diversity.get('available'):
            summary_lines.append(f"🌈 Diversidade Score: {diversity.get('diversity_score', 0):.4f}")
            summary_lines.append(f"   Features Analisadas: {diversity.get('num_features_analyzed', 0)}\n")

        # Warnings
        warnings = stats._generate_warnings()
        if warnings:
            summary_lines.append(f"⚠️ AVISOS ({len(warnings)}):")
            for warning in warnings:
                summary_lines.append(f"   • {warning}")
            summary_lines.append("")

        # Recomendações
        recommendations = stats._generate_recommendations()
        if recommendations:
            summary_lines.append(f"💡 RECOMENDAÇÕES ({len(recommendations)}):")
            for rec in recommendations:
                summary_lines.append(f"   • {rec}")

        summary_text = "\n".join(summary_lines)

        # Criar gráfico de distribuição de presets
        plot = None
        if presets.get('available'):
            distribution = presets.get('distribution', {})

            preset_names = list(distribution.keys())
            preset_counts = [distribution[k]['count'] for k in preset_names]
            preset_percentages = [distribution[k]['percentage'] for k in preset_names]

            # Criar gráfico de barras com Plotly
            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=preset_names,
                y=preset_counts,
                text=[f"{count}<br>({pct:.1f}%)" for count, pct in zip(preset_counts, preset_percentages)],
                textposition='auto',
                marker=dict(
                    color=preset_counts,
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(title="Amostras")
                )
            ))

            fig.update_layout(
                title="Distribuição de Presets",
                xaxis_title="Preset",
                yaxis_title="Número de Amostras",
                template="plotly_white",
                height=400
            )

            plot = fig

        # Gerar JSON completo (com tratamento de NaN/Infinity)
        def clean_for_json(obj):
            """Remove NaN e Infinity de objetos Python para JSON válido"""
            import math
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
                return obj
            else:
                return obj

        clean_report = clean_for_json(report)
        json_report = json.dumps(clean_report, indent=2, ensure_ascii=False)

        return summary_text, plot, json_report

    except Exception as e:
        import traceback
        error_msg = f"❌ Erro ao calcular estatísticas: {e}\n{traceback.format_exc()}"
        logging.error(error_msg)
        return error_msg, None, "{}"


def analyze_dataset_quality(catalog_path):
    """
    Analisa qualidade do dataset e retorna relatório detalhado.

    Args:
        catalog_path: Caminho para o catálogo Lightroom ou dataset CSV

    Returns:
        Markdown com relatório de qualidade
    """
    try:
        # Verificar se já existe dataset processado
        dataset_path = OUTPUT_DATASET_PATH

        if not dataset_path.exists():
            return """⚠️ **Dataset ainda não foi extraído.**

Execute primeiro a extração do catálogo na aba "Pipeline Completo" ou "Passo a Passo"."""

        # Criar instância do analisador
        analyzer = DatasetQualityAnalyzer(str(dataset_path))
        result = analyzer.analyze()

        # Formatar relatório em Markdown
        report_lines = []

        # Cabeçalho com score
        report_lines.append(f"# 📊 Análise de Qualidade do Dataset\n")
        report_lines.append(f"**Score:** {result['score']:.1f}/100 - **{result['grade']}**\n")
        report_lines.append("---\n")

        # Métricas principais
        metrics = result['metrics']
        report_lines.append("## 📈 Métricas Principais\n")
        report_lines.append(f"- **Total de Amostras:** {metrics.get('num_samples', 0)}")

        if metrics.get('has_presets'):
            report_lines.append(f"- **Número de Classes (Presets):** {metrics.get('num_classes', 0)}")
            report_lines.append(f"- **Ratio de Desbalanceamento:** {metrics.get('imbalance_ratio', 0):.2f}")

        if 'num_duplicates' in metrics:
            report_lines.append(f"- **Duplicatas Encontradas:** {metrics.get('num_duplicates', 0)}")

        report_lines.append(f"- **Sliders Utilizados:** {metrics.get('used_sliders', 0)}/{metrics.get('total_sliders', 0)}")
        report_lines.append("")

        # Distribuição de classes (se disponível)
        if metrics.get('has_presets') and 'class_distribution' in metrics:
            report_lines.append("### 🎨 Distribuição de Presets\n")
            class_dist = metrics['class_distribution']
            for preset_name, count in sorted(class_dist.items(), key=lambda x: x[1], reverse=True):
                report_lines.append(f"- **{preset_name}:** {count} amostras")
            report_lines.append("")

        # Sliders não utilizados
        unused_sliders = metrics.get('unused_sliders', [])
        if unused_sliders:
            report_lines.append(f"### 🔇 Sliders Não Utilizados ({len(unused_sliders)})\n")
            # Mostrar apenas os primeiros 5 para não poluir
            for slider in unused_sliders[:5]:
                report_lines.append(f"- `{slider}`")
            if len(unused_sliders) > 5:
                report_lines.append(f"- *...e mais {len(unused_sliders) - 5} sliders*")
            report_lines.append("")

        # Problemas identificados
        if result['issues']:
            report_lines.append("## ⚠️ Problemas Identificados\n")
            for issue in result['issues']:
                report_lines.append(f"{issue}")
            report_lines.append("")

        # Recomendações
        if result['recommendations']:
            report_lines.append("## 💡 Recomendações\n")
            for rec in result['recommendations']:
                report_lines.append(f"{rec}")
            report_lines.append("")

        # Resumo final
        report_lines.append("---\n")
        report_lines.append("## 📝 Resumo\n")

        score = result['score']
        if score >= 80:
            report_lines.append("✅ **Dataset de alta qualidade!** Pronto para treino.")
        elif score >= 60:
            report_lines.append("⚠️ **Dataset razoável.** Revise as recomendações acima para melhores resultados.")
        else:
            report_lines.append("❌ **Dataset precisa de melhorias significativas.** Siga as recomendações antes de treinar.")

        return "\n".join(report_lines)

    except FileNotFoundError as e:
        return f"❌ **Erro:** {str(e)}"
    except Exception as e:
        import traceback
        error_msg = f"❌ **Erro ao analisar qualidade:**\n\n```\n{str(e)}\n{traceback.format_exc()}\n```"
        logging.error(error_msg)
        return error_msg


def get_hyperparameter_recommendations(catalog_path, model_type):
    """
    Obtém recomendações automáticas de hiperparâmetros

    Args:
        catalog_path: Caminho para o catálogo ou dataset
        model_type: Tipo de modelo (classifier, regressor, clip, culling)

    Returns:
        Tuple (markdown_report, json_params)
    """
    try:
        # Verificar se dataset existe
        dataset_path = OUTPUT_DATASET_PATH

        if not dataset_path.exists():
            return """⚠️ **Dataset ainda não foi extraído.**

Execute primeiro a extração do catálogo.""", {}

        # Criar seletor automático
        selector = AutoHyperparameterSelector(str(dataset_path))
        result = selector.select_hyperparameters(model_type)

        params = result['hyperparameters']
        reasoning = result['reasoning']
        analysis = result['dataset_analysis']

        # Formatar em Markdown
        report_lines = []

        report_lines.append(f"# 🎯 Hiperparâmetros Recomendados - {model_type.upper()}\n")
        report_lines.append("---\n")

        # Análise do dataset
        report_lines.append("## 📊 Análise do Dataset\n")
        report_lines.append(f"- **Total de Amostras:** {analysis['num_samples']}")
        report_lines.append(f"- **Categoria:** {analysis['dataset_size_category'].upper()}")

        if analysis['has_presets']:
            report_lines.append(f"- **Classes:** {analysis['num_classes']}")
            report_lines.append(f"- **Balanceamento:** {analysis['balance_category'].upper()} (ratio: {analysis['imbalance_ratio']:.2f})")

        if analysis['has_ratings']:
            report_lines.append("- **Ratings:** Disponíveis ✅")

        report_lines.append("")

        # Hiperparâmetros
        report_lines.append("## ⚙️ Hiperparâmetros Recomendados\n")

        for param_name, param_value in params.items():
            reason = reasoning.get(param_name, "")
            # Formatação especial para booleanos
            if isinstance(param_value, bool):
                param_value = "✅ Sim" if param_value else "❌ Não"

            report_lines.append(f"### `{param_name}`")
            report_lines.append(f"**Valor:** {param_value}")
            if reason:
                report_lines.append(f"**Razão:** {reason}")
            report_lines.append("")

        # Notas
        report_lines.append("---\n")
        report_lines.append("## 💡 Como Usar\n")
        report_lines.append("1. Revise os valores recomendados acima")
        report_lines.append("2. Clique em '📋 Aplicar aos Inputs' para preencher automaticamente")
        report_lines.append("3. Ou ajuste manualmente na barra lateral")
        report_lines.append("")

        markdown_report = "\n".join(report_lines)

        return markdown_report, params

    except Exception as e:
        import traceback
        error_msg = f"❌ **Erro ao gerar recomendações:**\n\n```\n{str(e)}\n{traceback.format_exc()}\n```"
        logging.error(error_msg)
        return error_msg, {}


def classify_scenes(dataset_path: str, output_path: str, top_k: int):
    """
    Classifica cenas no dataset usando CLIP

    Args:
        dataset_path: Caminho do dataset CSV
        output_path: Caminho para salvar dataset com scene tags
        top_k: Número de categorias por imagem

    Returns:
        Tuple (markdown_report, plotly_figure)
    """
    try:
        from services.scene_classifier import classify_lightroom_catalog
        import plotly.graph_objects as go

        if not Path(dataset_path).exists():
            return "❌ **Dataset não encontrado!** Execute primeiro a extração do catálogo.", None

        logger.info(f"🎬 Classificando cenas: {dataset_path}")

        # Classificar
        distribution = classify_lightroom_catalog(
            dataset_path,
            output_path
        )

        # Gerar relatório
        total_images = sum(distribution.values())
        report_lines = []
        report_lines.append(f"# 🎬 Scene Classification Completa\n")
        report_lines.append(f"**Total de imagens:** {total_images}\n")
        report_lines.append(f"**Output salvo em:** `{output_path}`\n")
        report_lines.append("---\n")
        report_lines.append("## 📊 Distribuição de Cenas\n")

        for scene, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_images * 100) if total_images > 0 else 0
            report_lines.append(f"- **{scene}:** {count} imagens ({percentage:.1f}%)")

        markdown_report = "\n".join(report_lines)

        # Criar gráfico
        scenes = list(distribution.keys())
        counts = [distribution[s] for s in scenes]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=scenes,
            y=counts,
            text=counts,
            textposition='auto',
            marker=dict(
                color=counts,
                colorscale='Viridis',
                showscale=True
            )
        ))

        fig.update_layout(
            title="Distribuição de Categorias de Cena",
            xaxis_title="Categoria",
            yaxis_title="Número de Imagens",
            template="plotly_white",
            height=400
        )

        return markdown_report, fig

    except Exception as e:
        import traceback
        error_msg = f"❌ **Erro ao classificar cenas:**\n\n```\n{str(e)}\n{traceback.format_exc()}\n```"
        logging.error(error_msg)
        return error_msg, None


def detect_duplicates(dataset_path: str, method: str, threshold: int, detect_only: bool, output_path: str):
    """
    Detecta duplicatas no dataset

    Args:
        dataset_path: Caminho do dataset CSV
        method: Método de hashing
        threshold: Threshold de similaridade
        detect_only: Se True, apenas detecta; se False, remove duplicatas
        output_path: Caminho para salvar dataset limpo

    Returns:
        Tuple (markdown_report, html_report)
    """
    try:
        from services.duplicate_detector import DuplicateDetector
        import pandas as pd

        if not Path(dataset_path).exists():
            return "❌ **Dataset não encontrado!** Execute primeiro a extração do catálogo.", ""

        logger.info(f"🔍 Detectando duplicatas: {dataset_path}")

        # Criar detector
        detector = DuplicateDetector(hash_method=method)

        # Carregar dataset
        df = pd.read_csv(dataset_path)
        if 'image_path' not in df.columns:
            return "❌ **Erro:** Dataset deve conter coluna 'image_path'", ""

        image_paths = df['image_path'].tolist()

        # Detectar duplicatas
        duplicate_groups = detector.find_duplicates(image_paths, threshold=threshold)

        # Gerar relatório
        num_groups = len(duplicate_groups)
        total_duplicates = sum(len(g.duplicates) for g in duplicate_groups)

        report_lines = []
        report_lines.append(f"# 🔍 Duplicate Detection Completa\n")
        report_lines.append(f"**Método:** {method} hash\n")
        report_lines.append(f"**Threshold:** {threshold}\n")
        report_lines.append(f"**Total de imagens:** {len(image_paths)}\n")
        report_lines.append("---\n")
        report_lines.append(f"## 📊 Resultados\n")
        report_lines.append(f"- **Grupos de duplicatas encontrados:** {num_groups}")
        report_lines.append(f"- **Total de duplicatas:** {total_duplicates}")

        if total_duplicates == 0:
            report_lines.append("\n✅ **Nenhuma duplicata encontrada!**")
        else:
            report_lines.append(f"\n⚠️ **{total_duplicates} duplicatas encontradas** em {num_groups} grupos")

        # Remover duplicatas se solicitado
        if not detect_only and total_duplicates > 0:
            stats = detector.remove_duplicates_from_dataset(
                dataset_path,
                output_path,
                threshold=threshold
            )
            report_lines.append(f"\n### 🧹 Limpeza Realizada\n")
            report_lines.append(f"- **Dataset original:** {stats['original_size']} imagens")
            report_lines.append(f"- **Dataset limpo:** {stats['cleaned_size']} imagens")
            report_lines.append(f"- **Removidas:** {stats['removed_count']} imagens")
            report_lines.append(f"\n✅ **Dataset limpo salvo em:** `{output_path}`")

        markdown_report = "\n".join(report_lines)

        # Gerar HTML preview dos primeiros 5 grupos
        html_report = ""
        if num_groups > 0:
            html_lines = ["<div style='font-family: Arial, sans-serif;'>"]
            html_lines.append("<h3>Preview dos Primeiros Grupos de Duplicatas</h3>")

            for i, group in enumerate(duplicate_groups[:5], 1):
                html_lines.append(f"<div style='border: 1px solid #ccc; margin: 10px 0; padding: 10px;'>")
                html_lines.append(f"<h4>Grupo {i}</h4>")
                html_lines.append(f"<p><strong>Representative:</strong> {Path(group.representative).name}</p>")
                html_lines.append(f"<p><strong>Duplicates:</strong> {len(group.duplicates)}</p>")
                for dup in group.duplicates[:3]:
                    html_lines.append(f"<p>• {Path(dup).name}</p>")
                if len(group.duplicates) > 3:
                    html_lines.append(f"<p>... e mais {len(group.duplicates) - 3}</p>")
                html_lines.append("</div>")

            if num_groups > 5:
                html_lines.append(f"<p><em>... e mais {num_groups - 5} grupos</em></p>")

            html_lines.append("</div>")
            html_report = "\n".join(html_lines)

        return markdown_report, html_report

    except Exception as e:
        import traceback
        error_msg = f"❌ **Erro ao detectar duplicatas:**\n\n```\n{str(e)}\n{traceback.format_exc()}\n```"
        logging.error(error_msg)
        return error_msg, ""


def reset_dataset_outputs():
    """
    Remove ficheiros de dataset/estatísticas gerados, para forçar recalcular.
    """
    removed = []
    for path in [OUTPUT_DATASET_PATH, OUTPUT_FEATURES_PATH, OUTPUT_DEEP_FEATURES_PATH]:
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if removed:
        return f"📄 Removidos: {', '.join(removed)}\nVolta a correr a extração do catálogo antes de calcular estatísticas."
    return "Nada para remover. Extrai primeiro o catálogo para gerar novos ficheiros."


# --- FastAPI Server Management ---
# Global para armazenar o processo do servidor
_server_process = None

def start_fastapi_server():
    """
    Inicia o servidor FastAPI em background com logs em tempo real.

    Yields:
        Tuplas (logs, status)
    """
    global _server_process

    collector = []
    log_path = create_log_file("fastapi_server")

    python_executable = PROJECT_ROOT / "venv" / "bin" / "python"
    server_module = "services.server:app"

    if not python_executable.exists():
        error_msg = f"❌ Erro: Executável Python do venv não encontrado em {python_executable}"
        yield error_msg, "Erro"
        return

    command = [
        str(python_executable),
        "-m", "uvicorn",
        server_module,
        "--host", "127.0.0.1",
        "--port", "5678",
        "--reload"
    ]

    try:
        initial_msg = format_log_with_timestamp(f"🚀 Iniciando servidor FastAPI...")
        collector.append(initial_msg)
        append_log_line(log_path, initial_msg)

        cmd_msg = format_log_with_timestamp(f"Comando: {' '.join(command)}")
        collector.append(cmd_msg)
        append_log_line(log_path, cmd_msg)

        yield "\n".join(collector), "A iniciar..."

        _server_process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        success_msg = format_log_with_timestamp("✅ Servidor FastAPI iniciado!")
        collector.append(success_msg)
        collector.append(format_log_with_timestamp("📡 URL: http://127.0.0.1:5678"))
        collector.append(format_log_with_timestamp("📚 Docs: http://127.0.0.1:5678/docs"))
        collector.append(format_log_with_timestamp(""))
        collector.append("--- LOGS DO SERVIDOR ---")
        append_log_line(log_path, success_msg)

        yield "\n".join(collector), "✅ A executar"

        # Streaming de logs
        for line in iter(_server_process.stdout.readline, ''):
            if not line:
                break
            line = line.rstrip()
            collector.append(line)
            append_log_line(log_path, line)

            # Limitar tamanho do buffer (manter últimas 200 linhas)
            if len(collector) > 200:
                collector = collector[-200:]

            yield "\n".join(collector), "✅ A executar"

        _server_process.wait()

        if _server_process.returncode != 0:
            error_msg = format_log_with_timestamp(f"❌ Servidor terminou com erro (código {_server_process.returncode})")
            collector.append(error_msg)
            append_log_line(log_path, error_msg)
            yield "\n".join(collector), "❌ Erro"
        else:
            stop_msg = format_log_with_timestamp("⏹️ Servidor parado")
            collector.append(stop_msg)
            append_log_line(log_path, stop_msg)
            yield "\n".join(collector), "⏹️ Parado"

    except Exception as e:
        error_msg = format_log_with_timestamp(f"❌ Erro ao iniciar servidor: {e}")
        collector.append(error_msg)
        append_log_line(log_path, error_msg)
        yield "\n".join(collector), "❌ Erro"


def stop_fastapi_server():
    """Para o servidor FastAPI se estiver a correr."""
    global _server_process

    if _server_process and _server_process.poll() is None:
        _server_process.terminate()
        try:
            _server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _server_process.kill()
        return "⏹️ Servidor parado com sucesso"
    else:
        return "⚠️ Servidor não está a correr"


# --- Transfer Learning Functions ---
def run_transfer_learning(
    model_type="clip",
    epochs=30,
    batch_size=16,
    learning_rate=1e-3,
    use_attention=True,
    patience=10,
):
    """
    Executa treino com Transfer Learning (CLIP, DINOv2, ou ConvNeXt).

    Args:
        model_type: "clip", "dinov2", ou "convnext"
        epochs: Número de épocas
        batch_size: Tamanho do batch
        learning_rate: Taxa de aprendizagem
        use_attention: Usar mecanismos de atenção
        patience: Paciência para early stopping

    Yields:
        Tuplas (logs, log_file, status)
    """
    collector = []
    log_path = create_log_file(f"transfer_learning_{model_type}")

    initial_msg = format_log_with_timestamp(f"🎓 Iniciando Transfer Learning com {model_type.upper()}")
    collector.append(initial_msg)
    append_log_line(log_path, initial_msg)

    yield "\n".join(collector), None, "A treinar..."

    try:
        # Verificar se dataset existe
        if not OUTPUT_DATASET_PATH.exists():
            error_msg = "❌ Dataset não encontrado! Execute primeiro a extração do catálogo Lightroom."
            collector.append(format_log_with_timestamp(error_msg))
            append_log_line(log_path, format_log_with_timestamp(error_msg))
            yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"
            return

        # Preparar comando
        python_executable = sys.executable
        script_path = PROJECT_ROOT / "train" / "train_with_clip.py"

        command = [
            python_executable,
            str(script_path),
            "--dataset", str(OUTPUT_DATASET_PATH),
            "--clip-model", "ViT-B/32" if model_type == "clip" else "ViT-B/16",
            "--epochs", str(int(epochs)),
            "--batch-size", str(int(batch_size)),
            "--lr", str(float(learning_rate)),
            "--device", "mps" if sys.platform == "darwin" else "cuda",
        ]

        # Executar processo
        msg = format_log_with_timestamp(f"Executando: {' '.join(command)}")
        collector.append(msg)
        append_log_line(log_path, msg)
        yield "\n".join(collector), None, "A treinar..."

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT
        )

        # Streaming de output
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            line = line.rstrip()
            collector.append(line)
            append_log_line(log_path, line)
            yield "\n".join(collector), gr.update(value=str(log_path)), "A treinar..."

        process.wait()

        if process.returncode == 0:
            final_msg = format_log_with_timestamp(f"✅ Transfer Learning concluído com sucesso!")
            collector.append(final_msg)
            append_log_line(log_path, final_msg)
            yield "\n".join(collector), gr.update(value=str(log_path)), "✅ Concluído"
        else:
            error_msg = format_log_with_timestamp(f"❌ Processo terminou com erro (código {process.returncode})")
            collector.append(error_msg)
            append_log_line(log_path, error_msg)
            yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"

    except Exception as e:
        error_msg = format_log_with_timestamp(f"❌ Erro durante Transfer Learning: {e}")
        collector.append(error_msg)
        append_log_line(log_path, error_msg)
        yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"


def run_culling_training(
    dataset_type="lightroom",
    ava_images_limit=1000,
    epochs=50,
    batch_size=32,
    learning_rate=1e-4,
    patience=10,
):
    """
    Executa treino do modelo de Culling com DINOv2.

    Args:
        dataset_type: "lightroom" ou "ava"
        ava_images_limit: Número de imagens AVA a usar (se dataset_type="ava")
        epochs: Número de épocas
        batch_size: Tamanho do batch
        learning_rate: Taxa de aprendizagem
        patience: Paciência para early stopping

    Yields:
        Tuplas (logs, log_file, status)
    """
    collector = []
    log_path = create_log_file("culling_training")

    initial_msg = format_log_with_timestamp(f"⭐ Iniciando treino de Culling com dataset {dataset_type.upper()}")
    collector.append(initial_msg)
    append_log_line(log_path, initial_msg)

    yield "\n".join(collector), None, "A treinar..."

    try:
        # Verificar dataset
        if dataset_type == "lightroom" and not OUTPUT_DATASET_PATH.exists():
            error_msg = "❌ Dataset Lightroom não encontrado! Execute primeiro a extração do catálogo."
            collector.append(format_log_with_timestamp(error_msg))
            append_log_line(log_path, format_log_with_timestamp(error_msg))
            yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"
            return

        if dataset_type == "ava":
            ava_csv_path = PROJECT_ROOT / "data" / "ava" / "ava_dataset.csv"
            if not ava_csv_path.exists():
                error_msg = "❌ Dataset AVA não encontrado! Faça download primeiro na tab Smart Culling."
                collector.append(format_log_with_timestamp(error_msg))
                append_log_line(log_path, format_log_with_timestamp(error_msg))
                yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"
                return

        # Preparar comando
        python_executable = sys.executable
        script_path = PROJECT_ROOT / "train" / "train_culling_dinov2.py"

        command = [
            python_executable,
            str(script_path),
            "--dataset-type", dataset_type,
            "--epochs", str(int(epochs)),
            "--batch-size", str(int(batch_size)),
            "--learning-rate", str(float(learning_rate)),
            "--patience", str(int(patience)),
            "--device", "mps" if sys.platform == "darwin" else "cuda",
        ]

        if dataset_type == "lightroom":
            command.extend(["--lightroom-csv", str(OUTPUT_DATASET_PATH)])
        else:
            command.extend([
                "--ava-csv", str(PROJECT_ROOT / "data" / "ava" / "ava_dataset.csv"),
                "--ava-images-dir", str(PROJECT_ROOT / "data" / "ava" / "images"),
                "--ava-images-limit", str(int(ava_images_limit))
            ])

        # Executar processo
        msg = format_log_with_timestamp(f"Executando: {' '.join(command)}")
        collector.append(msg)
        append_log_line(log_path, msg)
        yield "\n".join(collector), None, "A treinar..."

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT
        )

        # Streaming de output
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            line = line.rstrip()
            collector.append(line)
            append_log_line(log_path, line)
            yield "\n".join(collector), gr.update(value=str(log_path)), "A treinar..."

        process.wait()

        if process.returncode == 0:
            final_msg = format_log_with_timestamp(f"✅ Treino de Culling concluído com sucesso!")
            collector.append(final_msg)
            append_log_line(log_path, final_msg)
            yield "\n".join(collector), gr.update(value=str(log_path)), "✅ Concluído"
        else:
            error_msg = format_log_with_timestamp(f"❌ Processo terminou com erro (código {process.returncode})")
            collector.append(error_msg)
            append_log_line(log_path, error_msg)
            yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"

    except Exception as e:
        error_msg = format_log_with_timestamp(f"❌ Erro durante treino de Culling: {e}")
        collector.append(error_msg)
        append_log_line(log_path, error_msg)
        yield "\n".join(collector), gr.update(value=str(log_path)), "❌ Erro"


def download_ava_dataset(num_images=1000):
    """
    Faz download do dataset AVA para treino de Culling.

    Args:
        num_images: Número de imagens a fazer download

    Yields:
        Tuplas (logs, status)
    """
    collector = []
    log_path = create_log_file("ava_download")

    initial_msg = format_log_with_timestamp(f"📥 Iniciando download de {num_images} imagens do dataset AVA")
    collector.append(initial_msg)
    append_log_line(log_path, initial_msg)

    yield "\n".join(collector), "A fazer download..."

    try:
        # Preparar comando
        python_executable = sys.executable
        script_path = PROJECT_ROOT / "tools" / "download_ava_dataset.py"

        command = [
            python_executable,
            str(script_path),
            "--num-samples", str(int(num_images)),
            "--output-dir", "data/ava",
            "--workers", "10"
        ]

        # Executar processo
        msg = format_log_with_timestamp(f"Executando: {' '.join(command)}")
        collector.append(msg)
        append_log_line(log_path, msg)
        yield "\n".join(collector), "A fazer download..."

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=PROJECT_ROOT
        )

        # Streaming de output
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            line = line.rstrip()
            collector.append(line)
            append_log_line(log_path, line)
            yield "\n".join(collector), "A fazer download..."

        process.wait()

        if process.returncode == 0:
            final_msg = format_log_with_timestamp(f"✅ Download do dataset AVA concluído com sucesso!")
            collector.append(final_msg)
            append_log_line(log_path, final_msg)
            yield "\n".join(collector), "✅ Concluído"
        else:
            error_msg = format_log_with_timestamp(f"❌ Processo terminou com erro (código {process.returncode})")
            collector.append(error_msg)
            append_log_line(log_path, error_msg)
            yield "\n".join(collector), "❌ Erro"

    except Exception as e:
        error_msg = format_log_with_timestamp(f"❌ Erro durante download: {e}")
        collector.append(error_msg)
        append_log_line(log_path, error_msg)
        yield "\n".join(collector), "❌ Erro"


# --- Training Pipeline ---
def run_training_step(
    step_name,
    catalog_path,
    overwrite=True,
    skip_missing=True,
    limit=None,
    num_presets=4,
    min_rating=3,
    classifier_epochs=50,
    refiner_epochs=100,
    batch_size=32,
    patience=7,
    stat_noise_std=0.05,
    deep_dropout_prob=0.1,
    mixup_alpha=0.3,
    classifier_weight_decay=0.01,
    refiner_weight_decay=0.02,
    model_width_factor=1.0,
    param_importance=json.dumps(_PARAM_IMPORTANCE, indent=4),
    button_labels=None,
    summary_parser=None,
):
    """
    Executa um passo do pipeline de treino.

    Args:
        step_name: Nome do passo a executar
        catalog_path: Caminho para o catálogo Lightroom
        button_labels: Dicionário com labels para os botões
        summary_parser: Função para parse do summary

    Yields:
        Tuplas com (logs, log_file, summary_data, summary_text, button_update)
    """
    collector: List[str] = []
    log_path = create_log_file(step_name.replace(" ", "_").lower())

    def button_update(label: Optional[str] = None, interactive: Optional[bool] = None):
        if button_labels is None:
            return gr.update()
        update_kwargs = {}
        if label is not None:
            update_kwargs["value"] = label
        if interactive is not None:
            update_kwargs["interactive"] = interactive
        return gr.update(**update_kwargs)

    def _file_update():
        if log_path and Path(log_path).exists():
            return gr.update(value=str(log_path))
        return gr.update(value=None)

    def yield_state():
        return (
            "\n".join(collector),
            _file_update(),
            gr.update(value=None),
            gr.update(value=None),
            button_update(button_labels.get("running") if button_labels else None, False),
        )

    # Log inicial
    initial_msg = format_log_with_timestamp(f"🚀 Iniciando: {step_name}")

    collector.append(initial_msg)
    append_log_line(log_path, initial_msg)
    yield yield_state()

    try:
        # Configurar treino (sempre V2)
        parsed_param_importance = json.loads(param_importance) if param_importance else None
        set_training_configs(
            catalog_path=catalog_path,
            min_rating=min_rating,
            classifier_epochs=classifier_epochs,
            refiner_epochs=refiner_epochs,
            batch_size=batch_size,
            patience=patience,
            param_importance=parsed_param_importance,
            stat_noise_std=stat_noise_std,
            deep_dropout_prob=deep_dropout_prob,
            mixup_alpha=mixup_alpha,
            classifier_weight_decay=classifier_weight_decay,
            refiner_weight_decay=refiner_weight_decay,
            model_width_factor=model_width_factor,
        )
        collector.append(format_log_with_timestamp(f"⚙️ Configurações definidas"))
        append_log_line(log_path, format_log_with_timestamp(f"⚙️ Configurações definidas"))
        yield (
            "\n".join(collector),
            gr.update(value=None),
            gr.update(value=None),
            gr.update(value=None),
            button_update(None, False),
        )

        # Executar passo específico
        if step_name == "Pipeline completo":
            def pipeline_runner():
                return run_full_training_pipeline(
                    catalog_path=catalog_path,
                    num_presets=num_presets,
                    min_rating=min_rating,
                    classifier_epochs=classifier_epochs,
                    refiner_epochs=refiner_epochs,
                    batch_size=batch_size,
                    patience=patience,
                )

            log_stream = stream_logs_from_function(
                pipeline_runner,
                collector,
                log_path
            )
            result_message = "Pipeline completo concluído."
            try:
                while True:
                    log_text = next(log_stream)
                    yield (
                        log_text,
                        _file_update(),
                        gr.update(value=None),
                        gr.update(value=None),
                        button_update(button_labels.get("running") if button_labels else None, False),
                    )
            except StopIteration as stop:
                result_message = stop.value or result_message

            summary_text = parse_mae_summary(collector, "Refinador") if summary_parser == "parse_mae_summary" else result_message

            collector.append(format_log_with_timestamp(result_message))
            append_log_line(log_path, format_log_with_timestamp(result_message))
            yield (
                "\n".join(collector),
                _file_update(),
                gr.update(value=None),
                summary_text,
                button_update(button_labels.get("idle") if button_labels else None, True),
            )
            return

        elif step_name == "Extração do catálogo Lightroom":
            dataset = extract_lightroom_data(
                catalog_path=Path(catalog_path),
                output_path=OUTPUT_DATASET_PATH,
                min_rating=min_rating
            )
            msg = f"✅ Extração concluída. {len(dataset)} imagens processadas."
            collector.append(format_log_with_timestamp(msg))
            append_log_line(log_path, format_log_with_timestamp(msg))

        elif step_name == "Identificação de Presets e Deltas":
            dataset = extract_lightroom_data(
                catalog_path=Path(catalog_path),
                output_path=OUTPUT_DATASET_PATH,
                min_rating=min_rating
            )
            dataset_with_deltas, _, _ = identify_presets_and_deltas(dataset, num_presets=num_presets)
            msg = f"✅ Presets e deltas identificados para {len(dataset_with_deltas)} imagens."
            collector.append(format_log_with_timestamp(msg))
            append_log_line(log_path, format_log_with_timestamp(msg))

        elif step_name == "Extração de Features (Estatísticas e Deep)":
            dataset = extract_lightroom_data(
                catalog_path=Path(catalog_path),
                output_path=OUTPUT_DATASET_PATH,
                min_rating=min_rating
            )
            dataset_with_deltas, _, _ = identify_presets_and_deltas(dataset, num_presets=num_presets)
            _, _ = extract_image_features(dataset_with_deltas, OUTPUT_FEATURES_PATH, OUTPUT_DEEP_FEATURES_PATH)
            msg = "✅ Features estatísticas e deep extraídas."
            collector.append(format_log_with_timestamp(msg))
            append_log_line(log_path, format_log_with_timestamp(msg))

        elif step_name == "Preparação de Dados de Treino":
            dataset = extract_lightroom_data(
                catalog_path=Path(catalog_path),
                output_path=OUTPUT_DATASET_PATH,
                min_rating=min_rating
            )
            dataset_with_deltas, _, delta_columns = identify_presets_and_deltas(dataset, num_presets=num_presets)
            features_df, deep_features = extract_image_features(dataset_with_deltas, OUTPUT_FEATURES_PATH, OUTPUT_DEEP_FEATURES_PATH)
            _, _, _, _, _, _, _, _, scaler_stat, scaler_deep, scaler_deltas = prepare_training_data(
                dataset_with_deltas, features_df, deep_features, delta_columns
            )
            save_scalers_local(scaler_stat, scaler_deep, scaler_deltas)
            msg = "✅ Dados de treino preparados e scalers guardados."
            collector.append(format_log_with_timestamp(msg))
            append_log_line(log_path, format_log_with_timestamp(msg))

        elif step_name == "Treinar Classificador de Presets":
            dataset = extract_lightroom_data(
                catalog_path=Path(catalog_path),
                output_path=OUTPUT_DATASET_PATH,
                min_rating=min_rating
            )
            dataset_with_deltas, _, delta_columns = identify_presets_and_deltas(dataset, num_presets=num_presets)
            features_df, deep_features = extract_image_features(dataset_with_deltas, OUTPUT_FEATURES_PATH, OUTPUT_DEEP_FEATURES_PATH)
            X_stat_train, X_stat_val, X_deep_train, X_deep_val, \
            y_train_labels, y_val_labels, _, _, _, _, _ = prepare_training_data(
                dataset_with_deltas, features_df, deep_features, delta_columns
            )
            train_preset_classifier(
                X_stat_train, X_stat_val, X_deep_train, X_deep_val,
                y_train_labels, y_val_labels,
                num_presets=num_presets,
            )
            msg = "✅ Classificador de presets treinado."
            collector.append(format_log_with_timestamp(msg))
            append_log_line(log_path, format_log_with_timestamp(msg))

        elif step_name == "Treinar Refinador de Ajustes":
            dataset = extract_lightroom_data(
                catalog_path=Path(catalog_path),
                output_path=OUTPUT_DATASET_PATH,
                min_rating=min_rating
            )
            dataset_with_deltas, _, delta_columns = identify_presets_and_deltas(dataset, num_presets=num_presets)
            features_df, deep_features = extract_image_features(dataset_with_deltas, OUTPUT_FEATURES_PATH, OUTPUT_DEEP_FEATURES_PATH)
            X_stat_train, X_stat_val, X_deep_train, X_deep_val, \
            y_train_labels, y_val_labels, y_train_deltas, y_val_deltas, \
            _, _, scaler_deltas = prepare_training_data(
                dataset_with_deltas, features_df, deep_features, delta_columns
            )
            train_refinement_regressor(
                X_stat_train, X_stat_val, X_deep_train, X_deep_val,
                y_train_labels, y_val_labels, y_train_deltas, y_val_deltas,
                delta_columns, scaler_deltas,
                num_presets=num_presets,
            )
            msg = "✅ Refinador de ajustes treinado."
            collector.append(format_log_with_timestamp(msg))
            append_log_line(log_path, format_log_with_timestamp(msg))

        else:
            raise ValueError(f"Passo de treino desconhecido: {step_name}")

        # Parse do summary se configurado
        summary_data = None
        summary_text = None
        if summary_parser:
            if isinstance(summary_parser, str):
                summary_func = globals().get(summary_parser)
                if summary_func and callable(summary_func):
                    summary_data, summary_text = summary_func(collector, "Refinador")
            elif callable(summary_parser):
                summary_data, summary_text = summary_parser(collector, "Refinador")

        # Mensagem final
        final_msg = format_log_with_timestamp(f"✅ {step_name} concluído com sucesso!")
        collector.append(final_msg)
        append_log_line(log_path, final_msg)

        final_label = button_labels.get("idle") if button_labels else "Concluído"
        yield (
            "\n".join(collector),
            gr.update(value=str(log_path)),
            gr.update(value=summary_data),
            gr.update(value=summary_text),
            button_update(final_label, True),
        )

    except Exception as e:
        error_msg = format_log_with_timestamp(f"❌ Erro durante '{step_name}': {e}")
        if "Dataset vazio" in str(e):
            error_msg += "\n\n💡 Por favor, verifique:\n"
            error_msg += "   • Caminho do catálogo Lightroom está correto\n"
            error_msg += "   • Catálogo contém imagens com rating >= " + str(min_rating) + "\n"
            error_msg += "   • Rating mínimo não está demasiado alto"
        collector.append(error_msg)
        append_log_line(log_path, error_msg)

        final_label = button_labels.get("error") if button_labels else "Erro"
        yield (
            "\n".join(collector),
            gr.update(value=str(log_path)),
            gr.update(value=None),
            gr.update(value=None),
            button_update(final_label, True),
        )
        raise gr.Error(error_msg)


# --- Labels dos botões ---
BUTTON_LABELS = {
    "pipeline": {
        "idle": "▶️ Executar Pipeline Completo",
        "running": "⏳ A executar pipeline...",
        "error": "🔄 Tentar Novamente",
    },
    "extract": {
        "idle": "1️⃣ Extrair Dados do Catálogo",
        "running": "⏳ A extrair dados...",
        "error": "🔄 Repetir Extração",
    },
    "identify_presets": {
        "idle": "2️⃣ Identificar Presets e Deltas",
        "running": "⏳ A identificar presets...",
        "error": "🔄 Repetir Identificação",
    },
    "extract_features": {
        "idle": "3️⃣ Extrair Features",
        "running": "⏳ A extrair features...",
        "error": "🔄 Repetir Extração",
    },
    "prepare_data": {
        "idle": "4️⃣ Preparar Dados de Treino",
        "running": "⏳ A preparar dados...",
        "error": "🔄 Repetir Preparação",
    },
    "train_classifier": {
        "idle": "5️⃣ Treinar Classificador",
        "running": "⏳ A treinar classificador...",
        "error": "🔄 Repetir Treino",
    },
    "train_regressor": {
        "idle": "6️⃣ Treinar Refinador",
        "running": "⏳ A treinar refinador...",
        "error": "🔄 Repetir Treino",
    },
}


# --- CSS Personalizado ---
CUSTOM_CSS = """
.gradio-container {
    max-width: 100%;
    margin: auto;
    padding: 20px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.title-header {
    text-align: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 30px;
    border-radius: 10px;
    margin-bottom: 20px;
}

.title-header h1 {
    margin: 0;
    font-size: 2.5em;
    font-weight: 700;
}

.title-header p {
    margin: 10px 0 0 0;
    font-size: 1.1em;
    opacity: 0.9;
}

.stats-container {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 8px;
    margin: 10px 0;
}
"""


# --- Gradio UI ---
with gr.Blocks(css=CUSTOM_CSS) as iface:
    # Header
    gr.HTML("""
        <div class="title-header">
            <h1>🎨 NSP Plugin V2</h1>
            <p>Pipeline de Treino Otimizado para Datasets Pequenos</p>
        </div>
    """)

    # ====================================================================
    # CONFIGURAÇÃO (Accordion colapsável no topo para definir componentes)
    # ====================================================================

    with gr.Accordion("⚙️ Configuração e Logs", open=False):
        with gr.Row():
            # Coluna lateral - Inputs de Configuração
            with gr.Column(scale=1, min_width=320):
                gr.Markdown("### 📁 Configuração do Catálogo")

                catalog_file_input = gr.File(
                    label="Arrasta ou seleciona o catálogo (.lrcat)",
                    file_types=[".lrcat"],
                    file_count="single",
                    type="filepath",
                )
                catalog_input = gr.Textbox(
                    label="Caminho completo do catálogo",
                    placeholder="/Users/teuuser/Pictures/Lightroom/Lightroom Catalog.lrcat",
                )

                gr.Markdown("### ⚙️ Configurações de Treino (V2 otimizado)")

                overwrite_checkbox = gr.Checkbox(
                    label="Recriar base de dados (overwrite)",
                    value=True,
                )
                skip_missing_checkbox = gr.Checkbox(
                    label="Ignorar imagens em falta",
                    value=True,
                )
                limit_input = gr.Number(
                    label="Limite de fotos (opcional)",
                    precision=0,
                    value=None,
                )
                batch_size_slider = gr.Slider(
                    label="Batch Size",
                    minimum=8,
                    maximum=128,
                    step=8,
                    value=32,
                    info="Reduza se tiver pouca RAM/VRAM",
                )

                gr.Markdown("### 🎯 Configurações Avançadas")

                num_presets_input = gr.Number(
                    label="Número de Presets a Identificar",
                    precision=0,
                    minimum=1,
                    value=4,
                )
                min_rating_input = gr.Number(
                    label="Rating Mínimo para Fotos de Treino",
                    precision=0,
                    minimum=1,
                    maximum=5,
                    value=3,
                )
                classifier_epochs_input = gr.Number(
                    label="Épocas para o Classificador",
                    precision=0,
                    minimum=1,
                    value=50,
                )
                refiner_epochs_input = gr.Number(
                    label="Épocas para o Refinador",
                    precision=0,
                    minimum=1,
                    value=100,
                )
                patience_input = gr.Number(
                    label="Paciência para Early Stopping",
                    precision=0,
                    minimum=1,
                    value=7,
                )
                stat_noise_input = gr.Slider(
                    label="Noise (STAT_NOISE_STD)",
                    minimum=0.0,
                    maximum=0.5,
                    step=0.01,
                    value=0.05,
                    info="Ruído estatístico para augment",
                )
                deep_dropout_input = gr.Slider(
                    label="Dropout (DEEP_DROPOUT_PROB)",
                    minimum=0.0,
                    maximum=0.8,
                    step=0.05,
                    value=0.1,
                    info="Dropout em features profundas",
                )
                mixup_alpha_input = gr.Slider(
                    label="Mixup Alpha",
                    minimum=0.0,
                    maximum=1.0,
                    step=0.05,
                    value=0.3,
                    info="Alpha da Beta para mixup (regressor)",
                )
                clf_wd_input = gr.Slider(
                    label="Weight Decay Classificador",
                    minimum=0.0,
                    maximum=0.2,
                    step=0.005,
                    value=0.01,
                    info="Regularização L2 do classificador",
                )
                ref_wd_input = gr.Slider(
                    label="Weight Decay Refinador",
                    minimum=0.0,
                    maximum=0.2,
                    step=0.005,
                    value=0.02,
                    info="Regularização L2 do refinador",
                )
                width_factor_input = gr.Slider(
                    label="Fator de largura do modelo",
                    minimum=0.5,
                    maximum=1.0,
                    step=0.05,
                    value=1.0,
                    info="<1.0 reduz parâmetros (simplicidade)",
                )
                param_importance_input = gr.Textbox(
                    label="Pesos de Importância dos Parâmetros (JSON)",
                    value=json.dumps(_PARAM_IMPORTANCE, indent=4),
                    lines=8,
                    interactive=True,
                )

                gr.Markdown("### ⚡ Recomendações rápidas (auto-preenche)")
                with gr.Row():
                    rec_aug_btn = gr.Button("Augmentação agressiva")
                    rec_reg_btn = gr.Button("Regularização forte")
                    rec_simple_btn = gr.Button("Modelo mais simples")
                    rec_onecycle_btn = gr.Button("OneCycleLR (já ativo)")

                rec_aug_btn.click(
                    fn=lambda: apply_recommendation("aug"),
                    inputs=[],
                    outputs=[
                        stat_noise_input,
                        deep_dropout_input,
                        mixup_alpha_input,
                        clf_wd_input,
                        ref_wd_input,
                        width_factor_input,
                    ],
                )
                rec_reg_btn.click(
                    fn=lambda: apply_recommendation("reg"),
                    inputs=[],
                    outputs=[
                        stat_noise_input,
                        deep_dropout_input,
                        mixup_alpha_input,
                        clf_wd_input,
                        ref_wd_input,
                        width_factor_input,
                    ],
                )
                rec_simple_btn.click(
                    fn=lambda: apply_recommendation("simple"),
                    inputs=[],
                    outputs=[
                        stat_noise_input,
                        deep_dropout_input,
                        mixup_alpha_input,
                        clf_wd_input,
                        ref_wd_input,
                        width_factor_input,
                    ],
                )
                rec_onecycle_btn.click(
                    fn=lambda: apply_recommendation("onecycle"),
                    inputs=[],
                    outputs=[
                        stat_noise_input,
                        deep_dropout_input,
                        mixup_alpha_input,
                        clf_wd_input,
                        ref_wd_input,
                        width_factor_input,
                    ],
                )

            # Coluna central - Outputs
            with gr.Column(scale=2):
                log_output = gr.Textbox(
                    label="📋 Logs do Processo",
                    lines=30,
                    interactive=False,
                    autoscroll=True,
                )
                log_file_output = gr.File(
                    label="💾 Transferir Último Log",
                    interactive=False,
                )
                summary_table = gr.Dataframe(
                    headers=["Modelo", "Slider", "MAE"],
                    label="📊 Resumo MAE (última avaliação)",
                    interactive=False,
                )
                summary_overall = gr.Textbox(
                    label="📈 MAE Global",
                    interactive=False,
                )

        # Callback para upload de ficheiro
        catalog_file_input.change(
            fn=_catalog_from_file,
            inputs=catalog_file_input,
            outputs=catalog_input,
        )

    # ====================================================================
    # TABS (aparecem logo a seguir ao header)
    # ====================================================================
    with gr.Tabs():
        # Tab 1: Pipeline Completo
        with gr.Tab("🚀 Pipeline Completo"):
            gr.Markdown("""
                Execute o pipeline completo de treino, desde a extração do catálogo até ao treino final dos modelos.

                **Passos incluídos:**
                1. Extração de dados do catálogo Lightroom
                2. Identificação de presets e deltas
                3. Extração de features (estatísticas + deep learning)
                4. Preparação de dados de treino
                5. Treino do classificador de presets
                6. Treino do refinador de ajustes
            """)

            start_pipeline_btn = gr.Button(
                BUTTON_LABELS["pipeline"]["idle"],
                variant="primary",
                interactive=False,
                size="lg"
            )
            start_pipeline_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Pipeline completo"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["pipeline"]),
                    gr.State("parse_mae_summary"),
                ],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    start_pipeline_btn,
                ],
            )

        # Tab 2: Passo a Passo
        with gr.Tab("🔧 Passo a Passo"):
            gr.Markdown("""
                Execute cada etapa do pipeline individualmente para maior controlo e debug.

                **Útil para:**
                - Debug de problemas específicos
                - Re-treino apenas de componentes específicos
                - Experimentação com diferentes configurações
            """)

            extract_btn = gr.Button(BUTTON_LABELS["extract"]["idle"], interactive=False)
            identify_presets_btn = gr.Button(BUTTON_LABELS["identify_presets"]["idle"], interactive=False)
            extract_features_btn = gr.Button(BUTTON_LABELS["extract_features"]["idle"], interactive=False)
            prepare_data_btn = gr.Button(BUTTON_LABELS["prepare_data"]["idle"], interactive=False)
            train_classifier_btn = gr.Button(BUTTON_LABELS["train_classifier"]["idle"], interactive=False)
            train_regressor_btn = gr.Button(BUTTON_LABELS["train_regressor"]["idle"], interactive=False)

            # Registar botões para ativação quando catálogo for carregado
            CATALOG_BUTTONS.clear()
            CATALOG_BUTTONS.extend([
                start_pipeline_btn,
                extract_btn,
                identify_presets_btn,
                extract_features_btn,
                prepare_data_btn,
                train_classifier_btn,
                train_regressor_btn,
            ])

            # Callbacks para ativação de botões
            catalog_input.change(
                fn=lambda manual_path, uploaded_path: [
                    gr.update(interactive=_has_catalog_path(manual_path, uploaded_path))
                    for _ in CATALOG_BUTTONS
                ],
                inputs=[catalog_input, catalog_file_input],
                outputs=CATALOG_BUTTONS,
            )
            catalog_file_input.change(
                fn=lambda uploaded_file_obj, manual_path: [
                    gr.update(value=_catalog_from_file(uploaded_file_obj)),
                    *[gr.update(interactive=_has_catalog_path(_catalog_from_file(uploaded_file_obj), manual_path))
                      for _ in CATALOG_BUTTONS]
                ],
                inputs=[catalog_file_input, catalog_input],
                outputs=[catalog_input, *CATALOG_BUTTONS],
            )

            # Callbacks dos botões individuais
            extract_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Extração do catálogo Lightroom"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["extract"]),
                    gr.State(None),
                ],
                outputs=[log_output, log_file_output, summary_table, summary_overall, extract_btn],
            )

            identify_presets_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Identificação de Presets e Deltas"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["identify_presets"]),
                    gr.State(None),
                ],
                outputs=[log_output, log_file_output, summary_table, summary_overall, identify_presets_btn],
            )

            extract_features_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Extração de Features (Estatísticas e Deep)"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["extract_features"]),
                    gr.State(None),
                ],
                outputs=[log_output, log_file_output, summary_table, summary_overall, extract_features_btn],
            )

            prepare_data_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Preparação de Dados de Treino"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["prepare_data"]),
                    gr.State(None),
                ],
                outputs=[log_output, log_file_output, summary_table, summary_overall, prepare_data_btn],
            )

            train_classifier_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Treinar Classificador de Presets"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["train_classifier"]),
                    gr.State(None),
                ],
                outputs=[log_output, log_file_output, summary_table, summary_overall, train_classifier_btn],
            )

            train_regressor_btn.click(
                fn=run_training_step,
                inputs=[
                    gr.State("Treinar Refinador de Ajustes"),
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    batch_size_slider,
                    patience_input,
                    stat_noise_input,
                    deep_dropout_input,
                    mixup_alpha_input,
                    clf_wd_input,
                    ref_wd_input,
                    width_factor_input,
                    param_importance_input,
                    gr.State(BUTTON_LABELS["train_regressor"]),
                    gr.State("parse_mae_summary"),
                ],
                outputs=[log_output, log_file_output, summary_table, summary_overall, train_regressor_btn],
            )

        # Tab 3: Estatísticas do Dataset (NOVA)
        with gr.Tab("📊 Estatísticas do Dataset"):
            gr.Markdown("""
                Analise a qualidade e características do seu dataset antes do treino.

                **Métricas incluídas:**
                - Tamanho total e número de features
                - Distribuição de presets
                - Balanceamento de classes
                - Completude dos dados
                - Diversidade das imagens
                - Recomendações de treino
            """)

            with gr.Row():
                stats_catalog_input = gr.Textbox(
                    label="Caminho do Catálogo ou Dataset CSV",
                    value=str(OUTPUT_DATASET_PATH),
                    interactive=True
                )
            compute_stats_btn = gr.Button("🔄 Calcular Estatísticas", variant="primary")
            reset_stats_btn = gr.Button("↩︎ Limpar dataset/estatísticas gerados", variant="secondary")

            # Botão de análise de qualidade
            analyze_quality_btn = gr.Button("🔍 Analisar Qualidade do Dataset", variant="secondary", size="lg")

            with gr.Row():
                with gr.Column(scale=1):
                    stats_summary = gr.Textbox(
                        label="📋 Resumo das Estatísticas",
                        lines=25,
                        interactive=False,
                    )

                with gr.Column(scale=1):
                    stats_plot = gr.Plot(
                        label="📊 Distribuição de Presets"
                    )

            # Relatório de qualidade
            quality_report = gr.Markdown(
                label="🎯 Relatório de Qualidade",
                value="Clique em 'Analisar Qualidade do Dataset' para ver o relatório completo"
            )

            # Seção de Recomendações de Hiperparâmetros
            gr.Markdown("---")
            gr.Markdown("### 🎯 Recomendações Automáticas de Hiperparâmetros")

            with gr.Row():
                hyperparam_model_type = gr.Dropdown(
                    choices=["classifier", "regressor", "clip", "culling"],
                    value="classifier",
                    label="Tipo de Modelo",
                    info="Selecione o tipo de treino para ver os hiperparâmetros recomendados"
                )
                get_recommendations_btn = gr.Button("🎯 Obter Recomendações", variant="primary")

            hyperparam_report = gr.Markdown(
                label="📋 Recomendações",
                value="Selecione o tipo de modelo e clique em 'Obter Recomendações'"
            )

            hyperparam_json = gr.JSON(
                label="⚙️ Hiperparâmetros (JSON)",
                visible=False
            )

            stats_json = gr.JSON(
                label="📄 Relatório Completo (JSON)",
            )

            # Callback para calcular estatísticas
            compute_stats_btn.click(
                fn=compute_dataset_statistics,
                inputs=[stats_catalog_input],
                outputs=[stats_summary, stats_plot, stats_json],
            )

            reset_stats_btn.click(
                fn=reset_dataset_outputs,
                inputs=[],
                outputs=[stats_summary],
            )

            # Callback para analisar qualidade do dataset
            analyze_quality_btn.click(
                fn=analyze_dataset_quality,
                inputs=[stats_catalog_input],
                outputs=[quality_report],
            )

            # Callback para obter recomendações de hiperparâmetros
            get_recommendations_btn.click(
                fn=get_hyperparameter_recommendations,
                inputs=[stats_catalog_input, hyperparam_model_type],
                outputs=[hyperparam_report, hyperparam_json],
            )

            # Atualizar automaticamente quando dataset for extraído
            catalog_input.change(
                fn=lambda x: str(OUTPUT_DATASET_PATH),
                inputs=[catalog_input],
                outputs=[stats_catalog_input],
            )

        # Tab 4: Scene Classification
        with gr.Tab("🎬 Scene Classification"):
            gr.Markdown("""
                Classifica automaticamente imagens em categorias de cena usando CLIP.

                **Categorias disponíveis:**
                - Portrait (Retratos)
                - Landscape (Paisagens)
                - Urban (Urbano/Arquitetura)
                - Food (Comida)
                - Product (Produto)
                - Wildlife (Vida Selvagem)
                - Event (Eventos)
                - Sports (Desporto)
                - Abstract (Abstrato)
                - Night (Noturna)

                **Use cases:**
                - Organizar fotos automaticamente
                - Aplicar presets específicos por tipo de cena
                - Balancear dataset por diversidade
            """)

            with gr.Row():
                scene_dataset_input = gr.Textbox(
                    label="Dataset CSV",
                    value=str(OUTPUT_DATASET_PATH),
                    interactive=True
                )

            with gr.Row():
                scene_output_path = gr.Textbox(
                    label="Output CSV (com scene tags)",
                    value="data/lightroom_dataset_with_scenes.csv",
                    interactive=True
                )

            with gr.Row():
                scene_top_k = gr.Slider(
                    minimum=1,
                    maximum=3,
                    value=1,
                    step=1,
                    label="Top K categorias por imagem",
                    info="Quantas categorias adicionar a cada imagem"
                )

            classify_scenes_btn = gr.Button("🎬 Classificar Cenas", variant="primary", size="lg")

            scene_output = gr.Markdown(label="Resultados")

            scene_distribution_plot = gr.Plot(label="📊 Distribuição de Cenas")

        # Tab 5: Duplicate Detection
        with gr.Tab("🔍 Duplicate Detection"):
            gr.Markdown("""
                Detecta e remove fotos duplicadas ou muito similares usando perceptual hashing.

                **Métodos disponíveis:**
                - Average Hash (rápido, bom para redimensionamentos)
                - Perceptual Hash (melhor para rotações/cores)
                - Difference Hash (bom para gradientes)
                - Wavelet Hash (melhor para alterações sutis)

                **Thresholds:**
                - 0 = Apenas idênticas
                - 5 = Muito similares (recomendado)
                - 10 = Similares
                - 15 = Parecidas
            """)

            with gr.Row():
                dup_dataset_input = gr.Textbox(
                    label="Dataset CSV",
                    value=str(OUTPUT_DATASET_PATH),
                    interactive=True
                )

            with gr.Row():
                dup_method = gr.Dropdown(
                    choices=["average", "perceptual", "difference", "wavelet"],
                    value="average",
                    label="Método de Hashing"
                )

                dup_threshold = gr.Slider(
                    minimum=0,
                    maximum=20,
                    value=5,
                    step=1,
                    label="Threshold de Similaridade",
                    info="Menor = mais restritivo"
                )

            with gr.Row():
                detect_only_checkbox = gr.Checkbox(
                    label="Apenas detectar (não remover)",
                    value=True,
                    info="Se desmarcado, cria dataset limpo sem duplicatas"
                )

            with gr.Row():
                dup_output_path = gr.Textbox(
                    label="Output CSV (dataset limpo)",
                    value="data/lightroom_dataset_clean.csv",
                    interactive=True,
                    visible=False
                )

            detect_duplicates_btn = gr.Button("🔍 Detectar Duplicatas", variant="primary", size="lg")

            dup_output = gr.Markdown(label="Resultados")

            dup_report_html = gr.HTML(label="Relatório Visual")

            # Mostrar/ocultar output path baseado no checkbox
            detect_only_checkbox.change(
                fn=lambda x: gr.update(visible=not x),
                inputs=[detect_only_checkbox],
                outputs=[dup_output_path]
            )

            # Callback para classificar cenas
            classify_scenes_btn.click(
                fn=classify_scenes,
                inputs=[scene_dataset_input, scene_output_path, scene_top_k],
                outputs=[scene_output, scene_distribution_plot]
            )

            # Callback para detectar duplicatas
            detect_duplicates_btn.click(
                fn=detect_duplicates,
                inputs=[dup_dataset_input, dup_method, dup_threshold, detect_only_checkbox, dup_output_path],
                outputs=[dup_output, dup_report_html]
            )

        # Tab 6: Servidor FastAPI
        with gr.Tab("🌐 Servidor FastAPI"):
            gr.Markdown("""
                Controle o servidor FastAPI que serve os modelos treinados ao plugin Lightroom.

                **Endpoints disponíveis:**
                - `POST /predict` - Predição de ajustes para imagem
                - `GET /health` - Status do servidor
                - `GET /docs` - Documentação interativa da API

                ---

                **URL do Servidor:** http://127.0.0.1:5678

                **Documentação Interativa:** http://127.0.0.1:5678/docs

                Configure este URL nas preferências do plugin Lightroom.
            """)

            with gr.Row():
                start_server_button = gr.Button(
                    "▶️ Iniciar Servidor",
                    variant="primary",
                    size="lg"
                )
                stop_server_button = gr.Button(
                    "⏹️ Parar Servidor",
                    variant="stop",
                    size="lg"
                )

            server_status = gr.Textbox(
                label="Status",
                interactive=False,
                value="⏹️ Parado"
            )

            server_logs = gr.Textbox(
                label="📋 Logs do Servidor (Tempo Real)",
                lines=25,
                interactive=False,
                autoscroll=True
            )

            # Callbacks
            start_server_button.click(
                fn=start_fastapi_server,
                inputs=[],
                outputs=[server_logs, server_status]
            )

            stop_server_button.click(
                fn=stop_fastapi_server,
                inputs=[],
                outputs=[server_status]
            )

        # Tab 5: Transfer Learning
        with gr.Tab("🎓 Transfer Learning"):
            gr.Markdown("""
                ## Transfer Learning - Treino com Datasets Pequenos

                **Quando usar Transfer Learning?**

                ✅ **USE quando:**
                - Tens menos de 200 fotos editadas
                - Dataset muito pequeno (< 50 fotos) com overfitting severo
                - Queres accuracy 80-85% com apenas 50 fotos
                - Precisas de treino mais rápido (15-30 minutos vs 1-2 horas)

                ❌ **NÃO USE quando:**
                - Tens dataset grande (> 500 fotos bem balanceadas)
                - Pipeline normal já dá bons resultados (> 75% accuracy)
                - Não tens GPU (Transfer Learning é mais lento em CPU)

                ---

                **Modelos Disponíveis:**

                | Modelo | Melhor Para | Dataset Mínimo | Accuracy Esperada | Velocidade |
                |--------|-------------|----------------|-------------------|------------|
                | **CLIP** | Compreensão semântica, estilos diversos | 50 fotos | 80-85% | Rápido |
                | **DINOv2** | Qualidade técnica, detalhes | 75 fotos | 75-80% | Médio |
                | **ConvNeXt** | Balanço entre os dois | 100 fotos | 78-83% | Lento |

                ---

                **Resultados Esperados:**

                - Com **50 fotos**: ~80% accuracy (vs ~45% no pipeline normal)
                - Com **100 fotos**: ~85% accuracy (vs ~60% no pipeline normal)
                - Com **200 fotos**: ~88% accuracy (vs ~70% no pipeline normal)

                💡 **Recomendação**: Comece com CLIP e 30 épocas.
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Configurações")

                    tl_model_type = gr.Dropdown(
                        label="Modelo Base",
                        choices=["clip", "dinov2", "convnext"],
                        value="clip",
                        info="CLIP é o mais recomendado para datasets pequenos"
                    )

                    tl_epochs = gr.Slider(
                        label="Épocas",
                        minimum=10,
                        maximum=100,
                        step=5,
                        value=30,
                        info="30-50 épocas são suficientes com Transfer Learning"
                    )

                    tl_batch_size = gr.Slider(
                        label="Batch Size",
                        minimum=4,
                        maximum=32,
                        step=4,
                        value=16,
                        info="Reduza se tiver pouca memória GPU"
                    )

                    tl_lr = gr.Slider(
                        label="Learning Rate",
                        minimum=1e-5,
                        maximum=1e-2,
                        step=1e-5,
                        value=1e-3,
                        info="1e-3 é um bom padrão para Transfer Learning"
                    )

                    tl_attention = gr.Checkbox(
                        label="Usar Mecanismos de Atenção",
                        value=True,
                        info="Melhora accuracy mas aumenta tempo de treino"
                    )

                    tl_patience = gr.Slider(
                        label="Paciência (Early Stopping)",
                        minimum=5,
                        maximum=20,
                        step=1,
                        value=10,
                        info="Número de épocas sem melhoria antes de parar"
                    )

                    tl_train_btn = gr.Button(
                        "🚀 Iniciar Transfer Learning",
                        variant="primary",
                        size="lg"
                    )

                with gr.Column(scale=2):
                    gr.Markdown("### 📋 Logs e Progresso")

                    tl_logs = gr.Textbox(
                        label="Logs do Treino",
                        lines=25,
                        interactive=False,
                        autoscroll=True
                    )

                    tl_log_file = gr.File(
                        label="💾 Transferir Log Completo",
                        interactive=False
                    )

                    tl_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Pronto para começar"
                    )

            # Callback Transfer Learning
            tl_train_btn.click(
                fn=run_transfer_learning,
                inputs=[
                    tl_model_type,
                    tl_epochs,
                    tl_batch_size,
                    tl_lr,
                    tl_attention,
                    tl_patience,
                ],
                outputs=[tl_logs, tl_log_file, tl_status]
            )

            gr.Markdown("""
                ---
                📚 **Documentação Completa:**
                - `TRANSFER_LEARNING_GUIDE.md` - Guia técnico detalhado
                - `TRANSFER_LEARNING_QUICKSTART.md` - Quick start prático
            """)

        # Tab 6: Smart Culling
        with gr.Tab("⭐ Smart Culling"):
            gr.Markdown("""
                ## Smart Culling - Avaliação Automática de Qualidade

                **Quando usar Smart Culling?**

                ✅ **USE quando:**
                - Tens milhares de fotos para selecionar
                - Queres automatizar a seleção inicial de fotos
                - Precisas de avaliar qualidade técnica (nitidez, exposição, composição)
                - Queres economizar tempo na fase de culling

                ❌ **NÃO USE quando:**
                - Tens poucas fotos (< 100)
                - Queres avaliação subjetiva/artística pura
                - Não tens exemplos de fotos boas/más no teu catálogo

                ---

                **Opções de Dataset:**

                | Dataset | Quando Usar | Fotos Necessárias | Accuracy Esperada | Tempo de Treino |
                |---------|-------------|-------------------|-------------------|-----------------|
                | **Lightroom** | Tens fotos com ratings no catálogo | 200+ | 70-75% | 30-60 min |
                | **AVA** | Não tens ratings, queres modelo genérico | 0 (usa dataset público) | 85%+ | 2-3 horas |

                ---

                **Como Funciona:**

                1. **Lightroom**: Usa ratings (⭐) das tuas fotos como labels
                   - ⭐⭐⭐⭐⭐ = Excelente (1.0)
                   - ⭐⭐⭐⭐ = Muito Boa (0.8)
                   - ⭐⭐⭐ = Boa (0.6)
                   - ⭐⭐ ou ⭐ = Razoável/Fraca (0.2-0.4)

                2. **AVA**: Usa 250,000 fotos profissionalmente avaliadas
                   - Aprende critérios estéticos universais
                   - Mais genérico mas muito robusto

                💡 **Recomendação**:
                - Se tens ratings: Use dataset Lightroom
                - Se não tens ratings: Faça download do AVA primeiro
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Configurações")

                    culling_dataset_type = gr.Radio(
                        label="Tipo de Dataset",
                        choices=["lightroom", "ava"],
                        value="lightroom",
                        info="Lightroom usa os teus ratings; AVA usa dataset público"
                    )

                    # Download AVA (só aparece se dataset=AVA)
                    with gr.Group(visible=False) as ava_download_group:
                        gr.Markdown("#### 📥 Download do Dataset AVA")
                        ava_num_images = gr.Slider(
                            label="Número de Imagens a Fazer Download",
                            minimum=100,
                            maximum=5000,
                            step=100,
                            value=1000,
                            info="1000 imagens ≈ 2GB, suficiente para treino robusto"
                        )
                        ava_download_btn = gr.Button("📥 Fazer Download do AVA", variant="secondary")
                        ava_download_status = gr.Textbox(
                            label="Status do Download",
                            interactive=False,
                            lines=5
                        )

                    culling_epochs = gr.Slider(
                        label="Épocas",
                        minimum=20,
                        maximum=100,
                        step=5,
                        value=50,
                        info="50-70 épocas são suficientes"
                    )

                    culling_batch_size = gr.Slider(
                        label="Batch Size",
                        minimum=8,
                        maximum=64,
                        step=8,
                        value=32,
                        info="32 é um bom padrão"
                    )

                    culling_lr = gr.Slider(
                        label="Learning Rate",
                        minimum=1e-5,
                        maximum=1e-3,
                        step=1e-5,
                        value=1e-4,
                        info="1e-4 funciona bem com DINOv2"
                    )

                    culling_patience = gr.Slider(
                        label="Paciência (Early Stopping)",
                        minimum=5,
                        maximum=20,
                        step=1,
                        value=10
                    )

                    culling_train_btn = gr.Button(
                        "🚀 Iniciar Treino de Culling",
                        variant="primary",
                        size="lg"
                    )

                with gr.Column(scale=2):
                    gr.Markdown("### 📋 Logs e Progresso")

                    culling_logs = gr.Textbox(
                        label="Logs do Treino",
                        lines=25,
                        interactive=False,
                        autoscroll=True
                    )

                    culling_log_file = gr.File(
                        label="💾 Transferir Log Completo",
                        interactive=False
                    )

                    culling_status = gr.Textbox(
                        label="Status",
                        interactive=False,
                        value="Pronto para começar"
                    )

            # Mostrar/esconder grupo AVA baseado na escolha
            def toggle_ava_group(dataset_type):
                return gr.update(visible=(dataset_type == "ava"))

            culling_dataset_type.change(
                fn=toggle_ava_group,
                inputs=[culling_dataset_type],
                outputs=[ava_download_group]
            )

            # Callback Download AVA
            ava_download_btn.click(
                fn=download_ava_dataset,
                inputs=[ava_num_images],
                outputs=[ava_download_status, ava_download_status]
            )

            # Callback Treino Culling
            culling_train_btn.click(
                fn=run_culling_training,
                inputs=[
                    culling_dataset_type,
                    ava_num_images,
                    culling_epochs,
                    culling_batch_size,
                    culling_lr,
                    culling_patience,
                ],
                outputs=[culling_logs, culling_log_file, culling_status]
            )

            gr.Markdown("""
                ---
                📚 **Uso do Modelo Treinado:**

                Após o treino, o modelo será salvo em `models/dinov2_culling_model.pth`.

                **Como usar:**

                ```python
                from services.culling import CullingPredictor

                predictor = CullingPredictor()
                score = predictor.predict_quality("path/to/image.jpg")

                if score >= 0.9:
                    print("⭐⭐⭐ Excelente!")
                elif score >= 0.75:
                    print("⭐⭐ Muito Boa")
                elif score >= 0.6:
                    print("⭐ Boa")
                else:
                    print("Razoável/Fraca")
                ```

                💡 **Integração futura**: Este modelo será integrado no plugin Lightroom para culling automático.
            """)

    # Footer
    gr.Markdown("""
        ---
        💡 **Dicas:**
        - Ajusta batch/épocas conforme o tamanho do dataset (batch ↑ se tens memória, ↓ se estás limitado; épocas ↓ se quiseres treino mais rápido)
        - Abre "Estatísticas do Dataset" antes de treinar; se aparecer aviso, corre primeiro a extração do catálogo (gera `data/lightroom_dataset.csv`)
        - Pesos de importância dão mais penalização a sliders críticos (exposição/cor). Para looks suaves, baixa esses pesos; para cor/exposição mais assertivas, sobe-os ligeiramente.
        - `patience` controla o early stopping: valores mais baixos param cedo para evitar overfitting, valores mais altos deixam treinar mais tempo.
    """)


if __name__ == "__main__":
    iface.queue().launch(
        server_name="127.0.0.1",
        share=False,
        show_error=True,
        inbrowser=True
    )
