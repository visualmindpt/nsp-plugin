"""
tools/prepare_features.py

Performs feature engineering by applying PCA to the embeddings.

- Loads the raw embeddings from data/embeddings.npy.
- Fits a PCA model to reduce dimensionality.
- Saves the fitted PCA model to models/pca_model.pkl.
- Saves the transformed embeddings to data/embeddings_pca.npy.
"""
import argparse
import os
import numpy as np
from sklearn.decomposition import PCA
import joblib
import logging
from pathlib import Path

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(args):
    # Define paths
    embeddings_path = Path(args.input)
    pca_model_path = Path(args.out_model)
    transformed_embeddings_path = Path(args.out_data)

    # Create output directories if they don't exist
    pca_model_path.parent.mkdir(parents=True, exist_ok=True)
    transformed_embeddings_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Load embeddings
        logging.info(f"Loading embeddings from {embeddings_path}...")
        embeddings = np.load(embeddings_path)
        logging.info(f"Embeddings loaded successfully. Shape: {embeddings.shape}")

        # Determine valid number of components
        max_components = min(args.pca_components, embeddings.shape[0], embeddings.shape[1])
        if max_components < 1:
            logging.error("Not enough samples to fit PCA. Need at least 1 component.")
            return
        if max_components < args.pca_components:
            logging.warning(
                "Requested %d PCA components but dataset only supports %d. Adjusting automatically.",
                args.pca_components,
                max_components,
            )

        # Initialize and fit PCA
        logging.info(f"Fitting PCA with {max_components} components...")
        pca = PCA(n_components=max_components)
        transformed_embeddings = pca.fit_transform(embeddings)
        logging.info(f"PCA fitting complete. New shape: {transformed_embeddings.shape}")

        # Save the PCA model
        joblib.dump(pca, pca_model_path)
        logging.info(f"PCA model saved to {pca_model_path}")

        # Save the transformed embeddings
        np.save(transformed_embeddings_path, transformed_embeddings)
        logging.info(f"Transformed embeddings saved to {transformed_embeddings_path}")

    except FileNotFoundError:
        logging.error(f"Error: Input file not found at {embeddings_path}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Prepare features by applying PCA to embeddings.")
    parser.add_argument('--input', default='data/embeddings.npy', help="Input embeddings file path (.npy).")
    parser.add_argument('--out-model', default='models/pca_model.pkl', help="Output PCA model file path (.pkl).")
    parser.add_argument('--out-data', default='data/embeddings_pca.npy', help="Output transformed embeddings file path (.npy).")
    parser.add_argument('--pca-components', type=int, default=256, help="Number of PCA components to keep.")
    
    args = parser.parse_args()
    main(args)
