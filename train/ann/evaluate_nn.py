import argparse
import logging
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import mean_absolute_error

# Assuming train_nn.py is in the same directory and contains the NN definition and data loading
from train_nn import (
    ALL_SLIDER_NAMES,
    MultiOutputNN,
    build_data_loaders,
    load_and_prepare_data_for_torch,
    load_config,
)

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent.parent.parent
NN_MODEL_PATH = APP_ROOT / 'models' / 'ann' / 'multi_output_nn.pth'
TARGET_MEAN_PATH = NN_MODEL_PATH.parent / 'targets_mean.npy'
TARGET_STD_PATH = NN_MODEL_PATH.parent / 'targets_std.npy'

# --- Main Evaluation Loop ---
def main():
    """Main function to evaluate the trained neural network."""
    parser = argparse.ArgumentParser(description="Evaluate the multi-output neural network.")
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Ignora sanidade de dados (apenas para debugging).",
    )
    parser.add_argument(
        "--iqr-multiplier",
        type=float,
        default=3.5,
        help="Multiplicador de IQR para deteção de outliers antes da avaliação.",
    )
    args = parser.parse_args()

    logging.info("--- Starting Neural Network Model Evaluation ---")

    # --- 1. Load Data ---
    X_array, y_array, input_dim, target_mean, target_std = load_and_prepare_data_for_torch(
        skip_validation=args.skip_validation,
        iqr_multiplier=args.iqr_multiplier,
    )
    if input_dim is None or X_array.size == 0:
        logging.error("Could not determine feature dimension. Aborting evaluation.")
        return
    logging.info(f"Loaded {len(X_array)} samples for evaluation.")

    if not TARGET_MEAN_PATH.exists() or not TARGET_STD_PATH.exists():
        logging.error("Target normalization statistics not found. Please run train_nn.py first.")
        return

    target_mean = np.load(TARGET_MEAN_PATH)
    target_std = np.load(TARGET_STD_PATH)

    # --- 2. Load Model ---
    if not NN_MODEL_PATH.exists():
        logging.error(f"Model not found at {NN_MODEL_PATH}. Please run train_nn.py first.")
        return

    model = MultiOutputNN(input_dim=input_dim, output_dim=len(ALL_SLIDER_NAMES))
    model.load_state_dict(torch.load(NN_MODEL_PATH))
    model.eval() # Set the model to evaluation mode
    logging.info(f"Model loaded from {NN_MODEL_PATH}.")

    # --- 3. Make Predictions ---
    config = load_config(None)
    train_loader, val_loader, test_loader, _, _ = build_data_loaders(
        X_array,
        y_array,
        config["train_ratio"],
        config["val_ratio"],
        batch_size=1024,
        target_mean=target_mean,
        target_std=target_std,
        seed=42,
    )

    # Evaluate on training set for legacy comparison
    with torch.no_grad():
        preds = []
        targets = []
        for loader in filter(None, [train_loader, val_loader, test_loader]):
            for inputs, target in loader:
                pred = model(inputs)
                preds.append(pred)
                targets.append(target)

    predictions = torch.cat(preds, dim=0)
    targets_norm = torch.cat(targets, dim=0)

    # Convert tensors to numpy arrays for metric calculation
    predictions_np = predictions.numpy() * target_std + target_mean
    targets_np = targets_norm.numpy() * target_std + target_mean

    # --- 4. Calculate and Report MAE ---
    overall_mae = mean_absolute_error(targets_np, predictions_np)
    slider_maes = {}

    for i, slider_name in enumerate(ALL_SLIDER_NAMES):
        slider_mae = mean_absolute_error(targets_np[:, i], predictions_np[:, i])
        slider_maes[slider_name] = slider_mae
        logging.info(f"Slider '{slider_name}': MAE = {slider_mae:.4f}")

    logging.info("\n--- Overall Mean Absolute Error (MAE) for Neural Network: {:.4f} ---".format(overall_mae))
    logging.info("Model evaluation complete.")

if __name__ == "__main__":
    main()
