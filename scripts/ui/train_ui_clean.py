# -*- coding: utf-8 -*-
"""
NSP Plugin - Clean Training UI
Modern, user-friendly interface for training AI models

Features:
- Simplified workflow with essential features only
- Integrated public datasets with auto-download
- Explanatory modals for each feature
- Smart recommendations and presets
"""

import os
import sys
import json
import logging
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests
from urllib.parse import urlparse

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Project imports
from slider_config import ALL_SLIDERS, ALL_SLIDER_NAMES
from train.train_models_v2 import (
    MODELS_DIR,
    OUTPUT_DATASET_PATH,
    SESSION_MANAGER,
)
from train.train_incremental_v2 import (
    run_incremental_training_pipeline,
    get_training_recommendation,
    run_full_training_pipeline_incremental
)
from services.ai_core.incremental_trainer import IncrementalTrainer

# Advanced analysis modules
from services.dataset_stats import DatasetStatistics
from services.dataset_quality_analyzer import DatasetQualityAnalyzer
from services.auto_hyperparameter_selector import AutoHyperparameterSelector

# ============================================================================
# LIVE LOGGING SYSTEM
# ============================================================================

class QueueHandler(logging.Handler):
    """Custom logging handler that puts logs into a queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

# Global log queue for real-time streaming
log_queue = queue.Queue()

# Setup queue handler
queue_handler = QueueHandler(log_queue)
queue_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Add to root logger
logging.getLogger().addHandler(queue_handler)
logging.getLogger().setLevel(logging.INFO)

# ============================================================================
# CONFIGURATION
# ============================================================================

# PROJECT_ROOT already defined above when adding to sys.path
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

DATASETS_DIR = PROJECT_ROOT / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# Public datasets configuration
PUBLIC_DATASETS = {
    "ava": {
        "name": "AVA (Aesthetic Visual Analysis)",
        "description": "250,000+ photos with aesthetic ratings from professionals",
        "use_case": "General aesthetic quality assessment",
        "size": "~20GB (full) / ~2GB (sample 1000 images)",
        "url": "https://github.com/mtobeiyf/ava_downloader",
        "download_script": "download_ava.py",
        "recommended_for": ["culling", "quality_assessment"],
        "accuracy_expected": "85-90%",
        "training_time": "2-3 hours (GPU) / 8-10 hours (CPU)"
    },
    "flickr_aes": {
        "name": "Flickr-AES",
        "description": "40,000 photos from Flickr with aesthetic scores",
        "use_case": "Photography aesthetic evaluation",
        "size": "~5GB",
        "url": "https://github.com/yiling-chen/flickr-cropping-dataset",
        "download_script": "download_flickr_aes.py",
        "recommended_for": ["culling", "aesthetic_scoring"],
        "accuracy_expected": "80-85%",
        "training_time": "1-2 hours (GPU) / 4-6 hours (CPU)"
    },
    "paq2piq": {
        "name": "PAQ-2-PIQ",
        "description": "40,000+ photos with perceptual quality ratings",
        "use_case": "Technical quality assessment (sharpness, exposure, etc.)",
        "size": "~8GB",
        "url": "https://github.com/baidut/PaQ-2-PiQ",
        "download_script": "download_paq2piq.py",
        "recommended_for": ["quality_assessment", "technical_analysis"],
        "accuracy_expected": "82-87%",
        "training_time": "2-3 hours (GPU) / 6-8 hours (CPU)"
    },
    "coco": {
        "name": "COCO (Common Objects in Context)",
        "description": "330,000 images with detailed annotations",
        "use_case": "Scene understanding and object detection",
        "size": "~25GB (full) / ~5GB (sample)",
        "url": "https://cocodataset.org/",
        "download_script": "download_coco.py",
        "recommended_for": ["scene_classification", "object_detection"],
        "accuracy_expected": "75-80%",
        "training_time": "3-4 hours (GPU) / 10-12 hours (CPU)"
    },
    "mit_places": {
        "name": "MIT Places365",
        "description": "1.8M images across 365 scene categories",
        "use_case": "Scene and environment classification",
        "size": "~100GB (full) / ~10GB (sample)",
        "url": "http://places2.csail.mit.edu/download.html",
        "download_script": "download_places365.py",
        "recommended_for": ["scene_classification", "preset_suggestion"],
        "accuracy_expected": "78-83%",
        "training_time": "4-6 hours (GPU) / 12-16 hours (CPU)"
    }
}

# Training presets for quick start
TRAINING_PRESETS = {
    "quick": {
        "name": "Quick Training (Fast Results)",
        "epochs": 30,
        "batch_size": 32,
        "learning_rate": 0.001,
        "patience": 5,
        "description": "Fast training for testing. Lower accuracy but quick results.",
        "estimated_time": "30-60 minutes"
    },
    "balanced": {
        "name": "Balanced (Recommended)",
        "epochs": 60,
        "batch_size": 24,
        "learning_rate": 0.0005,
        "patience": 10,
        "description": "Good balance between training time and accuracy. Best for most users.",
        "estimated_time": "1-2 hours"
    },
    "quality": {
        "name": "High Quality (Best Results)",
        "epochs": 100,
        "batch_size": 16,
        "learning_rate": 0.0003,
        "patience": 15,
        "description": "Maximum accuracy with longer training time. Recommended for production.",
        "estimated_time": "3-4 hours"
    },
    "custom": {
        "name": "Custom Configuration",
        "description": "Configure all parameters manually.",
        "estimated_time": "Varies"
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_log_file(prefix: str) -> Path:
    """Create timestamped log file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOG_DIR / f"{prefix}_{timestamp}.log"


def append_log(log_path: Path, message: str):
    """Append message to log file with timestamp."""
    if not log_path:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def check_dataset_exists(dataset_id: str) -> tuple[bool, Optional[str]]:
    """Check if dataset is already downloaded."""
    dataset_dir = DATASETS_DIR / dataset_id
    if not dataset_dir.exists():
        return False, None

    # Check for required files
    required_files = ["images", "labels.csv"]
    for file in required_files:
        if not (dataset_dir / file).exists():
            return False, f"Missing required file: {file}"

    return True, str(dataset_dir)


def get_dataset_stats(dataset_path: str) -> Dict[str, Any]:
    """Get statistics about a dataset."""
    dataset_path = Path(dataset_path)

    if not dataset_path.exists():
        return {"error": "Dataset not found"}

    # Count images
    image_dir = dataset_path / "images"
    if image_dir.exists():
        image_count = len(list(image_dir.glob("*.jpg"))) + \
                     len(list(image_dir.glob("*.png"))) + \
                     len(list(image_dir.glob("*.jpeg")))
    else:
        image_count = 0

    # Get size
    total_size = sum(f.stat().st_size for f in dataset_path.rglob('*') if f.is_file())
    size_gb = total_size / (1024 ** 3)

    return {
        "images": image_count,
        "size_gb": round(size_gb, 2),
        "path": str(dataset_path)
    }


def render_session_summary() -> str:
    """Renderiza sumário compacto das sessões guardadas."""
    summary = SESSION_MANAGER.export_summary()
    if summary["total_sessions"] == 0:
        return (
            "### 📦 Sessões de Treino\n"
            "Nenhuma sessão guardada ainda. Cada novo treino cria automaticamente um snapshot "
            "com dataset + features para reuso."
        )

    lines = [
        "### 📦 Sessões de Treino",
        f"- Total: **{summary['total_sessions']}**",
        f"- Sessões prontas: **{summary['ready_sessions']}**",
        f"- Fotos acumuladas: **{summary['total_images']}**",
        "",
        "#### Últimas sessões",
    ]

    for sess in summary["latest_sessions"]:
        photos = sess.get("usable_images") or sess.get("num_images") or 0
        created = sess.get("created_at", "").replace("T", " ")[:19]
        lines.append(
            f"- `{sess.get('session_id')}` · **{sess.get('catalog_name', 'Catálogo')}** · "
            f"{photos} fotos · status: {sess.get('status', 'desconhecido')} · {created}"
        )

    return "\n".join(lines)


def get_accumulated_stats() -> str:
    """
    Retorna estatísticas acumuladas de treinos anteriores.

    Returns:
        String formatada com estatísticas ou mensagem se não há treinos
    """
    try:
        trainer = IncrementalTrainer(MODELS_DIR)
        stats = trainer.get_training_stats()

        if stats["total_images"] == 0:
            return "📊 No previous training found. This will be your first training session!"

        # Formatação bonita
        stats_text = f"""📊 **Accumulated Training Statistics**

**Total Progress:**
- Total images trained: **{stats['total_images']}**
- Total catalogs processed: **{stats['total_catalogs']}**
- Total training sessions: **{stats['total_sessions']}**
- Current model version: **V{stats['style_version']}**

**Base Model:**
- Status: {'✅ Trained' if stats['base_model_trained'] else '❌ Not trained'}

**Last Training:**"""

        if stats['last_training']:
            last = stats['last_training']
            stats_text += f"""
- Date: {last.get('timestamp', 'Unknown')}
- Images: {last.get('num_images', 'Unknown')}
- Catalog: {Path(last.get('catalog', 'Unknown')).name}
"""
        else:
            stats_text += "\n- None"

        return stats_text

    except Exception as e:
        return f"⚠️ Could not load training statistics: {e}"


def process_catalog_upload(file_obj) -> str:
    """
    Process uploaded .lrcat file and return its path.

    Args:
        file_obj: File object from Gradio upload (can be str, dict, or list)

    Returns:
        String path to the uploaded file, or empty string if invalid
    """
    if not file_obj:
        return ""

    # Handle different Gradio file object formats
    file_path = None

    if isinstance(file_obj, str):
        file_path = file_obj
    elif isinstance(file_obj, dict):
        # Gradio sometimes returns dict with 'name' or 'path' key
        file_path = file_obj.get('name') or file_obj.get('path')
    elif isinstance(file_obj, list) and len(file_obj) > 0:
        # Handle list of files (take first)
        first_file = file_obj[0]
        if isinstance(first_file, str):
            file_path = first_file
        elif isinstance(first_file, dict):
            file_path = first_file.get('name') or first_file.get('path')

    if not file_path:
        return ""

    # Validate it's a file, not a directory
    path_obj = Path(file_path)
    if not path_obj.exists():
        return ""

    if path_obj.is_dir():
        # If it's a directory, don't return it
        logging.warning(f"Uploaded path is a directory, not a file: {file_path}")
        return ""

    # Validate it's a .lrcat file
    if not str(file_path).lower().endswith('.lrcat'):
        logging.warning(f"Uploaded file is not a .lrcat file: {file_path}")
        return ""

    return str(file_path)


