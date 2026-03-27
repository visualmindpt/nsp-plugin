import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import gradio as gr
from slider_config import ALL_SLIDERS

# --- Configuration ---
APP_ROOT = Path(__file__).resolve().parent
_PYTHON_BIN_CACHE: Optional[str] = None
_PYTHON_CANDIDATES = [
    APP_ROOT / "venv" / "bin" / "python3",
    APP_ROOT / "venv" / "bin" / "python",
    APP_ROOT / "venv" / "Scripts" / "python.exe",
    APP_ROOT / "venv" / "Scripts" / "python3.exe",
    APP_ROOT / ".venv" / "bin" / "python3",
    APP_ROOT / ".venv" / "Scripts" / "python.exe",
]

def resolve_python_binary() -> str:
    """Deteta o executável Python mais adequado para correr os scripts do pipeline."""
    global _PYTHON_BIN_CACHE
    if _PYTHON_BIN_CACHE and Path(_PYTHON_BIN_CACHE).exists():
        return _PYTHON_BIN_CACHE

    env_hint = os.environ.get("NSP_PYTHON")
    candidates = []
    if env_hint:
        candidates.append(Path(env_hint))
    candidates.append(Path(sys.executable))
    candidates.extend(_PYTHON_CANDIDATES)
    candidates.append(Path("python3"))
    candidates.append(Path("python"))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            expanded = candidate.expanduser()
        except AttributeError:
            expanded = Path(str(candidate))
        if expanded.is_file() or shutil.which(str(expanded)):
            _PYTHON_BIN_CACHE = str(expanded)
            return _PYTHON_BIN_CACHE

    _PYTHON_BIN_CACHE = "python3"
    return _PYTHON_BIN_CACHE


EXTRACT_SCRIPT = APP_ROOT / "tools" / "extract_from_lrcat.py"
CULLING_SCRIPT = APP_ROOT / "tools" / "run_culling.py"
EMBED_SCRIPT = APP_ROOT / "tools" / "generate_real_embeddings.py"
PCA_SCRIPT = APP_ROOT / "tools" / "prepare_features.py"
RETRAIN_FEEDBACK_SCRIPT = APP_ROOT / "train" / "retrain_from_feedback.py"
NN_TRAIN_SCRIPT = APP_ROOT / "train" / "ann" / "train_nn.py"
NN_EVAL_SCRIPT = APP_ROOT / "train" / "ann" / "evaluate_nn.py"
LOG_DIR = APP_ROOT / "logs"
SLIDER_MAE_RE = re.compile(r"Slider '([^']+)': MAE = ([0-9]+\.[0-9]+|[0-9]+)")
OVERALL_MAE_RE = re.compile(r"Overall Mean Absolute Error.*?([0-9]+\.[0-9]+|[0-9]+)")
CATALOG_BUTTONS: List[gr.Button] = []
GLOBAL_ORDERED_MAE_DISPLAYS: List[gr.Textbox] = []


# --- Helpers ---
def create_log_file(prefix: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return LOG_DIR / f"{prefix}_{timestamp}.log"


def append_log_line(log_path: Optional[Path], text: str) -> None:
    if not log_path:
        return
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text + ("\n" if not text.endswith("\n") else ""))


def _catalog_from_file(file_path: Optional[str]) -> str:
    return file_path or ""


def _has_catalog_path(manual_path: Optional[str], uploaded_path: Optional[str]) -> bool:
    if manual_path and manual_path.strip():
        return True
    return bool(uploaded_path)


def _catalog_button_updates(manual_path: Optional[str], uploaded_path: Optional[str]) -> List[object]:
    has_catalog = _has_catalog_path(manual_path, uploaded_path)
    return [gr.update(interactive=has_catalog) for _ in CATALOG_BUTTONS]


