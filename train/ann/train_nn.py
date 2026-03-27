
import argparse
import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Tuple
import sys

import joblib
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset

APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))

from services.embedding_manifest import load_manifest, resolve_manifest_ids
from tools.data_validation import validate_records
from tools.model_manifest import regenerate_default_manifest
from slider_config import ALL_SLIDERS as ALL_SLIDER_CONFIGS # Import ALL_SLIDERS from slider_config

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = APP_ROOT / 'data'
MODELS_DIR = APP_ROOT / 'models'
DB_PATH = DATA_DIR / 'nsp_plugin.db'
EMBEDDINGS_PATH = DATA_DIR / 'embeddings.npy'
NN_MODEL_DIR = MODELS_DIR / 'ann'
DEFAULT_CONFIG_PATH = NN_MODEL_DIR / 'nn_config.json'

ALL_SLIDER_NAMES = [s["python_name"] for s in ALL_SLIDER_CONFIGS] # Extract names


def load_config(config_path: Optional[Path]) -> dict:
    """Load optional configuration for slider weights and split ratios."""
    config = {
        "slider_weights": {},
        "train_ratio": 0.8,
        "val_ratio": 0.1,
        "test_ratio": 0.1,
        "early_stopping_patience": 10,
        "min_lr": 1e-6,
    }
    path: Optional[Path] = config_path or (DEFAULT_CONFIG_PATH if DEFAULT_CONFIG_PATH.exists() else None)
    if path and path.exists():
        with path.open() as handle:
            user_cfg = json.load(handle)
        config.update(user_cfg or {})
        logging.info("Loaded NN config from %s", path)
    else:
        logging.info("Using default NN configuration.")
    # Normalise ratios
    total = config["train_ratio"] + config["val_ratio"] + config["test_ratio"]
    if not np.isclose(total, 1.0):
        config["train_ratio"] = config["train_ratio"] / total
        config["val_ratio"] = config["val_ratio"] / total
        config["test_ratio"] = config["test_ratio"] / total
    return config


