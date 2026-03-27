# NSP Plugin — Neural Style Presets for Adobe Lightroom

> **AI-powered preset prediction engine that learns your editing style and applies it automatically.**

NSP Plugin analyses your existing Lightroom edits, identifies recurring patterns, and trains a two-stage neural network to replicate your personal style on any new photo — all without leaving Lightroom Classic.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.2-orange)](https://pytorch.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## How It Works

```
Your Lightroom Catalog
        │
        ▼
┌───────────────────┐    ┌─────────────────────────────────────────┐
│  Training Pipeline │    │              Inference                   │
│                   │    │                                           │
│  1. Extract edits │    │  New Photo → Stat Features + Deep Features│
│  2. Cluster into  │    │                    │                      │
│     N presets     │    │                    ▼                      │
│  3. Train         │    │          Preset Classifier                │
│     Classifier    │    │        "Which style fits best?"           │
│  4. Train         │    │                    │                      │
│     Refinement    │    │                    ▼                      │
│     Regressor     │    │         Refinement Regressor              │
│                   │    │       "Fine-tune 60+ parameters"          │
└───────────────────┘    │                    │                      │
                         │                    ▼                      │
                         │          Lightroom Adjustments            │
                         │      (Basic, Tone, HSL, Effects…)        │
                         └─────────────────────────────────────────┘
```

The ML pipeline has two stages:

1. **Preset Classifier** (`OptimizedPresetClassifier`) — A lightweight MLP that maps image features to one of N learned preset clusters. Uses class-weighted CrossEntropyLoss + OneCycleLR + optional curriculum learning.

2. **Refinement Regressor** (`OptimizedRefinementRegressor`) — Predicts per-parameter deltas on top of the chosen preset's centre values. Supports 60+ Lightroom parameters across Basic, Tone Curve, HSL, Split Toning, Sharpening, Noise Reduction, Effects, Lens Corrections, and Calibration panels.

---

## Features

- **Learns your style** — trains exclusively on your own Lightroom edits
- **Two-stage prediction** — coarse preset selection + fine-grained parameter tuning
- **Progressive / curriculum training** — starts with easy examples, gradually adds harder ones
- **Class-weighted loss** — handles imbalanced preset usage automatically
- **Deep feature extraction** — ResNet18 transfer learning + 100+ statistical image features
- **Parallel feature extraction** — multi-worker batch processing with persistent cache
- **Async batch processing** — submit batches from Lightroom, results applied automatically
- **Active learning** — feedback loop: approve/reject predictions to improve the model
- **FastAPI inference server** — lightweight, local, no cloud required
- **Lightroom Classic plugin** — native Lua integration with progress tracking and version checks
- **Control Center** — desktop UI for training management and monitoring (Tauri + Python backend)

---

## Quick Start

### 1 — Install

```bash
# macOS / Linux
./install/setup.sh

# Windows
install\setup.bat
```

### 2 — Configure catalog path

```bash
cp .env.example .env
# Edit .env and set LIGHTROOM_CATALOG_PATH
```

### 3 — Train models on your catalog

```bash
python train/train_models_v2.py
```

### 4 — Start inference server

```bash
./start_server.sh
# Server starts at http://127.0.0.1:5678
```

### 5 — Use in Lightroom Classic

1. Open Lightroom Classic
2. Select one or more photos
3. `File → Plug-in Extras → AI Preset V2`
4. Confirm the applied adjustments

---

## Installation — Detailed

**Requirements:**
- macOS 10.14+ or Windows 10+
- Python 3.11+
- Adobe Lightroom Classic 10+
- 8 GB RAM minimum (16 GB recommended for training)
- 5 GB free disk space

```bash
# Clone the repository
git clone https://github.com/nelsonsilva/nsp-plugin.git
cd nsp-plugin

# Create virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Install the Lightroom plugin
# Copy NSP-Plugin.lrplugin/ to your Lightroom Plug-ins folder:
# macOS: ~/Library/Application Support/Adobe/Lightroom/Modules/
# Windows: %APPDATA%\Adobe\Lightroom\Modules\
```

---

## Training Your Model

### Prepare the dataset

The training script reads directly from your Lightroom catalog:

```bash
# Set catalog path (or export LIGHTROOM_CATALOG_PATH in .env)
python train/train_models_v2.py
```

Training stages:
1. **Extract** photo metadata and edit parameters from catalog
2. **Cluster** photos into N preset groups (k-means on parameter space)
3. **Extract features** — 100+ statistical features per image + ResNet18 deep embeddings
4. **Split** — 70% train / 15% validation / 15% test (stratified)
5. **Train Classifier** — with class weights, data augmentation, OneCycleLR
6. **Train Regressor** — weighted MSE loss, early stopping, best-model checkpoint
7. **Save** models, scalers, and metadata to `models/`

### Key hyperparameters (`train/train_models_v2.py`)

| Variable | Default | Description |
|---|---|---|
| `NUM_PRESETS` | 4 | Number of style clusters |
| `CLASSIFIER_EPOCHS` | 50 | Max classifier training epochs |
| `REFINER_EPOCHS` | 100 | Max regressor training epochs |
| `BATCH_SIZE` | 16 | Training batch size |
| `PATIENCE` | 10 | Early stopping patience |
| `USE_PROGRESSIVE_TRAINING` | True | Enable curriculum learning |
| `USE_DATA_AUGMENTATION` | True | Feature-space augmentation |

---

## API Reference

The inference server exposes a REST API on `http://127.0.0.1:5678`.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check + server info |
| `GET` | `/version` | Server and model versions |
| `POST` | `/predict` | Single-image prediction |
| `POST` | `/predict/base64` | Predict from base64-encoded image |
| `POST` | `/batch/submit` | Submit batch of images |
| `GET` | `/batch/{job_id}/status` | Poll batch job progress |
| `GET` | `/batch/{job_id}/results` | Retrieve batch results |
| `POST` | `/feedback` | Submit correction feedback |
| `GET` | `/health` | Detailed health + model status |

### Example — Single prediction

```bash
curl -X POST http://127.0.0.1:5678/predict \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/path/to/photo.jpg"}'
```

Response:
```json
{
  "preset_id": 2,
  "preset_confidence": 0.87,
  "final_params": {
    "exposure": 0.35,
    "contrast": 12,
    "highlights": -45,
    "shadows": 28,
    "temperature": 5400,
    "...": "..."
  }
}
```

### Authentication (optional)

Enable in `config.json`:
```json
{ "security": { "api_auth_enabled": true } }
```

Generate and use a key:
```bash
python manage_api_keys.py generate "My Plugin" --level standard

curl -H "Authorization: Bearer nsp_xxxx..." http://127.0.0.1:5678/predict
```

---

## Project Structure

```
nsp-plugin/
├── NSP-Plugin.lrplugin/         # Lightroom Classic plugin (Lua)
│   ├── Info.lua                 # Plugin manifest
│   ├── ApplyPresetV2.lua        # Main menu action
│   ├── Common_V2.lua            # Shared utilities & API client
│   └── ProgressDialog.lua      # Progress/feedback UI
│
├── services/                    # Python backend
│   ├── server.py                # FastAPI app entry point
│   ├── api_auth.py              # API key authentication
│   ├── batch_processor.py       # Async batch job queue
│   ├── active_learning.py       # Feedback → retraining loop
│   └── ai_core/                 # ML core
│       ├── predictor.py             # LightroomAIPredictor
│       ├── model_architectures_v2.py # Neural network definitions
│       ├── trainer_v2.py            # Optimized trainers
│       ├── image_feature_extractor.py   # Statistical features
│       ├── deep_feature_extractor.py    # ResNet18 embeddings
│       ├── training_utils.py        # Dataset + loss utilities
│       ├── data_augmentation.py     # Feature-space augmentation
│       └── feature_selector.py      # Variance/importance selection
│
├── train/                       # Training scripts
│   ├── train_models_v2.py       # Main training pipeline
│   ├── training_validator.py    # Pre-training data quality checks
│   └── training_progress.py     # Progress tracking + ETA
│
├── control-center-v2/           # Desktop management UI
│   ├── backend/                 # Python dashboard API
│   └── desktop/                 # Tauri desktop app
│
├── models/                      # Trained model artifacts
│   ├── best_preset_classifier_v2.pth
│   ├── best_refinement_model_v2.pth
│   ├── scaler_stat.pkl / scaler_deep.pkl / scaler_deltas.pkl
│   ├── preset_centers.json      # Per-preset average parameters
│   └── delta_columns.json       # List of delta parameter names
│
├── tests/                       # Test suite
├── tools/                       # CLI utilities
├── install/                     # Setup scripts
├── docs/                        # Extended documentation
│
├── config.json                  # Runtime configuration
├── .env.example                 # Environment variable template
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
├── pyproject.toml               # Build + tool configuration
└── start_server.sh / stop_server.sh
```

---

## Configuration

`config.json` controls runtime behaviour:

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 5678
  },
  "models": {
    "classifier_path": "models/best_preset_classifier_v2.pth",
    "refiner_path": "models/best_refinement_model_v2.pth",
    "preset_centers": "models/preset_centers.json",
    "delta_columns": "models/delta_columns.json",
    "scaler_stat": "models/scaler_stat.pkl",
    "scaler_deep": "models/scaler_deep.pkl",
    "scaler_deltas": "models/scaler_deltas.pkl"
  },
  "security": {
    "api_auth_enabled": false
  }
}
```

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Lint
ruff check .

# Format
ruff format .
```