def parse_mae_summary(lines: List[str], model_label: str) -> Tuple[Optional[List[List[object]]], Optional[str]]:
    rows: List[List[object]] = []
    overall_value: Optional[str] = None
    
    global slider_mae_values # Access the global dictionary
    current_mae_results = {} # Temporarily store results for this evaluation

    for line in lines:
        slider_match = SLIDER_MAE_RE.search(line)
        if slider_match:
            slider_name = slider_match.group(1)
            mae_value = float(slider_match.group(2))
            rows.append([model_label, slider_name, mae_value])
            current_mae_results[slider_name] = mae_value # Store for global update
        else:
            overall_match = OVERALL_MAE_RE.search(line)
            if overall_match:
                overall_value = f"{model_label} Overall MAE: {overall_match.group(1)}"
    
    # Update the global dictionary with the latest results
    slider_mae_values.update(current_mae_results)

    if rows:
        return rows, overall_value
    return None, None


slider_mae_values = {} # Global dictionary to store the last MAE values for each slider

def create_slider_config_ui():
    """Dynamically creates Gradio slider components for all defined sliders."""
    categorized_sliders = {}
    for slider in ALL_SLIDERS:
        category = slider["category"]
        if category not in categorized_sliders:
            categorized_sliders[category] = []
        categorized_sliders[category].append(slider)

    slider_components = {} # To store references to Gradio components for updating
    ordered_mae_displays = [] # To store references to Textbox components for MAE in order

    global GLOBAL_ORDERED_MAE_DISPLAYS
    GLOBAL_ORDERED_MAE_DISPLAYS = ordered_mae_displays # Assign to global variable

    with gr.Column():
        gr.Markdown("### Visualização e Análise de Sliders")
        for category, sliders in categorized_sliders.items():
            with gr.Accordion(label=category, open=False):
                for slider in sliders:
                    with gr.Row():
                        gr.Markdown(f"**{slider['python_name'].replace('_', ' ').title()}** (`{slider['lr_key']}`)")
                        
                        # Slider for manual adjustment/visualization
                        slider_comp = gr.Slider(
                            minimum=slider.get("min", -100),
                            maximum=slider.get("max", 100),
                            step=slider.get("step", 1),
                            value=0, # Default value
                            label="Valor",
                            interactive=True, # Allow manual adjustment for testing
                            elem_id=f"slider_{slider['python_name']}"
                        )
                        
                        # Textbox to display MAE for this specific slider
                        mae_display = gr.Textbox(
                            label="MAE",
                            value="N/A",
                            interactive=False,
                            scale=3, # Changed from 0.3 to 3 (integer)
                            elem_id=f"mae_{slider['python_name']}"
                        )
                        
                        slider_components[slider["python_name"]] = slider_comp
                        ordered_mae_displays.append(mae_display)
    return slider_components, ordered_mae_displays

def update_slider_mae_displays(mae_data: Optional[List[List[object]]], ordered_mae_displays: List[gr.Textbox]):
    """Updates the MAE display textboxes for each slider."""
    updates = []
    
    # Initialize all updates to "N/A"
    for _ in ordered_mae_displays:
        updates.append(gr.update(value="N/A"))

    if mae_data is not None:
        # Update global state for later use
        global slider_mae_values
        slider_mae_values = {row[1]: row[2] for row in mae_data}

        # Create a mapping from slider_name to its index in the ordered list
        slider_name_to_index = {
            slider["python_name"]: i for i, slider in enumerate(ALL_SLIDERS)
        }

        # Populate updates list with actual MAE values
        for slider_name, mae_value in slider_mae_values.items():
            if slider_name in slider_name_to_index:
                index = slider_name_to_index[slider_name]
                updates[index] = gr.update(value=f"{mae_value:.2f}")
    
    return updates