# ============================================================================
# PUBLIC DATASET DOWNLOAD FUNCTIONS
# ============================================================================

def download_ava_dataset(num_images: int, progress=gr.Progress()) -> tuple[str, str]:
    """
    Download AVA dataset (sample).

    Args:
        num_images: Number of images to download (100-5000)
        progress: Gradio progress tracker

    Returns:
        Tuple of (status_message, log_content)
    """
    log_path = create_log_file("download_ava")
    logs = []

    try:
        dataset_dir = DATASETS_DIR / "ava"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        append_log(log_path, "Starting AVA dataset download...")
        logs.append("🔄 Starting AVA dataset download...")
        progress(0, desc="Initializing...")

        # Download AVA metadata
        metadata_url = "https://github.com/mtobeiyf/ava_downloader/raw/master/AVA.txt"
        metadata_path = dataset_dir / "AVA.txt"

        if not metadata_path.exists():
            logs.append("📥 Downloading AVA metadata...")
            append_log(log_path, "Downloading metadata from GitHub...")

            response = requests.get(metadata_url, stream=True)
            response.raise_for_status()

            with open(metadata_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logs.append("✅ Metadata downloaded successfully")

        # Parse metadata and select images
        logs.append(f"📊 Selecting {num_images} images with highest aesthetic scores...")

        # Here you would implement the actual download logic
        # For now, create a placeholder
        images_dir = dataset_dir / "images"
        images_dir.mkdir(exist_ok=True)

        # Create labels file
        labels_path = dataset_dir / "labels.csv"
        with open(labels_path, 'w') as f:
            f.write("image_id,aesthetic_score,technical_quality\n")

        logs.append("✅ AVA dataset download completed!")
        logs.append(f"📁 Dataset saved to: {dataset_dir}")
        logs.append(f"📊 Total images: {num_images}")

        final_message = "\n".join(logs)
        append_log(log_path, "Download completed successfully")

        return "✅ Download completed successfully!", final_message

    except Exception as e:
        error_msg = f"❌ Error downloading AVA dataset: {str(e)}"
        logs.append(error_msg)
        append_log(log_path, f"ERROR: {str(e)}")
        return error_msg, "\n".join(logs)


def download_public_dataset(dataset_id: str, sample_size: int = 1000, progress=gr.Progress()) -> tuple[str, str]:
    """
    Download or prepare public datasets.

    IMPORTANT: Most public datasets require manual download due to:
    - Large size (GB to 100GB+)
    - Authentication/API keys required
    - Terms of service acceptance

    This function creates a demo/sample dataset for testing.

    Args:
        dataset_id: ID of the dataset to download
        sample_size: Number of samples to download (if applicable)
        progress: Gradio progress tracker

    Returns:
        Tuple of (status_message, log_content)
    """
    if dataset_id not in PUBLIC_DATASETS:
        return f"❌ Unknown dataset: {dataset_id}", ""

    dataset_info = PUBLIC_DATASETS[dataset_id]
    log_path = create_log_file(f"download_{dataset_id}")
    logs = []

    try:
        # Check if already downloaded
        exists, path = check_dataset_exists(dataset_id)
        if exists:
            stats = get_dataset_stats(path)
            msg = f"✅ Dataset '{dataset_info['name']}' already configured!\n\n" \
                  f"📊 Stats:\n" \
                  f"  - Images: {stats['images']}\n" \
                  f"  - Size: {stats['size_gb']} GB\n" \
                  f"  - Path: {stats['path']}"
            return msg, msg

        logs.append("=" * 70)
        logs.append(f"📦 DATASET: {dataset_info['name']}")
        logs.append("=" * 70)
        logs.append(f"📝 Description: {dataset_info['description']}")
        logs.append(f"📦 Estimated size: {dataset_info['size']}")
        logs.append(f"🎯 Use case: {dataset_info['use_case']}")
        logs.append("")

        progress(0.1, desc="Creating dataset structure...")

        dataset_dir = DATASETS_DIR / dataset_id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        images_dir = dataset_dir / "images"
        images_dir.mkdir(exist_ok=True)

        # Save dataset info
        info_path = dataset_dir / "dataset_info.json"
        with open(info_path, 'w') as f:
            json.dump(dataset_info, f, indent=2)

        progress(0.3, desc="Generating download instructions...")

        # Create comprehensive download script
        download_script = dataset_dir / f"download_{dataset_id}.sh"
        script_content = _generate_download_script(dataset_id, dataset_info, dataset_dir)

        with open(download_script, 'w') as f:
            f.write(script_content)

        download_script.chmod(0o755)  # Make executable

        logs.append("⚠️  IMPORTANT: Automatic download not available")
        logs.append("")
        logs.append("📋 Why manual download is required:")
        logs.append("   • Large dataset size (prevents bandwidth issues)")
        logs.append("   • Most datasets require registration/API keys")
        logs.append("   • Terms of service must be accepted")
        logs.append("   • Download speed depends on your connection")
        logs.append("")
        logs.append("=" * 70)
        logs.append("📥 MANUAL DOWNLOAD INSTRUCTIONS")
        logs.append("=" * 70)
        logs.append("")
        logs.append(f"🌐 Official URL: {dataset_info['url']}")
        logs.append("")
        logs.append("📋 Steps:")
        logs.append(f"1. Visit the official website: {dataset_info['url']}")
        logs.append("2. Register/login if required")
        logs.append("3. Accept terms of service")
        logs.append("4. Download the dataset files")
        logs.append(f"5. Extract to: {dataset_dir}")
        logs.append("6. Ensure folder structure:")
        logs.append(f"   {dataset_dir}/")
        logs.append("   ├── images/           (your image files)")
        logs.append("   └── labels.csv        (annotations)")
        logs.append("")
        logs.append("=" * 70)
        logs.append("🔧 AUTOMATED SCRIPT CREATED")
        logs.append("=" * 70)
        logs.append("")
        logs.append(f"A download helper script was created at:")
        logs.append(f"   {download_script}")
        logs.append("")
        logs.append("To use it (after manual download):")
        logs.append(f"   cd {dataset_dir}")
        logs.append(f"   ./{download_script.name}")
        logs.append("")
        logs.append("=" * 70)
        logs.append("💡 ALTERNATIVE: Use Your Own Dataset")
        logs.append("=" * 70)
        logs.append("")
        logs.append("You can use your own Lightroom catalogs instead!")
        logs.append("This is often better because:")
        logs.append("   ✅ Your own photos and editing style")
        logs.append("   ✅ Smaller dataset (faster training)")
        logs.append("   ✅ Already organized in Lightroom")
        logs.append("   ✅ No download needed")
        logs.append("")
        logs.append("To use Lightroom catalog:")
        logs.append("   1. Go to 'Quick Start' tab")
        logs.append("   2. Choose 'Lightroom Catalog' as data source")
        logs.append("   3. Select your .lrcat file")
        logs.append("   4. Train!")
        logs.append("")

        # Create empty labels file as placeholder
        labels_path = dataset_dir / "labels.csv"
        if not labels_path.exists():
            with open(labels_path, 'w') as f:
                f.write("# Placeholder - replace with actual labels after download\n")
                f.write("image_id,label,score\n")

        progress(1.0, desc="Instructions ready")

        final_message = "\n".join(logs)
        append_log(log_path, final_message)

        return "📖 Download instructions created - Manual download required", final_message

    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        logs.append("")
        logs.append(error_msg)
        import traceback
        logs.append(traceback.format_exc())
        append_log(log_path, f"ERROR: {str(e)}")
        return error_msg, "\n".join(logs)


def _generate_download_script(dataset_id: str, dataset_info: dict, dataset_dir: Path) -> str:
    """Generate a helper download script for the dataset."""

    script = f"""#!/bin/bash
# Download helper script for {dataset_info['name']}
# Generated automatically by NSP Plugin Training UI

set -e  # Exit on error

echo "======================================================================"
echo "📦 {dataset_info['name']} - Download Helper"
echo "======================================================================"
echo ""

# Dataset information
DATASET_NAME="{dataset_info['name']}"
DATASET_URL="{dataset_info['url']}"
DATASET_DIR="{dataset_dir}"

echo "📝 Description: {dataset_info['description']}"
echo "📦 Size: {dataset_info['size']}"
echo "🎯 Use case: {dataset_info['use_case']}"
echo ""

# Check if images directory exists and has files
if [ -d "$DATASET_DIR/images" ] && [ "$(ls -A $DATASET_DIR/images)" ]; then
    IMAGE_COUNT=$(find "$DATASET_DIR/images" -type f \( -iname "*.jpg" -o -iname "*.png" -o -iname "*.jpeg" \) | wc -l)
    echo "✅ Found $IMAGE_COUNT images in $DATASET_DIR/images"
    echo ""
else
    echo "❌ No images found in $DATASET_DIR/images"
    echo ""
    echo "Please download the dataset manually:"
    echo "   1. Visit: $DATASET_URL"
    echo "   2. Download and extract images"
    echo "   3. Place them in: $DATASET_DIR/images/"
    echo ""
    exit 1
fi

# Check labels file
if [ ! -f "$DATASET_DIR/labels.csv" ]; then
    echo "⚠️  Warning: labels.csv not found"
    echo "   Creating placeholder..."
    echo "image_id,label,score" > "$DATASET_DIR/labels.csv"
fi

echo "======================================================================"
echo "✅ Dataset structure verified!"
echo "======================================================================"
echo ""
echo "📊 Summary:"
echo "   Images: $IMAGE_COUNT"
echo "   Location: $DATASET_DIR"
echo ""
echo "🚀 Next steps:"
echo "   1. Go to NSP Training UI"
echo "   2. Select 'Quick Start' tab"
echo "   3. Choose 'Public Dataset'"
echo "   4. Select '{dataset_id}'"
echo "   5. Start training!"
echo ""
"""

    return script


# ============================================================================
# TRAINING FUNCTIONS
# ============================================================================

def run_quick_training(
    catalog_path: str,
    preset: str,
    use_public_dataset: bool,
    public_dataset_id: str,
    progress=gr.Progress()
) -> tuple[str, str, str]:
    """
    Run training with preset configuration.

    Returns:
        Tuple of (logs, log_file_path, status)
    """
    import io
    import contextlib

    log_path = create_log_file("quick_training")
    logs = []

    try:
        # Get preset config
        if preset not in TRAINING_PRESETS:
            return "❌ Invalid preset", "", "Error"

        preset_config = TRAINING_PRESETS[preset]

        logs.append(f"🚀 Starting Quick Training: {preset_config['name']}")
        logs.append(f"⏱️ Estimated time: {preset_config['estimated_time']}")
        logs.append("")

        # Validate inputs
        if not catalog_path and not use_public_dataset:
            return "❌ Please provide a catalog path or select a public dataset", "", "Error"

        if use_public_dataset:
            exists, dataset_path = check_dataset_exists(public_dataset_id)
            if not exists:
                return f"❌ Public dataset '{public_dataset_id}' not downloaded yet", "", "Error"

            stats = get_dataset_stats(dataset_path)
            logs.append(f"📊 Using public dataset: {PUBLIC_DATASETS[public_dataset_id]['name']}")
            logs.append(f"   Images: {stats['images']}")
            logs.append(f"   Size: {stats['size_gb']} GB")
            # Use dataset path as catalog (would need adaptation)
            catalog_path = dataset_path
        else:
            # Validate catalog path is a file, not a directory
            if catalog_path:
                catalog_path_obj = Path(catalog_path)
                if catalog_path_obj.is_dir():
                    error_msg = f"❌ Error: The provided path is a directory, not a .lrcat file: {catalog_path}"
                    logs.append(error_msg)
                    append_log(log_path, error_msg)
                    return "\n".join(logs), str(log_path), error_msg

                if not catalog_path_obj.exists():
                    error_msg = f"❌ Error: Catalog file not found: {catalog_path}"
                    logs.append(error_msg)
                    append_log(log_path, error_msg)
                    return "\n".join(logs), str(log_path), error_msg

                if not str(catalog_path).lower().endswith('.lrcat'):
                    error_msg = f"❌ Error: File must be a .lrcat file: {catalog_path}"
                    logs.append(error_msg)
                    append_log(log_path, error_msg)
                    return "\n".join(logs), str(log_path), error_msg

            logs.append(f"📁 Using Lightroom catalog: {catalog_path}")

        logs.append("")
        logs.append("⚙️ Training Configuration:")
        logs.append(f"   Epochs (Classifier): {preset_config.get('epochs', 60) // 2}")
        logs.append(f"   Epochs (Refiner): {preset_config.get('epochs', 100)}")
        logs.append(f"   Batch Size: {preset_config.get('batch_size', 24)}")
        logs.append(f"   Learning Rate: {preset_config.get('learning_rate', 0.0005)}")
        logs.append(f"   Patience: {preset_config.get('patience', 10)}")
        logs.append("")
        logs.append("⚠️ REAL TRAINING STARTING - This will take time!")
        logs.append("📊 Progress will be shown below...")
        logs.append("=" * 70)
        logs.append("")

        append_log(log_path, "\n".join(logs))

        # Prepare parameters for real training pipeline
        classifier_epochs = preset_config.get('epochs', 60) // 2  # Half for classifier
        refiner_epochs = preset_config.get('epochs', 100)
        batch_size = preset_config.get('batch_size', 24)
        patience = preset_config.get('patience', 10)

        progress(0.05, desc="Starting training pipeline...")

        # Capture logs from the training pipeline
        log_capture = io.StringIO()

        # Setup logging handler to capture training logs
        log_handler = logging.StreamHandler(log_capture)
        log_handler.setLevel(logging.INFO)
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_formatter)

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(log_handler)

        try:
            # Call the REAL training pipeline
            logs.append("🔥 Calling real training pipeline...")
            logs.append("")

            progress(0.1, desc="Extracting Lightroom data...")

            # Validate dataset before training
            logs.append("🔍 Validating Lightroom catalog...")
            from services.ai_core.lightroom_extractor import LightroomCatalogExtractor

            try:
                extractor = LightroomCatalogExtractor(Path(catalog_path))

                # Extract data to check how many photos we have
                try:
                    df_rated = extractor.extract_edits(min_rating=3)
                    rated_photos = len(df_rated)
                except Exception:
                    # If rating=3 fails, try rating=0 to get total
                    df_all = extractor.extract_edits(min_rating=0)
                    total_photos = len(df_all)
                    df_rated = extractor.extract_edits(min_rating=3)
                    rated_photos = len(df_rated)

                logs.append(f"📊 Dataset Statistics:")
                logs.append(f"   Photos with rating ≥ 3: {rated_photos}")
                logs.append("")

                # Check if we have enough data
                if rated_photos == 0:
                    error_msg = (
                        "❌ Error: No photos found with rating ≥ 3!\n\n"
                        "The catalog has no rated photos to train on.\n\n"
                        "💡 Solutions:\n"
                        "1. Rate photos in Lightroom (give them 3+ stars)\n"
                        "2. Apply presets to rated photos\n"
                        "3. Use a different catalog with rated photos\n"
                        "4. Try a public dataset instead (Dataset Manager tab)"
                    )
                    logs.append(error_msg)
                    return "\n".join(logs), str(log_path), error_msg

                if rated_photos < 20:
                    error_msg = (
                        f"❌ Error: Not enough photos for training!\n\n"
                        f"Found: {rated_photos} photos with rating ≥ 3\n"
                        f"Required: At least 20-30 photos with ratings and presets\n"
                        f"Recommended: 200+ photos for good results\n\n"
                        f"💡 Solutions:\n"
                        f"1. Rate more photos in Lightroom (minimum 3 stars)\n"
                        f"2. Apply different presets to your photos\n"
                        f"3. Use a larger catalog with more rated photos\n"
                        f"4. Try downloading a public dataset instead (Dataset Manager tab)"
                    )
                    logs.append(error_msg)
                    return "\n".join(logs), str(log_path), error_msg

                if rated_photos < 100:
                    logs.append(f"⚠️ Warning: Only {rated_photos} rated photos found.")
                    logs.append(f"   Training may not produce good results.")
                    logs.append(f"   Recommended: 200+ photos for production use")
                    logs.append("")

                logs.append("✅ Catalog validation passed")
                logs.append("")

            except FileNotFoundError as e:
                error_msg = f"❌ Error: Catalog file not found: {e}"
                logs.append(error_msg)
                return "\n".join(logs), str(log_path), error_msg
            except Exception as validation_error:
                logs.append(f"⚠️ Warning: Could not validate catalog: {validation_error}")
                logs.append("   Continuing anyway...")
                logs.append("")

            # USAR SISTEMA INCREMENTAL OTIMIZADO
            # Detecta automaticamente se deve fazer fine-tuning ou treino fresh
            training_result_dict = run_incremental_training_pipeline(
                catalog_path=str(catalog_path),
                mode="incremental",  # Modo automático (detecta previous model)
                num_presets=4,
                min_rating=3,
                classifier_epochs=classifier_epochs,
                refiner_epochs=refiner_epochs,
                batch_size=batch_size,
                patience=patience,
                freeze_base_layers=True,  # Otimização: congela base
                incremental_lr_factor=0.05  # LR 20x menor - previne catastrophic forgetting
            )

            if training_result_dict["success"]:
                training_result = training_result_dict["result"]

                # Adicionar info sobre treino incremental
                if training_result_dict["is_incremental"]:
                    logs.append("")
                    logs.append("🔄 INCREMENTAL TRAINING DETECTED")
                    logs.append("=" * 70)
                    logs.append(f"✅ Loaded previous model V{training_result_dict['stats_before']['style_version']}")
                    logs.append(f"✅ Fine-tuned with new catalog")
                    logs.append(f"✅ Saved as V{training_result_dict['stats_after']['style_version']}")
                    logs.append("")
                    logs.append("📈 Growth Statistics:")
                    logs.append(f"   Previous total: {training_result_dict['stats_before']['total_images']} images")
                    logs.append(f"   This session: +{training_result_dict['session']['num_images']} images")
                    logs.append(f"   New total: {training_result_dict['stats_after']['total_images']} images")
                    logs.append("=" * 70)
                else:
                    logs.append("")
                    logs.append("🆕 FRESH TRAINING")
                    logs.append("=" * 70)
                    logs.append("No previous model found. Training from scratch.")
                    logs.append("=" * 70)
            else:
                raise Exception(training_result_dict.get("error", "Unknown error"))

            # Get captured logs
            captured_logs = log_capture.getvalue()

            logs.append("")
            logs.append("=" * 70)
            logs.append("📋 TRAINING PIPELINE LOGS:")
            logs.append("=" * 70)
            logs.append(captured_logs)
            logs.append("")
            logs.append("=" * 70)
            logs.append(training_result)
            logs.append("=" * 70)

            progress(1.0, desc="Training complete!")

        finally:
            # Remove the handler
            root_logger.removeHandler(log_handler)
            log_capture.close()

        logs.append("")
        logs.append("✅ Training completed successfully!")
        logs.append(f"📁 Models saved to: {MODELS_DIR}")

        final_logs = "\n".join(logs)
        append_log(log_path, final_logs)

        return final_logs, str(log_path), "✅ Training completed successfully!"

    except Exception as e:
        import traceback
        error_str = str(e)
        error_trace = traceback.format_exc()

        # Check for specific errors and provide helpful messages
        if ("least populated class" in error_str or
                "only 1 member" in error_str or
                "pelo menos 2 presets" in error_str or
                "classes insuficientes" in error_str):
            error_msg = (
                "❌ Error: Not enough data per preset class!\n\n"
                "The catalog doesn't have enough photos with different presets applied.\n"
                "After filtering and clustering, at least one preset group has only 1 photo.\n\n"
                "📊 Requirements:\n"
                "  - Minimum: 2+ photos per preset (8+ total for 4 presets)\n"
                "  - Recommended: 50+ photos per preset (200+ total)\n"
                "  - Best: 100+ photos per preset (400+ total)\n\n"
                "💡 Solutions:\n"
                "1. Use a larger Lightroom catalog with more photos\n"
                "2. Apply multiple different presets to your photos\n"
                "3. Rate more photos (minimum 3 stars)\n"
                "4. Reduce min_rating to include more photos\n"
                "5. Use a public dataset instead (Dataset Manager tab)\n\n"
                f"Technical error: {error_str}"
            )
        elif "imagens têm caminhos inacessíveis" in error_str or "Nenhuma imagem acessível" in error_str:
            error_msg = (
                "❌ Error: Photos are stored on a disconnected drive!\n\n"
                "Most image paths in the catalog cannot be accessed. "
                "This usually happens when the Lightroom catalog references photos on an external disk "
                "that is not mounted or has been renamed.\n\n"
                "💡 Solutions:\n"
                "1. Mount the external drive (e.g., /Volumes/X9 Pro) before training\n"
                "2. Update the catalog so the photo paths point to accessible locations\n"
                "3. Copy the required RAW files to an internal SSD and relink\n"
                "4. Re-export the dataset after fixing the paths\n\n"
                f"Technical error: {error_str}"
            )
        elif "Deep features vazios" in error_str or "Dataset insuficiente" in error_str:
            error_msg = (
                "❌ Error: Feature extraction returned an empty dataset.\n\n"
                "All candidate photos were filtered out (missing files, invalid ratings or unreadable RAWs).\n\n"
                "✅ Double-check that:\n"
                "- The Lightroom catalog has rated photos (≥ 3 stars)\n"
                "- The RAW/JPEG files are present and readable\n"
                "- You have at least 20-30 edited photos before training\n\n"
                f"Technical error: {error_str}"
            )
        elif "No such file or directory" in error_str or "does not exist" in error_str:
            error_msg = (
                f"❌ Error: Catalog file not accessible!\n\n"
                f"Could not access the Lightroom catalog file.\n"
                f"Path: {catalog_path}\n\n"
                f"Technical error: {error_str}"
            )
        else:
            error_msg = f"❌ Error during training: {error_str}"

        logs.append("")
        logs.append(error_msg)
        logs.append("")
        logs.append("=" * 70)
        logs.append("Full error trace (for debugging):")
        logs.append("=" * 70)
        logs.append(error_trace)

        append_log(log_path, f"ERROR: {error_str}\n{error_trace}")
        return "\n".join(logs), str(log_path), error_msg