def load_and_prepare_data_for_torch(skip_validation: bool, iqr_multiplier: float):
    """Loads and prepares data, returning arrays for splitting and stats."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, exif, develop_vector FROM records").fetchall()
    conn.close()
    records = [(row["id"], row["exif"], row["develop_vector"]) for row in rows]

    if not skip_validation:
        records, report = validate_records(
            records,
            ALL_SLIDER_NAMES,
            iqr_multiplier=iqr_multiplier,
        )
        logging.info("Validação NN: %s", report.describe())
        if not records:
            logging.warning("Sem registos válidos após a validação.")
            return (
                np.empty((0,)),
                np.empty((0,)),
                None,
                np.array([]),
                np.array([]),
            )
    else:
        logging.info("Validação de dados ignorada por opção do utilizador.")

    all_embeddings = np.load(EMBEDDINGS_PATH)
    pca_model = joblib.load(MODELS_DIR / 'pca_model.pkl')
    exif_scaler = joblib.load(MODELS_DIR / 'exif_scaler.pkl')
    EXIF_KEYS = ['iso', 'width', 'height']
    manifest = load_manifest()
    manifest_ids = resolve_manifest_ids(manifest, len(all_embeddings))
    id_lookup = {int(rid): idx for idx, rid in enumerate(manifest_ids)}

    X, y = [], []
    feature_dim = None

    for rec_id, exif_json, develop_json in records:
        develop_vector = json.loads(develop_json)
        if not develop_vector or len(develop_vector) != len(ALL_SLIDER_NAMES):
            continue

        record_idx = id_lookup.get(rec_id, rec_id if not id_lookup else None)
        if record_idx is None:
            continue
        if record_idx >= len(all_embeddings):
            continue

        embedding = all_embeddings[record_idx]
        embedding_pca = pca_model.transform(embedding.reshape(1, -1))
        
        orig_exif = json.loads(exif_json)
        exif_values = [orig_exif.get(k, 0) for k in EXIF_KEYS]
        exif_scaled = exif_scaler.transform(np.array(exif_values).reshape(1, -1))
        
        final_feature_vector = np.concatenate([embedding_pca, exif_scaled], axis=1)
        if feature_dim is None:
            feature_dim = final_feature_vector.shape[1]
        
        X.append(final_feature_vector.flatten())
        y.append(develop_vector)

    X_array = np.array(X, dtype=np.float32)
    y_array = np.array(y, dtype=np.float32)

    if X_array.size == 0 or y_array.size == 0:
        logging.warning("No samples were prepared for training.")
        return (
            np.empty((0,)),
            np.empty((0,)),
            feature_dim,
            np.array([]),
            np.array([]),
        )

    target_mean = y_array.mean(axis=0)
    target_std = y_array.std(axis=0)
    target_std = np.where(target_std < 1e-6, 1.0, target_std)

    logging.info(f"Loaded and prepared {len(X_array)} samples for PyTorch.")
    return X_array, y_array, feature_dim, target_mean, target_std

# --- Neural Network Definition ---
class MultiOutputNN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(MultiOutputNN, self).__init__()
        self.layer_1 = nn.Linear(input_dim, 256)
        self.bn1 = nn.BatchNorm1d(256)
        self.layer_2 = nn.Linear(256, 128)
        self.bn2 = nn.BatchNorm1d(128)
        self.layer_3 = nn.Linear(128, output_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=0.2)

    def forward(self, x):
        x = self.layer_1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.layer_2(x)
        x = self.bn2(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.layer_3(x) # No activation on the output layer for regression
        return x

# --- Training Utilities ---
class EarlyStopper:
    def __init__(self, patience: int, min_delta: float = 0.0):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float("inf")
        self.counter = 0

    def should_stop(self, loss: float) -> bool:
        if loss + self.min_delta < self.best_loss:
            self.best_loss = loss
            self.counter = 0
            return False
        self.counter += 1
        return self.counter >= self.patience


def build_data_loaders(
    X: np.ndarray,
    y: np.ndarray,
    train_ratio: float,
    val_ratio: float,
    batch_size: int,
    target_mean: np.ndarray,
    target_std: np.ndarray,
    seed: int = 42,
) -> Tuple[DataLoader, Optional[DataLoader], Optional[DataLoader], torch.Tensor, torch.Tensor]:
    mean_tensor = torch.tensor(target_mean, dtype=torch.float32)
    std_tensor = torch.tensor(target_std, dtype=torch.float32)
    y_norm = (y - target_mean) / target_std

    X_train, X_tmp, y_train, y_tmp = train_test_split(
        X, y_norm, test_size=(1 - train_ratio), random_state=seed
    )
    val_size = val_ratio / (1 - train_ratio) if val_ratio > 0 else 0
    if val_size > 0:
        X_val, X_test, y_val, y_test = train_test_split(
            X_tmp, y_tmp, test_size=(1 - val_size), random_state=seed
        )
    else:
        X_val, y_val, X_test, y_test = np.empty((0,)), np.empty((0,)), X_tmp, y_tmp

    def to_loader(features, labels, shuffle: bool):
        if features.size == 0:
            return None
        tensor_x = torch.tensor(features, dtype=torch.float32)
        tensor_y = torch.tensor(labels, dtype=torch.float32)
        dataset = TensorDataset(tensor_x, tensor_y)
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

    train_loader = to_loader(X_train, y_train, True)
    val_loader = to_loader(X_val, y_val, False) if X_val.size else None
    test_loader = to_loader(X_test, y_test, False) if X_test.size else None

    return train_loader, val_loader, test_loader, mean_tensor, std_tensor


# --- Main Training Loop ---
def main():
    """Main function to train the neural network."""
    parser = argparse.ArgumentParser(description="Train Neural Network on real data.")
    parser.add_argument("--config", type=Path, help="Optional path to NN config JSON.")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-validation", action="store_true", help="Ignora sanidade dos dados (não recomendado).")
    parser.add_argument("--iqr-multiplier", type=float, default=3.5, help="Multiplicador de IQR para deteção de outliers.")
    parser.add_argument("--load-pretrained", action="store_true", help="Carrega um modelo pré-treinado para continuar o treino.")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    # --- Device Selection ---
    device = torch.device('mps' if torch.backends.mps.is_available() and torch.backends.mps.is_built() else 'cpu')
    logging.info(f"Using device: {device}")

    config = load_config(args.config)

    # --- 1. Load Data ---
    X_array, y_array, input_dim, target_mean, target_std = load_and_prepare_data_for_torch(
        skip_validation=args.skip_validation,
        iqr_multiplier=args.iqr_multiplier,
    )
    if input_dim is None or X_array.size == 0:
        logging.error("Could not determine feature dimension. Aborting.")
        return

    NN_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    np.save(NN_MODEL_DIR / 'targets_mean.npy', target_mean.astype(np.float32))
    np.save(NN_MODEL_DIR / 'targets_std.npy', target_std.astype(np.float32))

    train_loader, val_loader, test_loader, mean_tensor, std_tensor = build_data_loaders(
        X_array,
        y_array,
        config["train_ratio"],
        config["val_ratio"],
        args.batch_size,
        target_mean,
        target_std,
        seed=args.seed,
    )
    if train_loader is None:
        logging.error("Training loader is empty. Aborting.")
        return

    # --- 2. Initialize Model, Loss, and Optimizer ---
    model = MultiOutputNN(input_dim=input_dim, output_dim=len(ALL_SLIDER_NAMES)).to(device)
    
    # Load pre-trained model if specified and available
    pretrained_path = NN_MODEL_DIR / 'multi_output_nn.pth'
    if args.load_pretrained and pretrained_path.exists():
        logging.info(f"Loading pre-trained model from {pretrained_path}")
        model.load_state_dict(torch.load(pretrained_path, map_location=device))
    elif args.load_pretrained and not pretrained_path.exists():
        logging.warning(f"Pre-trained model not found at {pretrained_path}. Starting training from scratch.")

    criterion = nn.MSELoss(reduction='none') # Mean Squared Error per-output
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, min_lr=config["min_lr"], verbose=True
    )

    slider_weights = torch.ones(len(ALL_SLIDER_NAMES), dtype=torch.float32)
    for idx, name in enumerate(ALL_SLIDER_NAMES):
        if name in config["slider_weights"]:
            slider_weights[idx] = config["slider_weights"][name]
        else:
            # Normalize by inverse std dev, but handle zero std dev
            if std_tensor[idx] > 1e-6:
                slider_weights[idx] = 1.0 / std_tensor[idx]
            else:
                slider_weights[idx] = 1.0

    slider_weights = slider_weights.unsqueeze(0).to(device)

    logging.info("Starting training of the Multi-Output Neural Network...")

    # --- 3. Training Loop ---
    stopper = EarlyStopper(patience=config["early_stopping_patience"])
    best_val_loss = None
    history = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            # Forward pass
            outputs = model(inputs)
            mse = criterion(outputs, targets)
            loss = (mse * slider_weights).mean()

            # Backward pass and optimization
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        train_loss /= max(len(train_loader), 1)

        model.eval()
        val_loss = None
        if val_loader is not None:
            with torch.no_grad():
                total = 0.0
                for inputs, targets in val_loader:
                    inputs, targets = inputs.to(device), targets.to(device)
                    outputs = model(inputs)
                    mse = criterion(outputs, targets)
                    total += (mse * slider_weights).mean().item()
                val_loss = total / max(len(val_loader), 1)
                scheduler.step(val_loss)
                if best_val_loss is None or val_loss < best_val_loss:
                    best_val_loss = val_loss
                    torch.save(model.state_dict(), NN_MODEL_DIR / 'multi_output_nn_best.pth')
                    stopper.counter = 0
                elif stopper.should_stop(val_loss):
                    logging.info("Early stopping triggered at epoch %d", epoch)
                    break
        else:
            scheduler.step(train_loss)

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "lr": optimizer.param_groups[0]["lr"],
            }
        )
        if epoch % 10 == 0 or epoch == 1:
            logging.info(
                "Epoch %d/%d - train_loss: %.4f%s",
                epoch,
                args.epochs,
                train_loss,
                f", val_loss: {val_loss:.4f}" if val_loss is not None else "",
            )

    logging.info("Training complete.")

    # --- 4. Save the Model ---
    final_path = NN_MODEL_DIR / 'multi_output_nn.pth'
    torch.save(model.state_dict(), final_path)
    logging.info("Model saved to %s", final_path)

    summary = {"history": history, "best_val_loss": best_val_loss}

    # Evaluate on hold-out test set if available
    if test_loader is not None:
        model.eval()
        with torch.no_grad():
            total = 0.0
            for inputs, targets in test_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                mse = criterion(outputs, targets)
                total += (mse * slider_weights).mean().item()
            test_loss = total / max(len(test_loader), 1)
            logging.info("Hold-out test loss (normalized space): %.4f", test_loss)
            summary["test_loss"] = test_loss

    history_path = NN_MODEL_DIR / 'training_history.json'
    history_path.write_text(json.dumps(summary, indent=2))
    logging.info("Saved training history to %s", history_path)

    if (NN_MODEL_DIR / 'multi_output_nn_best.pth').exists():
        logging.info("Best validation checkpoint stored at multi_output_nn_best.pth.")
    
    # --- ONNX Export ---
    onnx_path = NN_MODEL_DIR / 'multi_output_nn.onnx'
    try:
        # Create a dummy input for ONNX export
        dummy_input = torch.randn(1, input_dim, device=device)
        torch.onnx.export(
            model,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=11, # Common opset version
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        logging.info("Model exported to ONNX format at %s", onnx_path)
    except Exception as exc:
        logging.warning("Failed to export model to ONNX: %s", exc)

    try:
        manifest_path = regenerate_default_manifest()
        logging.info("Manifesto de modelos atualizado automaticamente em %s", manifest_path)
    except Exception as exc:
        logging.warning("Falhou atualização automática do manifesto: %s", exc)

if __name__ == "__main__":
    main()