def load_last_mae_into_sliders(slider_components_dict: dict):
    """Loads the last recorded MAE values into the slider components for visualization."""
    updates = {}
    for slider_name, mae_value in slider_mae_values.items():
        if slider_name in slider_components_dict:
            # Set slider value to MAE for visualization.
            # Note: MAE is always positive, so we might want to show it as an absolute value
            # or consider a different visualization if the slider represents a range.
            # For now, setting the slider value to MAE itself might be confusing.
            # A better approach might be to have a separate visualization for MAE,
            # or to use the slider to represent a *predicted* value, not an error.
            # For this task, let's just set the value to 0 and update the MAE textbox.
            # The slider itself is for manual interaction/testing.
            updates[slider_components_dict[slider_name]] = gr.update(value=0) # Reset slider value
    return updates


BUTTON_LABELS = {
    "pipeline": {
        "idle": "Executar pipeline completo",
        "running": "A executar pipeline...",
        "error": "Tentar novamente o pipeline",
    },
    "extract": {
        "idle": "1. Extrair dados do catálogo",
        "running": "A extrair dados do catálogo...",
        "error": "Repetir extração",
    },
    "culling": {
        "idle": "2. Aplicar culling",
        "running": "A aplicar culling...",
        "error": "Repetir culling",
    },
    "embeddings": {
        "idle": "3. Gerar embeddings",
        "running": "A gerar embeddings...",
        "error": "Repetir geração de embeddings",
    },
    "pca": {
        "idle": "4. Preparar PCA",
        "running": "A preparar PCA...",
        "error": "Repetir preparação PCA",
    },
    "retrain_feedback": {
        "idle": "7. Re-treinar com feedback novo",
        "running": "A re-treinar com feedback...",
        "error": "Repetir re-treino",
    },
    "train_nn": {
        "idle": "8. Treinar Rede Neural",
        "running": "A treinar Rede Neural...",
        "error": "Repetir treino da Rede Neural",
    },
    "eval_nn": {
        "idle": "9. Avaliar Rede Neural",
        "running": "A avaliar Rede Neural...",
        "error": "Repetir avaliação da Rede Neural",
    },
}

def run_script(
    script_path: Path,
    args: List[str],
    description: str,
    collector: List[str],
    log_path: Optional[Path],
    summary_parser=None,
    button_labels: Optional[dict] = None,
    keep_button_running: bool = False,
) -> Iterable[Tuple[str, object, object, object, object]]:
    """Run a script from the virtual environment and stream its output."""
    local_lines: List[str] = []
    header = f"--- {description} ---"
    collector.append(header)
    local_lines.append(header)
    append_log_line(log_path, header)
    python_bin = resolve_python_binary()
    python_label = f"Python: {python_bin}"
    collector.append(python_label)
    local_lines.append(python_label)
    append_log_line(log_path, python_label)

    def button_update(label: Optional[str] = None, interactive: Optional[bool] = None):
        if button_labels is None:
            return gr.update()
        update_kwargs = {}
        if label is not None:
            update_kwargs["value"] = label
        if interactive is not None:
            update_kwargs["interactive"] = interactive
        return gr.update(**update_kwargs)

    yield (
        "\n".join(collector),
        gr.update(value=None),
        gr.update(value=None),
        gr.update(value=None),
        button_update(button_labels.get("running") if button_labels else None, False),
    )

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    command = [python_bin, "-u", str(script_path)] + args

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    for line in iter(process.stdout.readline, ""):
        clean_line = line.rstrip("\n")
        collector.append(clean_line)
        local_lines.append(clean_line)
        append_log_line(log_path, clean_line)
        yield (
            "\n".join(collector),
            gr.update(value=None),
            gr.update(value=None),
            gr.update(value=None),
            button_update(None, False),
        )

    process.wait()
    footer = f"--- End of {description} ---"
    collector.append(footer)
    local_lines.append(footer)
    append_log_line(log_path, footer)
    summary_data = None
    summary_text = None
    if summary_parser:
        summary_data, summary_text = summary_parser(local_lines)

    if button_labels:
        if process.returncode != 0:
            final_label = button_labels.get("error", button_labels.get("idle"))
        elif keep_button_running:
            final_label = button_labels.get("running")
        else:
            final_label = button_labels.get("idle")
    else:
        final_label = None

    yield (
        "\n".join(collector),
        gr.update(value=str(log_path) if log_path else None),
        gr.update(value=summary_data),
        gr.update(value=summary_text),
        button_update(final_label, True),
    )
    if process.returncode != 0:
        raise gr.Error(f"Ocorreu um erro em: {description}. Consulta os logs acima.")