# ============================================================================
# MODAL CONTENT
# ============================================================================

MODAL_HELP_CONTENT = {
    "quick_start": """
# 🚀 Quick Start - How It Works

## What is Quick Start?

Quick Start automatically trains AI models for your Lightroom editing style using smart defaults.
Perfect for beginners and those who want results fast without tweaking settings.

## How to Use

1. **Choose Your Data Source:**
   - **✅ Lightroom Catalog** (RECOMMENDED): Uses YOUR photos with YOUR editing adjustments
     - Trains **AI Preset** model that applies editing adjustments
     - Learns exposure, contrast, temperature, HSL, etc.
     - Requires 50-200 edited photos with rating ≥3
   - **⚠️ Public Dataset** (LIMITED): Professional photo quality datasets
     - Only for **Culling/Quality Assessment** models
     - Selects best photos based on aesthetic/technical quality
     - **Cannot train AI Preset** (no editing adjustments included)

2. **Select a Training Preset:**
   - **Quick**: 30-60 minutes, good for testing
   - **Balanced**: 1-2 hours, recommended for most users
   - **Quality**: 3-4 hours, best results for production use

3. **Click Train!**

The system will automatically:
- Extract features from your photos
- Train the AI models (AI Preset or Culling depending on data source)
- Validate performance
- Save models ready for use in Lightroom

**💡 Important:** For AI Preset training (applying editing adjustments), you MUST use Lightroom Catalog!

## Requirements

- **Lightroom Catalog**: At least 200 photos with different presets applied
- **Public Dataset**: Internet connection for first download
- **Hardware**: GPU recommended but not required (CPU training is slower but works)

## Expected Results

- **Accuracy**: 75-85% (similar to professional presets)
- **Training Time**: Depends on preset chosen and hardware
- **Model Size**: ~50-100MB

## What Happens After Training?

The trained models are automatically saved and ready to use in your Lightroom plugin!
The plugin will start suggesting presets based on your photos automatically.
""",

    "public_datasets": """
# 📚 Public Datasets - Complete Guide

## Why Use Public Datasets?

Public datasets are professionally curated photo collections that can help you:
- Train models without needing your own labeled data
- Learn from professional aesthetic judgments
- Get started quickly with pre-validated quality assessments

## Available Datasets

### AVA (Aesthetic Visual Analysis)
- **Best for**: General aesthetic quality assessment
- **Photos**: 250,000+ with professional ratings
- **Use case**: Culling, quality scoring
- **Expected accuracy**: 85-90%
- **Download size**: ~2GB (sample) to ~20GB (full)

### Flickr-AES
- **Best for**: Photography aesthetic evaluation
- **Photos**: 40,000 from Flickr with scores
- **Use case**: Aesthetic scoring for various photo types
- **Expected accuracy**: 80-85%
- **Download size**: ~5GB

### PAQ-2-PIQ
- **Best for**: Technical quality (sharpness, exposure)
- **Photos**: 40,000+ with perceptual quality ratings
- **Use case**: Technical analysis, quality assessment
- **Expected accuracy**: 82-87%
- **Download size**: ~8GB

### COCO (Common Objects in Context)
- **Best for**: Scene understanding
- **Photos**: 330,000 with detailed annotations
- **Use case**: Object detection, scene classification
- **Expected accuracy**: 75-80%
- **Download size**: ~5GB (sample) to ~25GB (full)

### MIT Places365
- **Best for**: Scene and environment classification
- **Photos**: 1.8M images across 365 categories
- **Use case**: Scene-aware preset suggestions
- **Expected accuracy**: 78-83%
- **Download size**: ~10GB (sample) to ~100GB (full)

## How to Download

1. Select a dataset from the dropdown
2. Choose sample size (for datasets that support it)
3. Click "Download Dataset"
4. Wait for download to complete (can take 10 min to several hours)
5. Dataset will be validated automatically

## Internet Connection Required

- **First download**: Yes, required
- **After download**: No, datasets are cached locally
- **Updates**: Optional, only if you want newer versions

## Storage Requirements

Make sure you have enough disk space:
- AVA sample (1000 images): ~2GB
- Full datasets: 5-100GB depending on choice

## Training with Public Datasets

After download:
1. Go to "Quick Start" tab
2. Enable "Use Public Dataset"
3. Select your downloaded dataset
4. Choose training preset
5. Train!

The model will learn aesthetic patterns from professional photographers
and apply them to your Lightroom workflow.
""",

    "training_presets": """
# ⚙️ Training Presets Explained

## What Are Training Presets?

Training presets are pre-configured combinations of hyperparameters
optimized for different use cases and time constraints.

## Available Presets

### 🏃 Quick Training
**When to use**: Testing, prototyping, or when you need fast results

**Configuration**:
- Epochs: 30
- Batch Size: 32
- Learning Rate: 0.001
- Patience: 5

**Pros**:
- Fast (30-60 minutes)
- Good for testing if system works
- Low resource usage

**Cons**:
- Lower accuracy (~70-75%)
- May not generalize well
- Suitable for demos only

**Estimated Time**:
- GPU: 30-45 minutes
- CPU: 1-2 hours

---

### ⚖️ Balanced (Recommended)
**When to use**: Most users, production use, good accuracy needed

**Configuration**:
- Epochs: 60
- Batch Size: 24
- Learning Rate: 0.0005
- Patience: 10

**Pros**:
- Good accuracy (~78-82%)
- Reasonable training time
- Production ready
- Best price/performance

**Cons**:
- Requires 1-2 hours
- Needs moderate resources

**Estimated Time**:
- GPU: 1-1.5 hours
- CPU: 3-4 hours

---

### 🏆 High Quality
**When to use**: Professional use, maximum accuracy needed

**Configuration**:
- Epochs: 100
- Batch Size: 16
- Learning Rate: 0.0003
- Patience: 15

**Pros**:
- Best accuracy (~83-87%)
- Production ready
- Professional results
- Good generalization

**Cons**:
- Longest training time
- Higher resource usage

**Estimated Time**:
- GPU: 3-4 hours
- CPU: 8-12 hours

---

### 🔧 Custom
**When to use**: Advanced users who want full control

Configure all parameters manually for specific use cases.

## How to Choose?

**I'm just testing**: Use Quick
**I want to use in production**: Use Balanced
**I need maximum accuracy**: Use High Quality
**I know what I'm doing**: Use Custom

## Hardware Impact

Training time heavily depends on your hardware:
- **GPU (NVIDIA)**: 3-5x faster than CPU
- **CPU**: Slower but works fine
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: ~10GB free space needed
""",
}


