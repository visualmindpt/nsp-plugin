"""
tools/run_culling.py

Avalia automaticamente cada foto extraída do catálogo e decide se deve ser mantida
para treino com base em métricas simples de nitidez, contraste e exposição.
Os resultados são gravados na tabela `culling_results`, permitindo que o restante
do pipeline use apenas as imagens aprovadas.
"""
import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
from PIL import Image, UnidentifiedImageError

try:
    import rawpy
except ImportError:  # pragma: no cover
    rawpy = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / "data" / "nsp_plugin.db"


def ensure_table(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS culling_results (
            record_id INTEGER PRIMARY KEY,
            score REAL NOT NULL,
            sharpness REAL,
            exposure REAL,
            contrast REAL,
            keep_flag INTEGER NOT NULL,
            evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            FOREIGN KEY (record_id) REFERENCES records (id)
        )
        """
    )
    conn.commit()


def fetch_records(conn: sqlite3.Connection, limit: Optional[int]) -> Iterable[Tuple[int, str]]:
    cur = conn.cursor()
    query = "SELECT id, image_path FROM records ORDER BY id ASC"
    if limit:
        query += " LIMIT ?"
        yield from cur.execute(query, (limit,))
    else:
        yield from cur.execute(query)


def _prepare_image(path: str, max_side: int) -> np.ndarray:
    try:
        img = Image.open(path)
    except FileNotFoundError:
        raise
    except (UnidentifiedImageError, OSError) as pil_error:
        if rawpy is None:
            raise pil_error
        try:
            with rawpy.imread(path) as raw:
                rgb = raw.postprocess()
        except rawpy.LibRawError as raw_error:
            raise RuntimeError(f"Imagem inválida ({raw_error})")
        img = Image.fromarray(rgb)

    img = img.convert("L")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def _variance_of_laplacian(gray: np.ndarray) -> float:
    lap = (
        -4 * gray
        + np.roll(gray, 1, axis=0)
        + np.roll(gray, -1, axis=0)
        + np.roll(gray, 1, axis=1)
        + np.roll(gray, -1, axis=1)
    )
    return float(np.mean(lap ** 2))


def _normalize(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.0
    return float(np.clip((value - min_value) / (max_value - min_value), 0.0, 1.0))


def score_image(
    image_path: str,
    max_side: int,
) -> Tuple[float, Dict[str, float]]:
    try:
        gray = _prepare_image(image_path, max_side=max_side)
    except FileNotFoundError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise RuntimeError(f"Imagem inválida ({exc})")

    brightness = float(gray.mean())
    contrast = float(gray.std())
    sharpness = _variance_of_laplacian(gray)

    exposure_score = max(0.0, 1.0 - abs(brightness - 0.5) / 0.5)
    contrast_score = _normalize(contrast, 0.05, 0.25)
    sharpness_score = _normalize(sharpness, 5e-5, 5e-3)

    final_score = 0.5 * sharpness_score + 0.3 * contrast_score + 0.2 * exposure_score
    metrics = {
        "brightness": brightness,
        "contrast": contrast,
        "sharpness": sharpness,
        "exposure_score": exposure_score,
        "contrast_score": contrast_score,
        "sharpness_score": sharpness_score,
    }
    return final_score, metrics


def run_culling(
    db_path: Path,
    threshold: float,
    overwrite: bool,
    limit: Optional[int],
    max_side: int,
) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Base de dados não encontrada em {db_path}")

    conn = sqlite3.connect(db_path)
    ensure_table(conn)
    cur = conn.cursor()

    if overwrite:
        cur.execute("DELETE FROM culling_results")
        conn.commit()
        logging.info("Resultados anteriores de culling removidos (overwrite).")

    kept = 0
    rejected = 0
    failed = 0

    for record_id, image_path in fetch_records(conn, limit):
        if not image_path:
            rejected += 1
            cur.execute(
                """
                INSERT INTO culling_results (record_id, score, sharpness, exposure, contrast, keep_flag, reason, evaluated_at)
                VALUES (?, ?, NULL, NULL, NULL, 0, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_id) DO UPDATE SET
                    score=excluded.score,
                    sharpness=excluded.sharpness,
                    exposure=excluded.exposure,
                    contrast=excluded.contrast,
                    keep_flag=excluded.keep_flag,
                    reason=excluded.reason,
                    evaluated_at=excluded.evaluated_at
                """,
                (record_id, 0.0, "sem caminho de imagem"),
            )
            continue

        try:
            score, metrics = score_image(image_path, max_side=max_side)
            keep_flag = int(score >= threshold)
            reason = "score>=threshold" if keep_flag else "score<threshold"
            cur.execute(
                """
                INSERT INTO culling_results (record_id, score, sharpness, exposure, contrast, keep_flag, reason, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_id) DO UPDATE SET
                    score=excluded.score,
                    sharpness=excluded.sharpness,
                    exposure=excluded.exposure,
                    contrast=excluded.contrast,
                    keep_flag=excluded.keep_flag,
                    reason=excluded.reason,
                    evaluated_at=excluded.evaluated_at
                """,
                (
                    record_id,
                    score,
                    metrics["sharpness"],
                    metrics["brightness"],
                    metrics["contrast"],
                    keep_flag,
                    reason,
                ),
            )
            if keep_flag:
                kept += 1
            else:
                rejected += 1
        except FileNotFoundError:
            failed += 1
            cur.execute(
                """
                INSERT INTO culling_results (record_id, score, sharpness, exposure, contrast, keep_flag, reason, evaluated_at)
                VALUES (?, 0.0, NULL, NULL, NULL, 0, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_id) DO UPDATE SET
                    score=excluded.score,
                    sharpness=excluded.sharpness,
                    exposure=excluded.exposure,
                    contrast=excluded.contrast,
                    keep_flag=excluded.keep_flag,
                    reason=excluded.reason,
                    evaluated_at=excluded.evaluated_at
                """,
                (record_id, "imagem não encontrada"),
            )
            logging.warning("Imagem não encontrada: %s", image_path)
        except RuntimeError as exc:
            failed += 1
            cur.execute(
                """
                INSERT INTO culling_results (record_id, score, sharpness, exposure, contrast, keep_flag, reason, evaluated_at)
                VALUES (?, 0.0, NULL, NULL, NULL, 0, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(record_id) DO UPDATE SET
                    score=excluded.score,
                    sharpness=excluded.sharpness,
                    exposure=excluded.exposure,
                    contrast=excluded.contrast,
                    keep_flag=excluded.keep_flag,
                    reason=excluded.reason,
                    evaluated_at=excluded.evaluated_at
                """,
                (record_id, str(exc)),
            )
            logging.warning("Falha ao analisar %s: %s", image_path, exc)

    conn.commit()
    conn.close()
    total = kept + rejected + failed
    logging.info("Culling concluído. Total: %d | Mantidas: %d | Rejeitadas: %d | Falhadas: %d", total, kept, rejected, failed)
    if kept == 0:
        logging.warning("Nenhuma imagem passou o culling. Ajusta o limiar ou revê os dados.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa culling automático sobre os registos extraídos.")
    parser.add_argument("--db-path", type=Path, default=DB_PATH, help="Caminho para a base de dados SQLite.")
    parser.add_argument("--threshold", type=float, default=0.4, help="Pontuação mínima para manter uma foto (0-1).")
    parser.add_argument("--limit", type=int, default=None, help="Analisa apenas N fotos (debug).")
    parser.add_argument("--overwrite", action="store_true", help="Apaga resultados anteriores de culling antes de correr.")
    parser.add_argument(
        "--max-side",
        type=int,
        default=768,
        help="Redimensiona a maior dimensão da imagem para este valor antes da análise.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    run_culling(
        db_path=cli_args.db_path,
        threshold=max(0.0, min(1.0, cli_args.threshold)),
        overwrite=cli_args.overwrite,
        limit=cli_args.limit,
        max_side=max(64, cli_args.max_side),
    )