def handle_manual_catalog_change(manual_path: Optional[str], uploaded_path: Optional[str]):
    return _catalog_button_updates(manual_path, uploaded_path)


def handle_catalog_file_selection(uploaded_file_obj, manual_path: Optional[str]):
    uploaded_path_str = uploaded_file_obj.name if uploaded_file_obj and hasattr(uploaded_file_obj, 'name') else ""
    manual_path_str = (manual_path or "").strip()
    resolved_path = uploaded_path_str or manual_path_str
    updates = _catalog_button_updates(resolved_path, uploaded_path_str)
    return [gr.update(value=resolved_path), *updates]


def run_extract(
    catalog_path: str,
    overwrite: bool,
    skip_missing: bool,
    limit: Optional[float],
) -> Iterable[Tuple[str, object, object, object, object]]:
    path = _require_catalog_path(catalog_path)
    args: List[str] = ["--catalog_path", path]
    if overwrite:
        args.append("--overwrite")
    if skip_missing:
        args.append("--skip-missing-images")
    if limit and limit > 0:
        args.extend(["--limit", str(int(limit))])
    log_path = create_log_file("extract")
    collector: List[str] = []
    yield from run_script(
        EXTRACT_SCRIPT,
        args,
        "Extração do catálogo Lightroom",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["extract"],
    )


def run_culling_step(threshold: float, limit: Optional[float]) -> Iterable[Tuple[str, object, object, object, object]]:
    if threshold <= 0 or threshold >= 1:
        raise gr.Error("Define um limiar de culling entre 0 e 1.")
    args: List[str] = ["--threshold", f"{threshold:.4f}", "--overwrite"]
    if limit and limit > 0:
        args.extend(["--limit", str(int(limit))])
    log_path = create_log_file("culling")
    collector: List[str] = []
    yield from run_script(
        CULLING_SCRIPT,
        args,
        "Culling automático das imagens extraídas",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["culling"],
    )


def run_embeddings(use_culling: bool, batch_size: int) -> Iterable[Tuple[str, object, object, object, object]]:
    log_path = create_log_file("embeddings")
    collector: List[str] = []
    args: List[str] = [f"--batch-size", str(int(batch_size))]
    if use_culling:
        args.append("--use-culling")
    
    yield from run_script(
        EMBED_SCRIPT,
        args,
        "Geração de embeddings com CLIP",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["embeddings"],
    )


def run_prepare_features(
    pca_components: float,
) -> Iterable[Tuple[str, object, object, object, object]]:
    if not pca_components or pca_components < 1:
        raise gr.Error("Escolhe pelo menos 1 componente de PCA.")
    args = ["--pca-components", str(int(pca_components))]
    log_path = create_log_file("pca")
    collector: List[str] = []
    description = f"Preparação de features (PCA = {int(pca_components)})"
    yield from run_script(
        PCA_SCRIPT,
        args,
        description,
        collector,
        log_path,
        button_labels=BUTTON_LABELS["pca"],
    )


def run_retrain_feedback() -> Iterable[Tuple[str, object, object, object, object]]:
    log_path = create_log_file("retrain_feedback")
    collector: List[str] = []
    yield from run_script(
        RETRAIN_FEEDBACK_SCRIPT,
        [],
        "Re-treino com feedback registado",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["retrain_feedback"],
    )


def run_train_nn() -> Iterable[Tuple[str, object, object, object, object]]:
    log_path = create_log_file("train_nn")
    collector: List[str] = []
    yield from run_script(
        NN_TRAIN_SCRIPT,
        [],
        "Treino da Rede Neural",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["train_nn"],
    )