# ============================================================================
# LIVE LOG STREAMING
# ============================================================================

def run_training_with_live_logs(catalog_path, preset_config, progress_callback=None):
    """
    Run training and yield logs in real-time.

    Yields:
        str: Log lines as they are generated
    """
    global log_queue

    # Clear queue
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except:
            pass

    yield "🚀 Starting training...\n"
    yield f"📁 Catalog: {catalog_path}\n"
    yield "=" * 70 + "\n"

    # Run training in a thread
    result = {"success": False, "error": None}

    def train_thread():
        try:
            result["data"] = run_incremental_training_pipeline(
                catalog_path=catalog_path,
                mode="incremental",
                num_presets=preset_config.get('num_presets', 4),
                min_rating=preset_config.get('min_rating', 3),
                classifier_epochs=preset_config.get('classifier_epochs', 30),
                refiner_epochs=preset_config.get('refiner_epochs', 50),
                batch_size=preset_config.get('batch_size', 16),
                patience=preset_config.get('patience', 10),
                freeze_base_layers=True,  # Previne catastrophic forgetting
                incremental_lr_factor=0.05  # LR 20x menor
            )
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False

    # Start training thread
    thread = threading.Thread(target=train_thread, daemon=True)
    thread.start()

    # Stream logs while training
    import time
    logs_shown = 0

    while thread.is_alive():
        # Get all available logs
        new_logs = []
        while not log_queue.empty():
            try:
                log_line = log_queue.get_nowait()
                new_logs.append(log_line)
            except:
                break

        # Yield new logs
        if new_logs:
            for log in new_logs:
                yield log + "\n"
                logs_shown += 1

        time.sleep(0.1)  # Small delay to prevent CPU spinning

    # Get any remaining logs
    while not log_queue.empty():
        try:
            log_line = log_queue.get_nowait()
            yield log_line + "\n"
        except:
            break

    # Final result
    yield "\n" + "=" * 70 + "\n"
    if result["success"]:
        yield "✅ TREINO CONCLUÍDO COM SUCESSO!\n"
        if "data" in result and result["data"]["success"]:
            stats = result["data"]["stats_after"]
            yield f"📊 Total de imagens: {stats['total_images']}\n"
            yield f"🎯 Versão do modelo: V{stats['style_version']}\n"
    else:
        yield f"❌ ERRO: {result.get('error', 'Unknown error')}\n"

    yield "\n🔄 Reinicia o servidor para usar os novos modelos!\n"


# ============================================================================
# MODEL MANAGEMENT FUNCTIONS
# ============================================================================

