"""
Pipeline de treino para o modo Reference Match.

Uso:
    python train/train_reference_model.py

Pré-requisitos:
    1. Catálogo Lightroom com fotos editadas (LIGHTROOM_CATALOG_PATH em .env)
    2. JPEGs exportados das fotos editadas em data/previews/
       (gerados por tools/extract_lightroom_previews.py ou exportação manual)

Pipeline:
    1. Extrair dados do catálogo (reutiliza LightroomCatalogExtractor)
    2. Agrupar fotos por sessão (data de captura)
    3. Extrair features estatísticas e deep features (reutiliza extractors existentes)
    4. Extrair style fingerprints dos JPEGs editados (StyleFingerprintExtractor)
    5. Construir pares de treino (para cada foto P, cada R da mesma sessão = 1 amostra)
    6. Normalizar e dividir 70/15/15
    7. Treinar ReferenceRegressor
    8. Avaliar no test set e guardar métricas
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from services.ai_core.deep_feature_extractor import DeepFeatureExtractor
from services.ai_core.image_feature_extractor import ImageFeatureExtractor
from services.ai_core.lightroom_extractor import LightroomCatalogExtractor
from services.ai_core.reference_match_trainer import ReferenceMatchTrainer
from services.ai_core.reference_pair_dataset import ReferencePairDataset
from services.ai_core.reference_regressor import ReferenceRegressor
from services.ai_core.style_fingerprint_extractor import StyleFingerprintExtractor

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

CATALOG_PATH = Path(os.environ.get('LIGHTROOM_CATALOG_PATH', 'path/to/Lightroom Catalog.lrcat'))
PREVIEWS_DIR = Path('data/previews')
MODELS_DIR = Path('models')
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MIN_RATING = 3
BATCH_SIZE = 16
EPOCHS = 100
PATIENCE = 15
MAX_LR = 0.005
WEIGHT_DECAY = 0.02
STYLE_DIM = 128
USE_MIXED_PRECISION = True

# Pesos de importância dos parâmetros (reutilizar da versão Style Learner)
PARAM_IMPORTANCE = {
    'exposure': 2.0, 'contrast': 1.5, 'highlights': 1.8, 'shadows': 1.8,
    'whites': 1.3, 'blacks': 1.3, 'texture': 1.2, 'clarity': 1.0,
    'dehaze': 0.8, 'vibrance': 1.2, 'saturation': 1.2, 'temp': 2.0,
    'tint': 1.0, 'sharpen_amount': 0.7, 'nr_luminance': 0.6,
    'vignette': 0.9, 'grain': 0.6,
    'hsl_red_hue': 1.2, 'hsl_red_saturation': 1.2,
    'hsl_orange_hue': 1.3, 'hsl_orange_saturation': 1.3,
    'hsl_blue_hue': 1.2, 'hsl_blue_saturation': 1.2,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_log_dir = Path('logs')
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / f"train_reference_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_fh = logging.FileHandler(_log_file, encoding='utf-8')
_fh.setFormatter(_formatter)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger().addHandler(_fh)
logger = logging.getLogger(__name__)
logger.info(f"Log de treino: {_log_file}")


# ---------------------------------------------------------------------------
# Passo 1 — Extrair dados do catálogo
# ---------------------------------------------------------------------------

def load_catalog_data(catalog_path: Path, min_rating: int) -> pd.DataFrame:
    """Extrai dataset do catálogo Lightroom."""
    logger.info("PARTE 1: Extração de dados do catálogo")
    extractor = LightroomCatalogExtractor(catalog_path)
    dataset = extractor.create_dataset(min_rating=min_rating)
    if dataset.empty:
        raise ValueError("Dataset vazio. Verifique o catálogo e min_rating.")
    logger.info(f"  {len(dataset)} fotos extraídas")
    return dataset


# ---------------------------------------------------------------------------
# Passo 2 — Agrupar por sessão
# ---------------------------------------------------------------------------

def group_by_session(dataset: pd.DataFrame) -> Dict[str, List[int]]:
    """
    Agrupa índices do dataset por data de captura (sessão).

    Retorna dict {session_id -> [row_indices]}.
    """
    logger.info("PARTE 2: Agrupamento por sessão (data de captura)")
    date_col = None
    for col in ('capture_date', 'captureTime', 'date_taken', 'date'):
        if col in dataset.columns:
            date_col = col
            break

    if date_col is None:
        logger.warning("Coluna de data não encontrada — usando uma sessão única")
        return {'session_0': list(dataset.index)}

    sessions: Dict[str, List[int]] = {}
    for idx, row in dataset.iterrows():
        date_str = str(row[date_col])[:10]  # "YYYY-MM-DD"
        sessions.setdefault(date_str, []).append(idx)

    sessions = {k: v for k, v in sessions.items() if len(v) >= 2}
    logger.info(f"  {len(sessions)} sessões com ≥2 fotos")
    total_photos = sum(len(v) for v in sessions.values())
    logger.info(f"  {total_photos} fotos utilizáveis")
    return sessions


# ---------------------------------------------------------------------------
# Passo 3+4 — Extrair features e style fingerprints
# ---------------------------------------------------------------------------

def extract_all_features(
    dataset: pd.DataFrame,
    sessions: Dict[str, List[int]],
    previews_dir: Path,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str], List[int]]:
    """
    Extrai features de cada foto e style fingerprint dos JPEGs de referência.

    Retorna:
        stat_all:    [N, stat_dim]
        deep_all:    [N, deep_dim]
        style_all:   [N, 128]
        params_all:  [N, num_params]
        param_cols:  List[str]  — nomes dos parâmetros
        valid_idx:   List[int]  — índices do dataset usados
    """
    logger.info("PARTE 3: Extração de features + style fingerprints")

    stat_extractor = ImageFeatureExtractor()
    deep_extractor = DeepFeatureExtractor()
    style_extractor = StyleFingerprintExtractor()

    # Identificar colunas de parâmetros Lightroom (excluir colunas de metadata)
    meta_cols = {'image_path', 'image_id', 'capture_date', 'captureTime', 'date_taken',
                 'date', 'preset_cluster', 'rating', 'session_id'}
    param_cols = [c for c in dataset.columns
                  if c not in meta_cols and not c.startswith('delta_')]

    if not param_cols:
        raise ValueError("Nenhuma coluna de parâmetros encontrada no dataset.")
    logger.info(f"  {len(param_cols)} parâmetros Lightroom detectados")

    stat_list, deep_list, style_list, params_list, valid_idx = [], [], [], [], []
    missing_previews = 0

    for session_id, indices in sessions.items():
        rows = dataset.loc[indices]

        for photo_idx in indices:
            row = dataset.loc[photo_idx]
            image_path = str(row.get('image_path', ''))
            if not image_path or not Path(image_path).exists():
                continue

            # Features da foto
            try:
                stat_feat = stat_extractor.extract_all_features(image_path)
                deep_feat = deep_extractor.extract_features(image_path)
            except Exception as e:
                logger.debug(f"Erro ao extrair features de {image_path}: {e}")
                continue

            # Para cada outra foto da sessão como referência
            for ref_idx in indices:
                if ref_idx == photo_idx:
                    continue

                ref_row = dataset.loc[ref_idx]
                # Tentar encontrar JPEG exportado da referência
                image_id = str(ref_row.get('image_id', ref_idx))
                preview_path = previews_dir / f"{image_id}.jpg"
                if not preview_path.exists():
                    # Fallback: tentar pelo nome do ficheiro
                    img_name = Path(str(ref_row.get('image_path', ''))).stem
                    preview_path = previews_dir / f"{img_name}.jpg"

                if not preview_path.exists():
                    missing_previews += 1
                    continue

                try:
                    style_fp = style_extractor.extract(preview_path)
                except Exception as e:
                    logger.debug(f"Erro ao extrair fingerprint de {preview_path}: {e}")
                    continue

                # Parâmetros absolutos da foto (não deltas)
                params = row[param_cols].values.astype(np.float32)

                stat_list.append(stat_feat)
                deep_list.append(deep_feat)
                style_list.append(style_fp)
                params_list.append(params)
                valid_idx.append(int(photo_idx))

    if missing_previews > 0:
        logger.warning(
            f"  {missing_previews} pares ignorados por falta de JPEG em {previews_dir}. "
            "Execute tools/extract_lightroom_previews.py primeiro."
        )

    if not stat_list:
        raise ValueError(
            "Nenhum par de treino construído. Verifique se os previews estão em data/previews/."
        )

    logger.info(f"  {len(stat_list)} pares de treino construídos")
    return (
        np.array(stat_list, dtype=np.float32),
        np.array(deep_list, dtype=np.float32),
        np.array(style_list, dtype=np.float32),
        np.array(params_list, dtype=np.float32),
        param_cols,
        valid_idx,
    )


# ---------------------------------------------------------------------------
# Passo 5 — Normalizar e dividir
# ---------------------------------------------------------------------------

def prepare_data(
    stat_all: np.ndarray,
    deep_all: np.ndarray,
    style_all: np.ndarray,
    params_all: np.ndarray,
) -> Tuple:
    """Split 70/15/15 + normalização. Guarda scalers em models/."""
    logger.info("PARTE 4: Normalização e split 70/15/15")

    # Primeiro split: separar test (15%)
    (stat_tv, stat_test, deep_tv, deep_test,
     style_tv, style_test, params_tv, params_test) = train_test_split(
        stat_all, deep_all, style_all, params_all,
        test_size=0.15, random_state=42
    )
    # Segundo split: separar val (15% do total ≈ 17.6% do restante)
    val_frac = 0.15 / 0.85
    (stat_train, stat_val, deep_train, deep_val,
     style_train, style_val, params_train, params_val) = train_test_split(
        stat_tv, deep_tv, style_tv, params_tv,
        test_size=val_frac, random_state=42
    )

    logger.info(f"  Split: {len(stat_train)} treino / {len(stat_val)} val / {len(stat_test)} test")

    # Normalização — fit apenas no treino
    sc_stat = StandardScaler().fit(stat_train)
    sc_deep = StandardScaler().fit(deep_train)
    sc_style = StandardScaler().fit(style_train)
    sc_params = StandardScaler().fit(params_train)

    joblib.dump(sc_stat,   MODELS_DIR / 'scaler_stat.pkl')       # partilhado com Style Learner
    joblib.dump(sc_deep,   MODELS_DIR / 'scaler_deep.pkl')       # partilhado com Style Learner
    joblib.dump(sc_style,  MODELS_DIR / 'scaler_style.pkl')      # novo
    joblib.dump(sc_params, MODELS_DIR / 'scaler_params_ref.pkl') # novo
    logger.info("  Scalers guardados em models/")

    def _t(sc, x):
        return sc.transform(x)

    return (
        _t(sc_stat, stat_train), _t(sc_stat, stat_val), _t(sc_stat, stat_test),
        _t(sc_deep, deep_train), _t(sc_deep, deep_val), _t(sc_deep, deep_test),
        _t(sc_style, style_train), _t(sc_style, style_val), _t(sc_style, style_test),
        _t(sc_params, params_train), _t(sc_params, params_val), _t(sc_params, params_test),
        sc_stat, sc_deep, sc_style, sc_params,
    )


# ---------------------------------------------------------------------------
# Passo 6 — Treinar
# ---------------------------------------------------------------------------

def train_reference_regressor(
    stat_train, stat_val,
    deep_train, deep_val,
    style_train, style_val,
    params_train, params_val,
    param_cols: List[str],
    sc_params: StandardScaler,
) -> ReferenceRegressor:
    logger.info("PARTE 5: Treino do ReferenceRegressor")

    device = ('mps' if torch.backends.mps.is_available()
              else 'cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"  Dispositivo: {device}")

    stat_dim = stat_train.shape[1]
    deep_dim = deep_train.shape[1]
    num_params = params_train.shape[1]

    model = ReferenceRegressor(
        stat_features_dim=stat_dim,
        deep_features_dim=deep_dim,
        style_fingerprint_dim=STYLE_DIM,
        num_params=num_params,
    )
    logger.info(f"  ReferenceRegressor: {sum(p.numel() for p in model.parameters()):,} parâmetros")

    weights = [PARAM_IMPORTANCE.get(col, 1.0) for col in param_cols]
    weights_tensor = torch.FloatTensor(weights).to(device)

    train_ds = ReferencePairDataset(stat_train, deep_train, style_train, params_train)
    val_ds = ReferencePairDataset(stat_val, deep_val, style_val, params_val)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    trainer = ReferenceMatchTrainer(
        model,
        param_weights=weights_tensor,
        device=device,
        use_mixed_precision=USE_MIXED_PRECISION,
        weight_decay=WEIGHT_DECAY,
    )

    ckpt_path = MODELS_DIR / 'reference_model.pth'
    trained = trainer.train(
        train_loader, val_loader,
        epochs=EPOCHS,
        patience=PATIENCE,
        param_columns=param_cols,
        scaler_params=sc_params,
        max_lr=MAX_LR,
        checkpoint_path=ckpt_path,
    )

    # Guardar histórico
    history = {
        'train_losses': trainer.train_losses,
        'val_losses': trainer.val_losses,
        'learning_rates': trainer.learning_rates,
    }
    with open(MODELS_DIR / 'reference_training_history.json', 'w') as f:
        json.dump(history, f, indent=2)

    return trained


# ---------------------------------------------------------------------------
# Passo 7 — Avaliação no test set
# ---------------------------------------------------------------------------

def evaluate_test(
    model: ReferenceRegressor,
    stat_test, deep_test, style_test, params_test,
    param_cols: List[str],
    sc_params: StandardScaler,
    device: str,
) -> None:
    logger.info("PARTE 6: Avaliação final no test set")

    test_ds = ReferencePairDataset(stat_test, deep_test, style_test, params_test)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)

    weights = [PARAM_IMPORTANCE.get(col, 1.0) for col in param_cols]
    weights_tensor = torch.FloatTensor(weights).to(device)

    trainer = ReferenceMatchTrainer(
        model,
        param_weights=weights_tensor,
        device=device,
        use_mixed_precision=False,
    )
    test_loss, mae_per_param, _, _ = trainer.validate(test_loader)
    avg_mae = float(np.mean(mae_per_param))

    logger.info(f"  Test Loss: {test_loss:.6f} | MAE médio: {avg_mae:.4f}")

    results = {
        'test_loss': float(test_loss),
        'mae_avg': avg_mae,
        'mae_per_param': {
            col: float(mae_per_param[i]) * sc_params.scale_[i]
            for i, col in enumerate(param_cols)
            if i < len(mae_per_param)
        },
    }
    out = MODELS_DIR / 'reference_test_evaluation.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"  Resultados guardados em {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=" * 70)
    logger.info("TREINO DO MODO REFERENCE MATCH — NSP Plugin v2.1")
    logger.info("=" * 70)

    dataset = load_catalog_data(CATALOG_PATH, MIN_RATING)
    sessions = group_by_session(dataset)

    (stat_all, deep_all, style_all, params_all,
     param_cols, _) = extract_all_features(dataset, sessions, PREVIEWS_DIR)

    # Guardar lista de parâmetros
    with open(MODELS_DIR / 'reference_param_columns.json', 'w') as f:
        json.dump(param_cols, f, indent=2)

    (stat_train, stat_val, stat_test,
     deep_train, deep_val, deep_test,
     style_train, style_val, style_test,
     params_train, params_val, params_test,
     sc_stat, sc_deep, sc_style, sc_params) = prepare_data(
        stat_all, deep_all, style_all, params_all
    )

    device = ('mps' if torch.backends.mps.is_available()
              else 'cuda' if torch.cuda.is_available() else 'cpu')

    model = train_reference_regressor(
        stat_train, stat_val, deep_train, deep_val,
        style_train, style_val, params_train, params_val,
        param_cols, sc_params,
    )

    evaluate_test(
        model,
        stat_test, deep_test, style_test, params_test,
        param_cols, sc_params, device,
    )

    logger.info("=" * 70)
    logger.info("TREINO DO MODO REFERENCE MATCH COMPLETO!")
    logger.info(f"  Modelos em: {MODELS_DIR}")
    logger.info(f"  reference_model.pth")
    logger.info(f"  scaler_style.pkl")
    logger.info(f"  scaler_params_ref.pkl")
    logger.info(f"  reference_test_evaluation.json")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
