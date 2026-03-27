"""
debug_load.py

A simple script to isolate model loading issues outside of the FastAPI/Uvicorn server.
It loads all models one by one to identify the source of a potential crash.
"""
import os
import glob
import joblib
import lightgbm as lgb
import torch
import torchvision.models as models
import logging
from pathlib import Path

# --- Setup & Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent
MODELS_DIR = APP_ROOT / 'models'

def load_culling_model(device):
    """Loads the fine-tuned culling model."""
    model = models.resnet34(weights=None)
    model.fc = torch.nn.Sequential(
        torch.nn.Linear(model.fc.in_features, 256),
        torch.nn.ReLU(),
        torch.nn.Dropout(0.4),
        torch.nn.Linear(256, 3)
    )
    model_path = MODELS_DIR / 'culling_model.pth'
    if model_path.exists():
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.to(device)
        model.eval()
        logging.info("Culling model loaded successfully.")
        return model
    else:
        logging.warning("Culling model not found.")
        return None

def main():
    device = 'cpu'
    logging.info(f"Using device: {device}")

    try:
        logging.info("--- Loading ResNet50 (for embedder) ---")
        embedder_model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT).to(device)
        embedder_model.fc = torch.nn.Identity()
        embedder_model.eval()
        logging.info("ResNet50 loaded successfully.")

        logging.info("--- Loading Culling Model (ResNet34) ---")
        culling_model = load_culling_model(device)

        logging.info("--- Loading PCA model ---")
        pca_model = joblib.load(MODELS_DIR / 'pca_model.pkl')
        logging.info("PCA model loaded successfully.")

        logging.info("--- Loading EXIF scaler ---")
        exif_scaler = joblib.load(MODELS_DIR / 'exif_scaler.pkl')
        logging.info("EXIF scaler loaded successfully.")

        logging.info("--- Loading Slider Models (LightGBM) ---")
        slider_files = glob.glob(str(MODELS_DIR / 'slider_*.txt'))
        for f in slider_files:
            slider_name = os.path.basename(f).replace('slider_', '').replace('.txt', '')
            lgb.Booster(model_file=f)
            logging.info(f"Slider model '{slider_name}' loaded successfully.")
        
        logging.info("\n*** ALL MODELS LOADED SUCCESSFULLY ***")

    except Exception as e:
        logging.error(f"An error occurred during model loading: {e}", exc_info=True)

if __name__ == '__main__':
    main()