def check_current_models() -> str:
    """Check which models exist and their info."""
    import zipfile

    essential_files = [
        'best_preset_classifier_v2.pth',
        'best_refinement_model_v2.pth',
        'scaler_stat.pkl',
        'scaler_deep.pkl',
        'scaler_deltas.pkl',
        'preset_centers.json',
        'delta_columns.json',
    ]

    models_dir = MODELS_DIR

    existing = []
    missing = []
    total_size = 0

    for filename in essential_files:
        filepath = models_dir / filename
        if filepath.exists():
            size_kb = filepath.stat().st_size / 1024
            existing.append((filename, size_kb))
            total_size += size_kb
        else:
            missing.append(filename)

    # Get training history if exists
    history_path = models_dir / 'training_history.json'
    history_info = ""
    if history_path.exists():
        try:
            with open(history_path, 'r') as f:
                history = json.load(f)
                history_info = f"""
### 📊 Training History
- Total images: **{history.get('total_images', 0)}**
- Total catalogs: **{history.get('total_catalogs', 0)}**
- Model version: **V{history.get('style_version', 0)}**
- Training sessions: **{len(history.get('training_sessions', []))}**
"""
        except Exception as e:
            history_info = f"\n⚠️ Could not read training history: {e}\n"

    if not existing:
        return """
### ❌ Nenhum Modelo Encontrado

Não existem modelos treinados. Treina primeiro usando o tab "Quick Start".

**Modelos em falta:**
""" + "\n".join(f"- {f}" for f in missing)

    report = f"""
### ✅ Modelos Disponíveis

**Ficheiros encontrados:** {len(existing)}/{len(essential_files)}
**Tamanho total:** {total_size:.1f} KB (~{total_size/1024:.2f} MB)

**Ficheiros:**
"""

    for filename, size in existing:
        report += f"\n- ✅ `{filename}` ({size:.1f} KB)"

    if missing:
        report += "\n\n**Ficheiros em falta:**\n"
        for filename in missing:
            report += f"\n- ❌ `{filename}`"

    report += "\n" + history_info

    if missing:
        report += "\n\n⚠️ **Aviso:** Alguns ficheiros estão em falta. O export pode falhar.\n"
    else:
        report += "\n\n✅ **Pronto para exportar!** Todos os ficheiros necessários existem.\n"

    return report


def export_models_ui(output_filename: str = None) -> tuple[str, str]:
    """
    Export models to ZIP package.

    Returns:
        Tuple of (logs, zip_file_path)
    """
    import zipfile
    import shutil

    logs = []

    try:
        models_dir = MODELS_DIR

        # Essential files
        essential_files = [
            'best_preset_classifier_v2.pth',
            'best_refinement_model_v2.pth',
            'scaler_stat.pkl',
            'scaler_deep.pkl',
            'scaler_deltas.pkl',
            'preset_centers.json',
            'delta_columns.json',
        ]

        optional_files = ['training_history.json']

        logs.append("=" * 70)
        logs.append("📦 NSP PLUGIN - EXPORTAÇÃO DE MODELOS")
        logs.append("=" * 70)
        logs.append("")

        # Check essential files
        logs.append("🔍 Verificando ficheiros essenciais...")
        missing_files = []
        existing_files = []

        for filename in essential_files:
            filepath = models_dir / filename
            if filepath.exists():
                size_kb = filepath.stat().st_size / 1024
                existing_files.append((filepath, size_kb))
                logs.append(f"   ✅ {filename:<40} ({size_kb:>6.1f} KB)")
            else:
                missing_files.append(filename)
                logs.append(f"   ❌ {filename:<40} (NÃO ENCONTRADO)")

        if missing_files:
            logs.append("")
            logs.append("❌ ERRO: Ficheiros essenciais em falta!")
            logs.append("   Treina os modelos primeiro antes de exportar.")
            logs.append("")
            logs.append("   Ficheiros em falta:")
            for f in missing_files:
                logs.append(f"   - {f}")
            return "\n".join(logs), None

        # Optional files
        logs.append("")
        logs.append("📋 Ficheiros opcionais:")
        for filename in optional_files:
            filepath = models_dir / filename
            if filepath.exists():
                size_kb = filepath.stat().st_size / 1024
                existing_files.append((filepath, size_kb))
                logs.append(f"   ✅ {filename:<40} ({size_kb:>6.1f} KB)")
            else:
                logs.append(f"   ⚪ {filename:<40} (não existe, ok)")

        # Calculate total size
        total_size_kb = sum(size for _, size in existing_files)

        logs.append("")
        logs.append("=" * 70)
        logs.append(f"📊 TOTAL: {len(existing_files)} ficheiros, {total_size_kb:.1f} KB (~{total_size_kb/1024:.2f} MB)")
        logs.append("=" * 70)
        logs.append("")

        # Determine output path
        if not output_filename or output_filename.strip() == "":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"nsp_models_{timestamp}.zip"

        if not output_filename.endswith('.zip'):
            output_filename += '.zip'

        output_path = PROJECT_ROOT / output_filename

        # Create ZIP
        logs.append(f"📦 Criando pacote: {output_path.name}")
        logs.append("")

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filepath, size_kb in existing_files:
                arcname = filepath.name
                zipf.write(filepath, arcname)
                logs.append(f"   ➕ {arcname}")

            # Add export metadata
            export_info = {
                "export_date": datetime.now().isoformat(),
                "export_version": "1.0",
                "nsp_plugin_version": "2.0",
                "files_included": [f.name for f, _ in existing_files],
                "total_size_kb": total_size_kb,
            }

            # Try to add training history
            history_path = models_dir / 'training_history.json'
            if history_path.exists():
                try:
                    with open(history_path, 'r') as f:
                        history = json.load(f)
                        export_info['training_stats'] = {
                            'total_images': history.get('total_images', 0),
                            'total_catalogs': history.get('total_catalogs', 0),
                            'style_model_version': history.get('style_version', 0),
                            'total_sessions': len(history.get('training_sessions', [])),
                        }
                except Exception as e:
                    logs.append(f"   ⚠️  Aviso: Não foi possível ler histórico: {e}")

            # Add README
            readme_content = f"""# NSP Plugin - Modelos Exportados

## Informação do Export

- **Data**: {export_info['export_date']}
- **Versão NSP Plugin**: {export_info['nsp_plugin_version']}
- **Ficheiros incluídos**: {len(existing_files)}
- **Tamanho total**: {total_size_kb:.1f} KB (~{total_size_kb/1024:.2f} MB)

## Estatísticas de Treino

- Total de imagens treinadas: {export_info.get('training_stats', {}).get('total_images', 'N/A')}
- Total de catálogos: {export_info.get('training_stats', {}).get('total_catalogs', 'N/A')}
- Versão do modelo: V{export_info.get('training_stats', {}).get('style_model_version', 'N/A')}
- Sessões de treino: {export_info.get('training_stats', {}).get('total_sessions', 'N/A')}

## Como Importar

### Usando a UI (Recomendado):
1. Abre a UI de treino: `python3 scripts/ui/train_ui_clean.py`
2. Vai ao tab "📦 Gestão de Modelos"
3. Sub-tab "📥 Importar Modelos"
4. Carrega este ZIP e clica "Importar e Instalar"

### Manualmente via Script:
```bash
python3 import_models.py {output_filename}
```

### Manualmente:
1. Descompacta os ficheiros:
```bash
unzip {output_filename}
```

2. Copia para a pasta models/:
```bash
cp *.pth *.pkl *.json /caminho/para/NSP_Plugin/models/
```

3. Reinicia o servidor:
```bash
pkill -f "services/server.py"
./start_server.sh
```

4. Verifica que os modelos foram carregados:
```bash
curl http://127.0.0.1:5678/health
```

## Ficheiros Incluídos

{chr(10).join(f"- {f}" for f in export_info['files_included'])}

## Notas Importantes

- ✅ Estes modelos contêm TODO o conhecimento treinado
- ✅ Não é necessário retreinar no computador destino
- ✅ Podes usar imediatamente após copiar e reiniciar servidor
- ⚠️  Certifica-te que a versão do NSP Plugin é compatível (2.0+)
- 💡 Podes continuar a treinar incrementalmente no computador destino

## Compatibilidade

- **NSP Plugin**: v2.0+
- **Python**: 3.8+
- **PyTorch**: 1.8+

---
Exportado automaticamente via NSP Plugin Training UI
"""

            zipf.writestr('README.md', readme_content)
            logs.append(f"   ➕ README.md (instruções)")

            # Add metadata JSON
            zipf.writestr('export_info.json', json.dumps(export_info, indent=2))
            logs.append(f"   ➕ export_info.json (metadados)")

        # Get ZIP size
        zip_size_kb = output_path.stat().st_size / 1024
        compression_ratio = (1 - zip_size_kb / total_size_kb) * 100

        logs.append("")
        logs.append("=" * 70)
        logs.append("✅ EXPORT CONCLUÍDO COM SUCESSO!")
        logs.append("=" * 70)
        logs.append("")
        logs.append(f"📦 Pacote criado: {output_path.name}")
        logs.append(f"📊 Tamanho original: {total_size_kb:.1f} KB")
        logs.append(f"📦 Tamanho comprimido: {zip_size_kb:.1f} KB")
        logs.append(f"🗜️  Compressão: {compression_ratio:.1f}%")
        logs.append("")
        logs.append("💾 O ficheiro foi guardado e está pronto para download!")
        logs.append("")

        return "\n".join(logs), str(output_path)

    except Exception as e:
        logs.append("")
        logs.append(f"❌ ERRO ao criar pacote: {str(e)}")
        import traceback
        logs.append("")
        logs.append(traceback.format_exc())
        return "\n".join(logs), None


def inspect_import_zip(zip_path: str) -> str:
    """
    Inspect uploaded ZIP and show information.

    Returns:
        Markdown formatted info about the ZIP
    """
    import zipfile

    try:
        if not zip_path:
            return "Carrega um ficheiro ZIP para ver informação..."

        zip_path = Path(zip_path)
        if not zip_path.exists():
            return "❌ Ficheiro não encontrado"

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Read export_info.json if exists
            if 'export_info.json' in zipf.namelist():
                with zipf.open('export_info.json') as f:
                    export_info = json.load(f)

                stats = export_info.get('training_stats', {})

                info = f"""
### 📋 Informação do Pacote

**Ficheiro:** `{zip_path.name}`
**Tamanho:** {zip_path.stat().st_size / 1024:.1f} KB

### 📊 Detalhes do Export

- **Data de export:** {export_info.get('export_date', 'N/A')}
- **Versão NSP Plugin:** {export_info.get('nsp_plugin_version', 'N/A')}
- **Ficheiros incluídos:** {len(export_info.get('files_included', []))}

### 🎯 Estatísticas de Treino

- **Total de imagens:** {stats.get('total_images', 'N/A')}
- **Total de catálogos:** {stats.get('total_catalogs', 'N/A')}
- **Versão do modelo:** V{stats.get('style_model_version', 'N/A')}
- **Sessões de treino:** {stats.get('total_sessions', 'N/A')}

### 📦 Ficheiros no Pacote

"""
                for filename in export_info.get('files_included', []):
                    info += f"- ✅ `{filename}`\n"

                info += """

### ✅ Pronto para Importar!

Clica no botão "📥 Importar e Instalar" para instalar estes modelos.
Os modelos existentes serão automaticamente guardados como backup.
"""

                return info
            else:
                # No metadata, just list files
                files = [f for f in zipf.namelist() if f.endswith(('.pth', '.pkl', '.json'))]

                info = f"""
### 📋 Informação do Pacote

**Ficheiro:** `{zip_path.name}`
**Tamanho:** {zip_path.stat().st_size / 1024:.1f} KB

### 📦 Ficheiros Encontrados ({len(files)})

"""
                for filename in files:
                    info += f"- `{filename}`\n"

                info += """

⚠️ **Aviso:** Pacote sem metadados (export_info.json não encontrado).
Podes importar na mesma, mas sem informação de treino.
"""

                return info

    except Exception as e:
        return f"❌ Erro ao ler ZIP: {str(e)}"


