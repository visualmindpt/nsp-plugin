
import numpy as np
from pathlib import Path
import logging

# --- Setup & Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / 'data'
EMBEDDINGS_PATH = DATA_DIR / 'embeddings.npy'

NUM_RECORDS = 5000 # Must match the num_records in ingest_catalog.py
EMBEDDING_DIM = 1024 # Must match the input dimension expected by pca_model.pkl

def generate_mock_embeddings(num_records, embedding_dim):
    """Generates mock embeddings for the specified number of records."""
    logging.info(f"Generating {num_records} mock embeddings of dimension {embedding_dim}...")
    # Generate random embeddings. In a real scenario, these would come from an image embedder.
    mock_embeddings = np.random.rand(num_records, embedding_dim).astype(np.float32)
    np.save(EMBEDDINGS_PATH, mock_embeddings)
    logging.info(f"Mock embeddings saved to {EMBEDDINGS_PATH}.")

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generate_mock_embeddings(NUM_RECORDS, EMBEDDING_DIM)

if __name__ == '__main__':
    main()
