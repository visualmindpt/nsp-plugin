
import argparse
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image, UnidentifiedImageError
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import torch

try:
    import rawpy
except ImportError:  # pragma: no cover - optional dependency
    rawpy = None

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / 'data' / 'nsp_plugin.db'
EMBEDDINGS_PATH = APP_ROOT / 'data' / 'embeddings.npy'
MANIFEST_PATH = APP_ROOT / 'data' / 'embeddings_manifest.json'
MODEL_NAME = 'clip-ViT-B-32' # A standard, powerful CLIP model

# --- Main Embedding Generation Logic ---
def _table_exists(cur: sqlite3.Cursor, table_name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cur.fetchone() is not None


def get_image_records_from_db(use_culling: bool) -> List[Tuple[int, str]]:
    """Fetches record ids + paths, optionally filtrando pelos resultados de culling."""
    if not DB_PATH.exists():
        logging.error("Database not found at %s. Please run extract_from_lrcat.py first.", DB_PATH)
        return []

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    try:
        query: str
        params: Sequence[object] = ()
        culling_info = ""
        if use_culling and _table_exists(cur, "culling_results"):
            cur.execute("SELECT COUNT(*) FROM culling_results")
            total_culled = cur.fetchone()[0]
            if total_culled > 0:
                query = """
                    SELECT r.id, r.image_path
                    FROM records AS r
                    JOIN culling_results AS c ON c.record_id = r.id
                    WHERE c.keep_flag = 1
                    ORDER BY r.id ASC
                """
                cur.execute("SELECT COUNT(*) FROM culling_results WHERE keep_flag = 1")
                kept = cur.fetchone()[0]
                culling_info = f" (após culling: {kept} de {total_culled})"
            else:
                query = "SELECT id, image_path FROM records ORDER BY id ASC"
        else:
            query = "SELECT id, image_path FROM records ORDER BY id ASC"

        rows = cur.execute(query, params).fetchall()
        logging.info("Encontrados %d caminhos de imagem%s.", len(rows), culling_info)
        return rows
    finally:
        con.close()

def _load_image(path: str):
    """
    Load image and return a PIL.Image in RGB mode.
    Supports RAW formats (e.g., .ARW) when rawpy is available.
    """
    try:
        img = Image.open(path)
        return img.convert("RGB")
    except FileNotFoundError:
        raise
    except UnidentifiedImageError as pil_error:
        if rawpy is None:
            raise pil_error
        try:
            with rawpy.imread(path) as raw:
                rgb = raw.postprocess()
        except rawpy.LibRawError as raw_error:  # pragma: no cover - depends on specific raw file
            raise raw_error
        return Image.fromarray(rgb)
    except OSError as pil_error:
        if rawpy is None:
            raise pil_error
        try:
            with rawpy.imread(path) as raw:
                rgb = raw.postprocess()
        except rawpy.LibRawError as raw_error:  # pragma: no cover
            raise raw_error
        return Image.fromarray(rgb)

def main(use_culling: bool, batch_size: int):
    """Main function to generate and save real image embeddings."""
    logging.info("--- Starting Real Embedding Generation ---")

    # 1. Get image paths from the database
    image_records = get_image_records_from_db(use_culling=use_culling)
    if not image_records:
        logging.warning("No image paths found in the database. Aborting.")
        return

    # 2. Load the CLIP model
    logging.info(f"Loading sentence-transformer model: {MODEL_NAME}. This may take a moment...")
    
    # Detect and select MPS (GPU) device on Apple Silicon if available
    device = 'cpu'
    try:
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            device = 'mps'
            logging.info("MPS (GPU) backend disponível. A usar 'mps'.")
        else:
            logging.info("MPS (GPU) backend não disponível ou versão do PyTorch incompatível. A usar 'cpu'.")
    except AttributeError:
        # Older PyTorch versions might not have the 'backends' attribute.
        logging.info("Versão do PyTorch não suporta MPS. A usar 'cpu'.")

    # Define o diretório de modelos e garante que ele existe
    models_dir = APP_ROOT / 'models'
    models_dir.mkdir(exist_ok=True)

    model = SentenceTransformer(MODEL_NAME, device=device, cache_folder=str(models_dir))
    # Force model to MPS device if available, as the constructor might not be reliable in older versions
    if device == 'mps':
        model.to(torch.device('mps'))
    logging.info("Model loaded successfully on device: %s", model.device)

    # 3. Generate embeddings em batches para reduzir o consumo de memória
    logging.info("Generating embeddings for %d images...", len(image_records))

    batch_images: List[Image.Image] = []
    batch_ids: List[int] = []
    batch_paths: List[str] = []
    embeddings_chunks: List[np.ndarray] = []
    valid_record_ids: List[int] = []
    valid_paths: List[str] = []

    def flush_batch() -> None:
        if not batch_images:
            return
        logging.info("Encoding batch com %d imagens...", len(batch_images))
        encoded = model.encode(
            batch_images,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        embeddings_chunks.append(encoded)
        valid_record_ids.extend(batch_ids)
        valid_paths.extend(batch_paths)
        batch_images.clear()
        batch_ids.clear()
        batch_paths.clear()

    for record_id, path in tqdm(image_records, desc="Opening images"):
        try:
            image = _load_image(path)
        except FileNotFoundError:
            logging.warning("Image not found at: %s. Skipping.", path)
            continue
        except Exception as exc:
            logging.warning("Could not open image %s: %s. Skipping.", path, exc)
            continue

        batch_images.append(image)
        batch_ids.append(record_id)
        batch_paths.append(path)

        if len(batch_images) >= batch_size:
            flush_batch()

    # process remaining images
    flush_batch()

    if not embeddings_chunks:
        logging.error("No valid images could be opened. Aborting embedding generation.")
        return

    embeddings = np.vstack(embeddings_chunks)

    # 4. Save embeddings
    logging.info(f"Saving {len(embeddings)} embeddings to {EMBEDDINGS_PATH}")
    np.save(EMBEDDINGS_PATH, embeddings)
    manifest_payload = {
        "record_ids": valid_record_ids,
        "paths": valid_paths,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "use_culling": bool(use_culling),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest_payload, indent=2))
    logging.info("Embedding manifest gravado em %s", MANIFEST_PATH)

    logging.info("--- Real Embedding Generation Complete ---")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate CLIP embeddings for the extracted records.")
    parser.add_argument(
        "--use-culling",
        action="store_true",
        help="Se existir tabela de culling, usa apenas os registos assinalados como keep_flag=1.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Número de imagens a processar em cada lote na GPU."
    )
    return parser.parse_args()


if __name__ == "__main__":
    import multiprocessing as mp
    # For macOS and to prevent fork-related issues with torch/sentence-transformers
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass  # context has been already set

    cli_args = parse_args()
    main(use_culling=cli_args.use_culling, batch_size=cli_args.batch_size)