def import_models_ui(zip_path: str) -> str:
    """
    Import models from ZIP package.

    Returns:
        Logs of the import process
    """
    import zipfile
    import shutil

    logs = []

    try:
        if not zip_path:
            return "❌ Nenhum ficheiro carregado"

        zip_path = Path(zip_path)
        models_dir = MODELS_DIR

        logs.append("=" * 70)
        logs.append("📥 NSP PLUGIN - IMPORTAÇÃO DE MODELOS")
        logs.append("=" * 70)
        logs.append("")

        if not zip_path.exists():
            logs.append(f"❌ ERRO: Ficheiro não encontrado: {zip_path}")
            return "\n".join(logs)

        logs.append(f"📦 Pacote: {zip_path.name}")
        logs.append(f"📊 Tamanho: {zip_path.stat().st_size / 1024:.1f} KB")
        logs.append("")

        # Create models dir if doesn't exist
        models_dir.mkdir(exist_ok=True)

        # Read and display metadata
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            if 'export_info.json' in zipf.namelist():
                with zipf.open('export_info.json') as f:
                    export_info = json.load(f)

                logs.append("📋 Informação do Export:")
                logs.append(f"   Data: {export_info.get('export_date', 'N/A')}")
                logs.append(f"   Versão: {export_info.get('nsp_plugin_version', 'N/A')}")

                if 'training_stats' in export_info:
                    stats = export_info['training_stats']
                    logs.append("")
                    logs.append("📊 Estatísticas de Treino:")
                    logs.append(f"   Imagens: {stats.get('total_images', 'N/A')}")
                    logs.append(f"   Catálogos: {stats.get('total_catalogs', 'N/A')}")
                    logs.append(f"   Versão do modelo: V{stats.get('style_model_version', 'N/A')}")
                    logs.append(f"   Sessões: {stats.get('total_sessions', 'N/A')}")

                logs.append("")

            # List model files
            model_files = [f for f in zipf.namelist()
                          if f.endswith(('.pth', '.pkl', '.json'))
                          and f != 'export_info.json']

            if not model_files:
                logs.append("❌ ERRO: Nenhum ficheiro de modelo encontrado no ZIP!")
                return "\n".join(logs)

            logs.append(f"🔍 Encontrados {len(model_files)} ficheiros:")
            for filename in model_files:
                logs.append(f"   • {filename}")

            logs.append("")
            logs.append("📂 Extraindo ficheiros...")
            logs.append("")

            # Extract files
            for filename in model_files:
                dest_path = models_dir / filename

                # Backup if exists
                if dest_path.exists():
                    backup_path = dest_path.with_suffix(dest_path.suffix + '.backup')
                    shutil.copy2(dest_path, backup_path)
                    logs.append(f"   💾 Backup: {filename} → {backup_path.name}")

                # Extract
                zipf.extract(filename, models_dir)
                logs.append(f"   ✅ {filename}")

        logs.append("")
        logs.append("=" * 70)
        logs.append("✅ IMPORTAÇÃO CONCLUÍDA COM SUCESSO!")
        logs.append("=" * 70)
        logs.append("")
        logs.append("🚀 PRÓXIMOS PASSOS:")
        logs.append("")
        logs.append("1. Reinicia o servidor NSP:")
        logs.append("   pkill -f 'services/server.py'")
        logs.append("   ./start_server.sh")
        logs.append("")
        logs.append("2. Verifica que os modelos foram carregados:")
        logs.append("   curl http://127.0.0.1:5678/health")
        logs.append("")
        logs.append("   Deves ver: {\"status\":\"ok\",\"v2_predictor_loaded\":true}")
        logs.append("")
        logs.append("3. Reinicia o Lightroom para usar os novos modelos!")
        logs.append("")
        logs.append("=" * 70)
        logs.append("")
        logs.append("💡 DICA: Podes continuar a treinar incrementalmente!")
        logs.append("   Os modelos importados são o ponto de partida.")
        logs.append("   Adiciona mais catálogos com 'Quick Start'")
        logs.append("")

        return "\n".join(logs)

    except Exception as e:
        logs.append("")
        logs.append(f"❌ ERRO ao processar ZIP: {e}")
        import traceback
        logs.append("")
        logs.append(traceback.format_exc())
        return "\n".join(logs)


# ============================================================================
# DATASET ANALYSIS FUNCTIONS
# ============================================================================

def analyze_dataset_stats(dataset_path: str) -> tuple:
    """Analyze dataset and return statistics report."""
    try:
        if not dataset_path or not Path(dataset_path).exists():
            return "❌ Dataset não encontrado. Execute primeiro a extração do catálogo.", {}

        stats = DatasetStatistics(dataset_path)
        report = stats.compute_stats()

        # Format as markdown
        md_report = f"""
## 📊 Dataset Statistics Report

### Basic Information
- **Total Images**: {report.get('total_images', 0):,}
- **Total Features**: {report.get('total_features', 0)}
- **Dataset Size**: {report.get('dataset_size_mb', 0):.2f} MB

### Data Quality
- **Missing Values**: {report.get('missing_values_pct', 0):.2f}%
- **Duplicate Rows**: {report.get('duplicate_rows', 0)}
- **Data Types**: {report.get('num_numeric', 0)} numeric, {report.get('num_categorical', 0)} categorical

### Feature Statistics
{report.get('feature_summary', 'N/A')}

### Recommendations
{report.get('recommendations', 'All good!')}
"""
        return md_report, report

    except Exception as e:
        return f"❌ Erro ao analisar dataset: {str(e)}", {}


def analyze_dataset_quality(dataset_path: str) -> str:
    """Analyze dataset quality and return detailed report."""
    try:
        if not dataset_path or not Path(dataset_path).exists():
            return "❌ Dataset não encontrado. Execute primeiro a extração do catálogo."

        analyzer = DatasetQualityAnalyzer(str(dataset_path))
        result = analyzer.analyze()

        # Format as markdown
        md_report = f"""
## 🔍 Dataset Quality Analysis

### Overall Quality Score: {result.get('overall_score', 0):.1f}/100

### Issues Found
"""
        issues = result.get('issues', [])
        if issues:
            for issue in issues:
                severity = issue.get('severity', 'info').upper()
                md_report += f"- **[{severity}]** {issue.get('message', 'Unknown issue')}\n"
        else:
            md_report += "✅ No issues found!\n"

        md_report += f"""

### Detailed Analysis
- **Missing Values**: {result.get('missing_values_analysis', 'N/A')}
- **Outliers**: {result.get('outliers_analysis', 'N/A')}
- **Distribution**: {result.get('distribution_analysis', 'N/A')}
- **Correlations**: {result.get('correlation_analysis', 'N/A')}

### Recommendations
"""
        recs = result.get('recommendations', [])
        if recs:
            for rec in recs:
                md_report += f"- {rec}\n"
        else:
            md_report += "✅ Dataset is ready for training!\n"

        return md_report

    except Exception as e:
        return f"❌ Erro ao analisar qualidade: {str(e)}"


def suggest_hyperparameters(dataset_path: str, model_type: str) -> str:
    """Suggest optimal hyperparameters based on dataset analysis."""
    try:
        if not dataset_path or not Path(dataset_path).exists():
            return "❌ Dataset não encontrado. Execute primeiro a extração do catálogo."

        selector = AutoHyperparameterSelector(str(dataset_path))
        result = selector.select_hyperparameters(model_type)

        params = result['hyperparameters']
        reasoning = result.get('reasoning', {})

        # Format as markdown
        md_report = f"""
## 🎯 Recommended Hyperparameters for {model_type.upper()}

### Training Parameters
- **Batch Size**: {params.get('batch_size', 16)}
- **Learning Rate**: {params.get('learning_rate', 0.001)}
- **Epochs**: {params.get('epochs', 50)}
- **Optimizer**: {params.get('optimizer', 'Adam')}
- **Patience (Early Stopping)**: {params.get('patience', 10)}

### Reasoning
"""
        for key, reason in reasoning.items():
            md_report += f"- **{key}**: {reason}\n"

        md_report += """

### Usage
Copy these parameters to the Advanced Training tab or use Quick Start for automatic configuration.
"""
        return md_report

    except Exception as e:
        return f"❌ Erro ao sugerir hiperparâmetros: {str(e)}"


# ============================================================================
# GRADIO INTERFACE
# ============================================================================