---

## Troubleshooting

**Server does not start**
```bash
# Check if port is in use
lsof -i :5678
# Check logs
cat logs/server.log
```

**Plugin does not appear in Lightroom**
1. Open `File → Plug-in Manager`
2. Verify the path points to `NSP-Plugin.lrplugin/`
3. Reload the plugin

**Models not found**
```bash
ls -lh models/*.pth     # verify models exist
python train/train_models_v2.py   # retrain if needed
```

**"Preset ID not found" error**
The loaded `preset_centers.json` must match the trained model. Retrain or restore matching artifacts to `models/`.

---

## Roadmap

### v2.1
- [ ] Web dashboard for preset management
- [ ] Multi-catalog support
- [ ] Granular per-parameter feedback

### v3.0
- [ ] Cloud-based training for larger datasets
- [ ] Preset sharing / marketplace
- [ ] Video colour grading support

---

## Documentation

- [Installation Guide](docs/user-guide/installation.md)
- [Quick Testing Guide](docs/user-guide/quick-testing-guide.md)
- [Troubleshooting](docs/user-guide/troubleshooting.md)
- [Architecture](docs/developer/architecture.md)
- [ML Optimizations](docs/developer/ml-optimizations.md)
- [Training Guide](docs/developer/training-ui.md)

---

## License

[MIT](LICENSE) — © 2025 Nelson Silva