def run_eval_nn() -> Iterable[Tuple[str, object, object, object, object]]:
    log_path = create_log_file("evaluate_nn")
    collector: List[str] = []
    yield from run_script(
        NN_EVAL_SCRIPT,
        [],
        "Avaliação da Rede Neural",
        collector,
        log_path,
        summary_parser=parse_mae_summary, # Changed from parse_nn_summary to parse_mae_summary
        button_labels=BUTTON_LABELS["eval_nn"],
    )


def run_full_pipeline(
    catalog_path: str,
    overwrite: bool,
    skip_missing: bool,
    limit: Optional[float],
    apply_culling: bool,
    culling_threshold: float,
    pca_components: float,
    batch_size: int,
    include_nn: bool,
    include_nn_eval: bool,
    num_presets: int,
    min_rating: int,
    classifier_epochs: int,
    refiner_epochs: int,
    patience: int,
    param_importance: str, # Received as JSON string
) -> Iterable[Tuple[str, object, object, object, object]]:
    log_path = create_log_file("pipeline")
    collector: List[str] = []
    summary_rows: List[List[object]] = []
    summary_texts: List[str] = []
    catalog_resolved = _require_catalog_path(catalog_path)

    # Arguments for train/train_models_v2.py
    train_models_args = [
        "--catalog_path", catalog_resolved,
        "--num_presets", str(num_presets),
        "--min_rating", str(min_rating),
        "--classifier_epochs", str(classifier_epochs),
        "--refiner_epochs", str(refiner_epochs),
        "--patience", str(patience),
        "--param_importance", param_importance, # Pass as JSON string
    ]

    def summary_parser_factory(label: str):
        def parser(local_lines: List[str]) -> Tuple[Optional[List[List[object]]], Optional[str]]:
            rows, overall = parse_mae_summary(local_lines, label)
            if rows:
                summary_rows.extend(rows)
            if overall:
                summary_texts.append(overall)
            combined_rows = summary_rows if summary_rows else None
            combined_text = "\n".join(summary_texts) if summary_texts else None
            return combined_rows, combined_text

        return parser

    limit_args = ["--limit", str(int(limit))] if limit and limit > 0 else []

    yield from run_script(
        EXTRACT_SCRIPT,
        ["--catalog_path", catalog_resolved]
        + (["--overwrite"] if overwrite else [])
        + (["--skip-missing-images"] if skip_missing else [])
        + limit_args,
        "Passo 1: Extração do catálogo Lightroom",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["pipeline"],
        keep_button_running=True,
    )

    culling_args: List[str] = []
    if apply_culling:
        threshold = max(0.01, min(0.99, culling_threshold))
        culling_args = ["--use-culling"]
        yield from run_script(
            CULLING_SCRIPT,
            ["--threshold", f"{threshold:.4f}", "--overwrite"] + limit_args,
            "Passo 2: Culling automático das imagens",
            collector,
            log_path,
            button_labels=BUTTON_LABELS["pipeline"],
            keep_button_running=True,
        )

    embedding_args = culling_args + [f"--batch-size", str(int(batch_size))]
    yield from run_script(
        EMBED_SCRIPT,
        embedding_args,
        "Passo 3: Geração de embeddings com CLIP",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["pipeline"],
        keep_button_running=True,
    )

    yield from run_script(
        PCA_SCRIPT,
        ["--pca-components", str(int(pca_components))],
        f"Passo 4: Preparação de features (PCA = {int(pca_components)})",
        collector,
        log_path,
        button_labels=BUTTON_LABELS["pipeline"],
        keep_button_running=True,
    )

    if include_nn:
        yield from run_script(
            NN_TRAIN_SCRIPT,
            train_models_args, # Pass all training parameters here
            "Passo 8: Treino da Rede Neural",
            collector,
            log_path,
            button_labels=BUTTON_LABELS["pipeline"],
            keep_button_running=True,
        )
        if include_nn_eval:
            yield from run_script(
                NN_EVAL_SCRIPT,
                [],
                "Passo 9: Avaliação da Rede Neural",
                collector,
                log_path,
                summary_parser=summary_parser_factory("Rede Neural"),
                button_labels=BUTTON_LABELS["pipeline"],
                keep_button_running=True,
            )

    conclusion = "--- PIPELINE COMPLETO FINALIZADO ---"
    collector.append(conclusion)
    append_log_line(log_path, conclusion)
    yield (
        "\n".join(collector),
        gr.update(value=str(log_path)),
        gr.update(value=summary_rows if summary_rows else None),
        gr.update(
            value="\n".join(summary_texts) if summary_texts else None
        ),
        gr.update(
            value=BUTTON_LABELS["pipeline"]["idle"],
            interactive=True,
        ),
    )