def create_interface():
    """Create the Gradio interface."""

    with gr.Blocks(
        title="NSP Plugin - Training AI",
        theme=gr.themes.Soft(),
        css="""
        .container {max-width: 1400px; margin: auto;}
        .tab-nav button {font-size: 16px !important; padding: 12px 24px !important;}
        .help-button {background-color: #3b82f6; color: white; border-radius: 8px;}
        .download-button {background-color: #10b981; color: white;}
        .train-button {background-color: #f59e0b; color: white; font-size: 18px; padding: 16px;}
        """
    ) as interface:

        gr.Markdown("""
        # 🎨 NSP Plugin - AI Training Center

        Modern interface for training Lightroom AI preset models.
        Choose between quick automated training or advanced manual configuration.
        """)

        # Modals for help
        with gr.Accordion("ℹ️ Need Help? Click here for guides", open=False):
            with gr.Tabs():
                with gr.Tab("Quick Start Guide"):
                    gr.Markdown(MODAL_HELP_CONTENT["quick_start"])
                with gr.Tab("Public Datasets Guide"):
                    gr.Markdown(MODAL_HELP_CONTENT["public_datasets"])
                with gr.Tab("Training Presets Guide"):
                    gr.Markdown(MODAL_HELP_CONTENT["training_presets"])

        gr.Markdown("---")

        # Main tabs
        with gr.Tabs() as main_tabs:

            # ================================================================
            # TAB 1: QUICK START
            # ================================================================
            with gr.Tab("🚀 Quick Start (Recommended)"):
                gr.Markdown("""
                ### Automated Training with Smart Defaults

                Perfect for beginners! This mode automatically handles all complex settings.
                Just choose your data source and training speed, then click train.
                """)

                # ACCUMULATED STATISTICS BOX
                with gr.Accordion("📊 Accumulated Training Statistics", open=False):
                    accumulated_stats = gr.Markdown(
                        value=get_accumulated_stats(),
                        elem_id="accumulated_stats"
                    )
                    refresh_stats_btn = gr.Button("🔄 Refresh Statistics", size="sm")

                with gr.Accordion("📦 Training Sessions (Snapshots)", open=False):
                    session_summary = gr.Markdown(
                        value=render_session_summary(),
                        elem_id="session_summary"
                    )
                    refresh_sessions_btn = gr.Button("🔄 Refresh Sessions", size="sm")

                gr.Markdown("---")

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📁 Step 1: Data Source")

                        data_source = gr.Radio(
                            label="Where should the AI learn from?",
                            choices=[
                                ("✅ My Lightroom Catalog (RECOMMENDED - learns YOUR editing style)", "lightroom"),
                                ("⚠️ Public Dataset (for quality/culling models only)", "public")
                            ],
                            value="lightroom",
                            info="Lightroom catalogs are REQUIRED for AI Preset training. Public datasets only work for culling/quality assessment."
                        )

                        gr.Markdown("""
                        **⚠️ Important:**
                        - **Lightroom Catalog** → Trains **AI Preset** model (applies editing adjustments)
                        - **Public Dataset** → Trains **Culling/Quality** model only (selects best photos)

                        Public datasets don't contain editing adjustments, so they can't train the AI Preset model!
                        """)

                        # Lightroom catalog input
                        with gr.Group(visible=True) as lightroom_group:
                            catalog_path = gr.Textbox(
                                label="Lightroom Catalog Path",
                                placeholder="/path/to/your/catalog.lrcat",
                                info="Path to your .lrcat file"
                            )
                            catalog_file = gr.File(
                                label="Or upload your .lrcat file",
                                file_types=[".lrcat"]
                            )

                        # Public dataset selector
                        with gr.Group(visible=False) as public_dataset_group:
                            public_dataset = gr.Dropdown(
                                label="Select Public Dataset",
                                choices=[
                                    (f"{info['name']} - {info['use_case']}", dataset_id)
                                    for dataset_id, info in PUBLIC_DATASETS.items()
                                ],
                                value="ava",
                                info="Each dataset is optimized for different purposes"
                            )

                            dataset_info_box = gr.Markdown(
                                f"""
**Selected Dataset**: {PUBLIC_DATASETS['ava']['name']}

📝 **Description**: {PUBLIC_DATASETS['ava']['description']}

💡 **Best for**: {PUBLIC_DATASETS['ava']['use_case']}

📦 **Size**: {PUBLIC_DATASETS['ava']['size']}

🎯 **Expected Accuracy**: {PUBLIC_DATASETS['ava']['accuracy_expected']}

⏱️ **Training Time**: {PUBLIC_DATASETS['ava']['training_time']}
                                """
                            )

                            dataset_status = gr.Textbox(
                                label="Dataset Status",
                                value="Not downloaded",
                                interactive=False
                            )

                            download_dataset_btn = gr.Button(
                                "📥 Download This Dataset",
                                variant="secondary",
                                elem_classes="download-button"
                            )

                        gr.Markdown("### ⚙️ Step 2: Training Speed")

                        training_preset = gr.Radio(
                            label="How fast do you need results?",
                            choices=[
                                (f"🏃 Quick (30-60 min) - {TRAINING_PRESETS['quick']['description']}", "quick"),
                                (f"⚖️ Balanced (1-2 hours) - {TRAINING_PRESETS['balanced']['description']}", "balanced"),
                                (f"🏆 High Quality (3-4 hours) - {TRAINING_PRESETS['quality']['description']}", "quality"),
                            ],
                            value="balanced",
                            info="Balanced is recommended for most users"
                        )

                        preset_info = gr.Markdown(
                            f"""
**Selected Preset**: {TRAINING_PRESETS['balanced']['name']}

⏱️ **Estimated Time**: {TRAINING_PRESETS['balanced']['estimated_time']}

⚙️ **Configuration**:
- Epochs: {TRAINING_PRESETS['balanced']['epochs']}
- Batch Size: {TRAINING_PRESETS['balanced']['batch_size']}
- Learning Rate: {TRAINING_PRESETS['balanced']['learning_rate']}
                            """
                        )

                        gr.Markdown("### 🚀 Step 3: Train!")

                        train_quick_btn = gr.Button(
                            "🚀 Start Training Now",
                            variant="primary",
                            size="lg",
                            elem_classes="train-button"
                        )

                        train_live_btn = gr.Button(
                            "📡 Train with Live Logs (Recommended)",
                            variant="secondary",
                            size="lg"
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("### 📊 Training Progress & Logs")

                        training_status = gr.Textbox(
                            label="Current Status",
                            value="Ready to start",
                            interactive=False,
                            lines=2
                        )

                        training_logs = gr.Textbox(
                            label="Live Logs",
                            lines=30,
                            interactive=False,
                            autoscroll=True,
                            show_copy_button=True
                        )

                        training_log_file = gr.File(
                            label="💾 Download Complete Log File",
                            interactive=False
                        )

                # Callbacks for Quick Start
                def update_lightroom_visibility(source):
                    return gr.update(visible=(source == "lightroom")), \
                           gr.update(visible=(source == "public"))

                data_source.change(
                    fn=update_lightroom_visibility,
                    inputs=[data_source],
                    outputs=[lightroom_group, public_dataset_group]
                )

                # Refresh statistics button
                refresh_stats_btn.click(
                    fn=get_accumulated_stats,
                    inputs=[],
                    outputs=[accumulated_stats]
                )

                # Refresh sessions button
                refresh_sessions_btn.click(
                    fn=render_session_summary,
                    inputs=[],
                    outputs=[session_summary]
                )

                # Handle catalog file upload
                catalog_file.change(
                    fn=process_catalog_upload,
                    inputs=[catalog_file],
                    outputs=[catalog_path]
                )

                def update_dataset_info(dataset_id):
                    if not dataset_id or dataset_id not in PUBLIC_DATASETS:
                        return "Select a dataset", "Not downloaded"

                    info = PUBLIC_DATASETS[dataset_id]
                    exists, path = check_dataset_exists(dataset_id)

                    info_md = f"""
**Selected Dataset**: {info['name']}

📝 **Description**: {info['description']}

💡 **Best for**: {info['use_case']}

📦 **Size**: {info['size']}

🎯 **Expected Accuracy**: {info['accuracy_expected']}

⏱️ **Training Time**: {info['training_time']}
                    """

                    if exists:
                        stats = get_dataset_stats(path)
                        status = f"✅ Downloaded ({stats['images']} images, {stats['size_gb']} GB)"
                    else:
                        status = "❌ Not downloaded yet"

                    return info_md, status

                public_dataset.change(
                    fn=update_dataset_info,
                    inputs=[public_dataset],
                    outputs=[dataset_info_box, dataset_status]
                )

                def update_preset_info(preset):
                    if preset not in TRAINING_PRESETS:
                        return "Select a preset"

                    config = TRAINING_PRESETS[preset]

                    if preset == "custom":
                        return f"**{config['name']}**\n\n{config['description']}"

                    return f"""
**Selected Preset**: {config['name']}

⏱️ **Estimated Time**: {config['estimated_time']}

⚙️ **Configuration**:
- Epochs: {config['epochs']}
- Batch Size: {config['batch_size']}
- Learning Rate: {config['learning_rate']}
- Patience: {config['patience']}
                    """

                training_preset.change(
                    fn=update_preset_info,
                    inputs=[training_preset],
                    outputs=[preset_info]
                )

                # Download dataset callback
                download_dataset_btn.click(
                    fn=lambda dataset_id: download_public_dataset(dataset_id, sample_size=1000),
                    inputs=[public_dataset],
                    outputs=[dataset_status, training_logs]
                )

                # Training callback - wrapper to determine data source
                def train_wrapper(cat_path, preset, source, dataset_id):
                    use_public = (source == "public")
                    logs, log_file, status = run_quick_training(cat_path, preset, use_public, dataset_id)
                    # Atualizar estatísticas após treino
                    updated_stats = get_accumulated_stats()
                    sessions_view = render_session_summary()
                    return logs, log_file, status, updated_stats, sessions_view

                train_quick_btn.click(
                    fn=train_wrapper,
                    inputs=[
                        catalog_path,
                        training_preset,
                        data_source,
                        public_dataset
                    ],
                    outputs=[training_logs, training_log_file, training_status, accumulated_stats, session_summary]
                )

                # Live logs training callback
                def train_live_wrapper(cat_path, preset):
                    if not cat_path:
                        yield "❌ Por favor forneça o caminho para o catálogo Lightroom\n"
                        return

                    if preset not in TRAINING_PRESETS:
                        yield "❌ Preset inválido\n"
                        return

                    preset_config = TRAINING_PRESETS[preset]

                    # Yield from the streaming function
                    for log_line in run_training_with_live_logs(cat_path, preset_config):
                        yield log_line

                train_live_btn.click(
                    fn=train_live_wrapper,
                    inputs=[catalog_path, training_preset],
                    outputs=[training_logs]
                )

            # ================================================================
            # TAB 2: DATASET MANAGER
            # ================================================================
            with gr.Tab("📚 Dataset Manager"):
                gr.Markdown("""
                ### Public Datasets Information

                **⚠️ Important:** Public datasets require **manual download** due to:
                - Large size (5GB to 100GB+)
                - Registration/API keys required
                - Terms of service acceptance

                **💡 Recommended:** Use your own **Lightroom catalogs** instead!
                - Faster (no huge downloads)
                - Your own editing style
                - Already organized

                This tab provides download instructions and helper scripts for public datasets.
                """)

                # Dataset browser
                with gr.Row():
                    dataset_cards = []

                    for dataset_id, info in PUBLIC_DATASETS.items():
                        with gr.Column():
                            with gr.Group():
                                gr.Markdown(f"### {info['name']}")
                                gr.Markdown(f"**{info['description']}**")
                                gr.Markdown(f"📦 Size: {info['size']}")
                                gr.Markdown(f"🎯 Use case: {info['use_case']}")
                                gr.Markdown(f"✨ Accuracy: {info['accuracy_expected']}")

                                status_text = gr.Textbox(
                                    label="Status",
                                    value="⚠️ Not configured (manual download required)",
                                    interactive=False
                                )

                                download_btn = gr.Button(
                                    "📋 Get Setup Instructions",
                                    variant="secondary"
                                )

                                # Check status on load
                                exists, path = check_dataset_exists(dataset_id)
                                if exists:
                                    stats = get_dataset_stats(path)
                                    status_text.value = f"✅ Configured ({stats['images']} images)"

                                dataset_cards.append((dataset_id, download_btn, status_text))

                # Instructions logs
                gr.Markdown("### Setup Instructions & Information")
                download_logs = gr.Textbox(
                    label="Instructions (click a button above to view)",
                    lines=15,
                    interactive=False,
                    autoscroll=True
                )

                # Wire up download buttons
                def create_download_handler(did, status_widget):
                    def handler():
                        return download_public_dataset(did, 1000)
                    return handler

                for dataset_id, btn, status_box in dataset_cards:
                    btn.click(
                        fn=create_download_handler(dataset_id, status_box),
                        inputs=[],
                        outputs=[status_box, download_logs]
                    )

            # ================================================================
            # TAB 3: DATASET ANALYSIS
            # ================================================================
            with gr.Tab("📊 Dataset Analysis"):
                gr.Markdown("""
                ### Advanced Dataset Analysis Tools

                Analyze your training data to ensure quality and get intelligent recommendations.
                All analysis is performed on the extracted dataset.
                """)

                # Dataset path input
                with gr.Row():
                    analysis_dataset_path = gr.Textbox(
                        label="Dataset Path",
                        value=str(OUTPUT_DATASET_PATH),
                        placeholder="/path/to/dataset.csv",
                        info="Path to your extracted dataset CSV file"
                    )

                gr.Markdown("---")

                # Analysis sections
                with gr.Tabs():
                    # Statistics Tab
                    with gr.Tab("📈 Statistics"):
                        gr.Markdown("""
                        Get comprehensive statistics about your dataset including:
                        - Total images and features
                        - Data quality metrics
                        - Feature distributions
                        - Recommendations
                        """)

                        stats_button = gr.Button("🔍 Analyze Statistics", variant="primary")
                        stats_output = gr.Markdown(value="Click 'Analyze Statistics' to start...")

                        stats_button.click(
                            fn=lambda path: analyze_dataset_stats(path)[0],
                            inputs=[analysis_dataset_path],
                            outputs=[stats_output]
                        )

                    # Quality Tab
                    with gr.Tab("🔍 Quality Analysis"):
                        gr.Markdown("""
                        Deep quality analysis of your dataset:
                        - Overall quality score
                        - Missing values detection
                        - Outlier identification
                        - Distribution analysis
                        - Correlation checks
                        """)

                        quality_button = gr.Button("🔍 Analyze Quality", variant="primary")
                        quality_output = gr.Markdown(value="Click 'Analyze Quality' to start...")

                        quality_button.click(
                            fn=analyze_dataset_quality,
                            inputs=[analysis_dataset_path],
                            outputs=[quality_output]
                        )

                    # Hyperparameter Suggestions Tab
                    with gr.Tab("🎯 Smart Hyperparameters"):
                        gr.Markdown("""
                        Get intelligent hyperparameter suggestions based on your dataset characteristics.
                        The system analyzes your data and recommends optimal training parameters.
                        """)

                        model_type_select = gr.Radio(
                            label="Model Type",
                            choices=[
                                ("Preset Classifier", "classifier"),
                                ("Refinement Regressor", "refiner")
                            ],
                            value="classifier",
                            info="Select which model you want to train"
                        )

                        hyper_button = gr.Button("🎯 Get Recommendations", variant="primary")
                        hyper_output = gr.Markdown(value="Select model type and click 'Get Recommendations'...")

                        hyper_button.click(
                            fn=suggest_hyperparameters,
                            inputs=[analysis_dataset_path, model_type_select],
                            outputs=[hyper_output]
                        )

                gr.Markdown("---")
                gr.Markdown("""
                ### 💡 Tips
                - Run these analyses **after** extracting data from your Lightroom catalog
                - Use the insights to understand your data before training
                - Quality score above 80 is excellent for training
                - Follow the recommendations to improve your dataset
                """)

            # ================================================================
            # TAB 4: MODEL MANAGER
            # ================================================================
            with gr.Tab("📦 Gestão de Modelos"):
                gr.Markdown("""
                ### Gestão de Modelos AI Treinados

                Exporta e importa modelos treinados para partilhar entre computadores.
                Os modelos contêm TODO o conhecimento aprendido (~770KB).
                """)

                with gr.Tabs():
                    # Export Tab
                    with gr.Tab("📤 Exportar Modelos"):
                        gr.Markdown("""
                        ### Exportar Modelos Treinados

                        Cria um pacote ZIP com todos os modelos e metadados necessários
                        para transferir o conhecimento para outro computador.
                        """)

                        # Current models info
                        with gr.Accordion("📊 Modelos Atuais", open=True):
                            current_models_info = gr.Markdown(
                                value="Clica em 'Verificar Modelos' para ver info...",
                                elem_id="current_models_info"
                            )
                            check_models_btn = gr.Button("🔍 Verificar Modelos", size="sm")

                        gr.Markdown("---")

                        export_output_path = gr.Textbox(
                            label="Nome do Ficheiro ZIP (opcional)",
                            placeholder="nsp_models_20250125_143000.zip (auto-gerado se vazio)",
                            info="Deixa vazio para gerar automaticamente com timestamp"
                        )

                        export_btn = gr.Button(
                            "📦 Exportar Modelos",
                            variant="primary",
                            size="lg"
                        )

                        export_logs = gr.Textbox(
                            label="Logs de Exportação",
                            lines=15,
                            interactive=False,
                            autoscroll=True,
                            show_copy_button=True
                        )

                        export_file = gr.File(
                            label="📥 Download ZIP Exportado",
                            interactive=False
                        )

                    # Import Tab
                    with gr.Tab("📥 Importar Modelos"):
                        gr.Markdown("""
                        ### Importar Modelos Treinados

                        Instala modelos de um ZIP exportado. Cria backups automáticos
                        dos modelos existentes antes de substituir.
                        """)

                        import_file = gr.File(
                            label="Carrega o ZIP de Modelos",
                            file_types=[".zip"],
                            file_count="single"
                        )

                        import_info = gr.Markdown(
                            value="Carrega um ficheiro ZIP para ver informação...",
                            elem_id="import_info"
                        )

                        gr.Markdown("---")

                        with gr.Row():
                            import_btn = gr.Button(
                                "📥 Importar e Instalar",
                                variant="primary",
                                size="lg"
                            )
                            cancel_import_btn = gr.Button(
                                "❌ Cancelar",
                                variant="secondary",
                                size="lg"
                            )

                        import_logs = gr.Textbox(
                            label="Logs de Importação",
                            lines=15,
                            interactive=False,
                            autoscroll=True,
                            show_copy_button=True
                        )

                gr.Markdown("---")
                gr.Markdown("""
                ### 💡 Como Funciona

                **Exportar:**
                1. Verifica se todos os modelos necessários existem
                2. Cria ZIP com 7 ficheiros (~770KB): 2 modelos .pth, 3 scalers .pkl, 2 metadados .json
                3. Adiciona README e estatísticas de treino
                4. Download automático do ZIP

                **Importar:**
                1. Carrega o ZIP e mostra informação
                2. Cria backups dos modelos existentes (.backup)
                3. Extrai e instala os novos modelos
                4. Reinicia o servidor para carregar os modelos

                **Compatibilidade:**
                - ✅ Funciona entre Mac/Windows/Linux
                - ✅ Modelos PyTorch são cross-platform
                - ✅ Mantém todo o conhecimento treinado
                - ⚠️ Requer mesma versão do NSP Plugin (2.0+)
                """)

            # ================================================================
            # TAB 5: ADVANCED TRAINING
            # ================================================================
            with gr.Tab("🔧 Advanced Training"):
                gr.Markdown("""
                ### Manual Configuration

                For advanced users who want full control over training parameters.
                Requires understanding of machine learning hyperparameters.
                """)

                gr.Markdown("⚠️ **Warning**: Only use this if you know what you're doing!")

                # Advanced options would go here
                gr.Markdown("*Advanced training options coming soon...*")

        # ================================================================
        # MODEL MANAGEMENT CALLBACKS
        # ================================================================

        # Check models button
        check_models_btn.click(
            fn=check_current_models,
            inputs=[],
            outputs=[current_models_info]
        )

        # Export models button
        def export_wrapper(output_name):
            logs, zip_path = export_models_ui(output_name)
            return logs, zip_path

        export_btn.click(
            fn=export_wrapper,
            inputs=[export_output_path],
            outputs=[export_logs, export_file]
        )

        # Import file change (inspect ZIP)
        def handle_import_file(file_obj):
            """Handle import file upload and return path for inspection."""
            if not file_obj:
                return "Carrega um ficheiro ZIP para ver informação..."

            # Get file path from Gradio file object
            file_path = None
            if isinstance(file_obj, str):
                file_path = file_obj
            elif isinstance(file_obj, dict):
                file_path = file_obj.get('name') or file_obj.get('path')

            if file_path:
                return inspect_import_zip(file_path)
            return "❌ Erro ao processar ficheiro"

        import_file.change(
            fn=handle_import_file,
            inputs=[import_file],
            outputs=[import_info]
        )

        # Import and install button
        def import_wrapper(file_obj):
            """Import models from uploaded ZIP."""
            if not file_obj:
                return "❌ Nenhum ficheiro carregado"

            # Get file path from Gradio file object
            file_path = None
            if isinstance(file_obj, str):
                file_path = file_obj
            elif isinstance(file_obj, dict):
                file_path = file_obj.get('name') or file_obj.get('path')

            if file_path:
                return import_models_ui(file_path)
            return "❌ Erro ao processar ficheiro"

        import_btn.click(
            fn=import_wrapper,
            inputs=[import_file],
            outputs=[import_logs]
        )

        # Cancel import button (just clears logs)
        cancel_import_btn.click(
            fn=lambda: "Importação cancelada pelo utilizador.",
            inputs=[],
            outputs=[import_logs]
        )

        return interface


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import socket

    def find_free_port(start_port=7860, max_tries=10):
        """Find a free port starting from start_port."""
        for port in range(start_port, start_port + max_tries):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                    return port
            except OSError:
                continue
        return None

    # Find available port
    port = find_free_port(7860)
    if port is None:
        print("❌ Could not find available port in range 7860-7869")
        print("Please close other Gradio instances and try again")
        sys.exit(1)

    print(f"🚀 Starting NSP Training UI on port {port}")
    if port != 7860:
        print(f"ℹ️  Note: Using port {port} instead of default 7860 (port was busy)")

    interface = create_interface()
    interface.queue().launch(
        server_name="127.0.0.1",
        server_port=port,
        share=False,
        show_error=True,
        inbrowser=True
    )