# --- Gradio UI ---
with gr.Blocks(css=".gradio-container {max-width: 100%; margin: auto; padding: 20px;}") as iface:
    gr.Markdown(
        "<h2 style='text-align: center;'>NSP Plugin — Treinador com Dados Reais</h2><p style='text-align: center;'>Executa todo o pipeline (extração, embeddings, PCA, treino e avaliação) com botões simples.</p>"
    )

    with gr.Row():
        with gr.Column(scale=1, min_width=320):
            catalog_file_input = gr.File(
                label="Arrasta ou seleciona o catálogo (.lrcat)",
                file_types=[".lrcat"],
                file_count="single",
                type="filepath",
            )
            catalog_input = gr.Textbox(
                label="Caminho completo do catálogo (.lrcat)",
                placeholder="/Users/teuuser/Pictures/Lightroom/Lightroom Catalog.lrcat",
            )
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
            culling_checkbox = gr.Checkbox(
                label="Aplicar culling automático antes dos embeddings",
                value=True,
            )
            culling_threshold = gr.Slider(
                label="Limiar de culling",
                minimum=0.1,
                maximum=0.9,
                step=0.05,
                value=0.4,
            )
            pca_slider = gr.Slider(
                label="Componentes PCA",
                minimum=1,
                maximum=512,
                step=1,
                value=256,
            )
            batch_size_slider = gr.Slider(
                label="Batch Size (Embeddings)",
                minimum=8,
                maximum=128,
                step=8,
                value=32,
                info="Valores mais altos são mais rápidos em GPUs potentes. Reduza se tiver pouca RAM/VRAM."
            )
            include_nn_checkbox = gr.Checkbox(
                label="Incluir treino da Rede Neural no pipeline completo",
                value=True, # Changed default to True
            )
            include_nn_eval_checkbox = gr.Checkbox(
                label="Avaliar Rede Neural após treino (só se a opção anterior estiver ativa)",
                value=True, # Changed default to True
            )
            gr.Markdown("### Configurações de Treino Avançadas")
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
            param_importance_input = gr.Textbox(
                label="Pesos de Importância dos Parâmetros (JSON)",
                value="""{
    "exposure": 2.0, "contrast": 1.5, "highlights": 1.8, "shadows": 1.8,
    "temperature": 2.0, "vibrance": 1.2, "clarity": 1.0, "whites": 1.3,
    "blacks": 1.3, "tint": 1.0, "saturation": 1.2, "dehaze": 0.8,
    "sharpness": 0.5, "noise_reduction": 0.5
}""",
                lines=10,
                interactive=True,
            )
        with gr.Column(scale=2):
            log_output = gr.Textbox(
                label="Logs do processo",
                lines=28,
                interactive=False,
                autoscroll=True,
            )
            log_file_output = gr.File(
                label="Transferir último log",
                interactive=False,
            )
            summary_table = gr.Dataframe(
                headers=["Modelo", "Slider", "MAE"],
                label="Resumo MAE (última avaliação)",
                interactive=False,
            )
            summary_overall = gr.Textbox(
                label="MAE global",
                interactive=False,
            )
            catalog_file_input.change(
                fn=_catalog_from_file,
                inputs=catalog_file_input,
                outputs=catalog_input,
            )

    with gr.Tabs():
        with gr.Tab("Pipeline completo"):
            start_pipeline_btn = gr.Button(
                "Executar pipeline completo",
                variant="primary",
                interactive=False,
            )
            start_pipeline_btn.click(
                fn=run_full_pipeline,
                inputs=[
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                    culling_checkbox,
                    culling_threshold,
                    pca_slider,
                    batch_size_slider,
                    include_nn_checkbox,
                    include_nn_eval_checkbox,
                    num_presets_input,
                    min_rating_input,
                    classifier_epochs_input,
                    refiner_epochs_input,
                    patience_input,
                    param_importance_input,
                ],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    start_pipeline_btn,
                ],
            )

        with gr.Tab("Passo a passo"):
            gr.Markdown("Sê granular: corre etapas individuais quando precisares.")
            extract_btn = gr.Button("1. Extrair dados do catálogo", interactive=False)
            culling_btn = gr.Button("2. Aplicar culling", interactive=False)
            embeddings_btn = gr.Button("3. Gerar embeddings", interactive=False)
            pca_btn = gr.Button("4. Preparar PCA", interactive=False)
            retrain_feedback_btn = gr.Button("7. Re-treinar com feedback novo", interactive=False)
            train_nn_btn = gr.Button("8. Treinar Rede Neural", interactive=False)
            eval_nn_btn = gr.Button("9. Avaliar Rede Neural", interactive=False)

            CATALOG_BUTTONS.clear()
            CATALOG_BUTTONS.extend(
                [
                    start_pipeline_btn,
                    extract_btn,
                    culling_btn,
                    embeddings_btn,
                    pca_btn,
                    retrain_feedback_btn,
                    train_nn_btn,
                    eval_nn_btn,
                ]
            )

            catalog_input.change(
                fn=handle_manual_catalog_change,
                inputs=[catalog_input, catalog_file_input],
                outputs=CATALOG_BUTTONS,
            )
            catalog_file_input.change(
                fn=handle_catalog_file_selection,
                inputs=[catalog_file_input, catalog_input],
                outputs=[catalog_input, *CATALOG_BUTTONS],
            )

            extract_btn.click(
                fn=run_extract,
                inputs=[
                    catalog_input,
                    overwrite_checkbox,
                    skip_missing_checkbox,
                    limit_input,
                ],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    extract_btn,
                ],
            )
            embeddings_btn.click(
                fn=run_embeddings,
                inputs=[culling_checkbox, batch_size_slider],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    embeddings_btn,
                ],
            )
            culling_btn.click(
                fn=run_culling_step,
                inputs=[
                    culling_threshold,
                    limit_input,
                ],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    culling_btn,
                ],
            )
            pca_btn.click(
                fn=run_prepare_features,
                inputs=[pca_slider],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    pca_btn,
                ],
            )
            retrain_feedback_btn.click(
                fn=run_retrain_feedback,
                inputs=[],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    retrain_feedback_btn,
                ],
            )
            train_nn_btn.click(
                fn=run_train_nn,
                inputs=[],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    train_nn_btn,
                ],
            )
            eval_nn_btn.click(
                fn=run_eval_nn,
                inputs=[],
                outputs=[
                    log_output,
                    log_file_output,
                    summary_table,
                    summary_overall,
                    eval_nn_btn,
                ],
            )

        with gr.Tab("Configuração de Sliders"):
            slider_components, _ = create_slider_config_ui() # ordered_mae_displays is now GLOBAL_ORDERED_MAE_DISPLAYS
            load_mae_btn = gr.Button("Carregar MAE da Última Avaliação")
            load_mae_btn.click(
                fn=lambda: update_slider_mae_displays(
                    [[None, name, value] for name, value in slider_mae_values.items()],
                    GLOBAL_ORDERED_MAE_DISPLAYS
                ),
                inputs=[],
                outputs=GLOBAL_ORDERED_MAE_DISPLAYS
            )

if __name__ == "__main__":
    iface.queue().launch(server_name="127.0.0.1", share=False)
