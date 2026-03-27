"""
train/profiling/train_profiles.py

Treina clusters de estilo (Auto-Profiling) a partir das embeddings já
geradas e regista o resultado na base de dados.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

APP_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = APP_ROOT / "data"
MODELS_DIR = APP_ROOT / "models"
PROFILES_DIR = MODELS_DIR / "profiles"
DB_PATH = DATA_DIR / "nsp_plugin.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def load_embeddings() -> np.ndarray:
    embeddings_path = DATA_DIR / "embeddings.npy"
    if not embeddings_path.exists():
        raise FileNotFoundError(f"Embeddings não encontrados em {embeddings_path}.")
    logging.info("A carregar embeddings de %s", embeddings_path)
    return np.load(embeddings_path)


def fetch_record_ids(limit: int | None = None) -> list[int]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Base de dados não encontrada em {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        query = "SELECT id FROM records ORDER BY id ASC"
        if limit:
            query += " LIMIT ?"
            rows = cursor.execute(query, (limit,)).fetchall()
        else:
            rows = cursor.execute(query).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def persist_results(
    labels: np.ndarray,
    distances: np.ndarray,
    record_ids: list[int],
    model_path: Path,
    num_clusters: int,
) -> int:
    conn = sqlite3.connect(DB_PATH)
    run_id: int
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO profile_runs (label, algorithm, embedding_dim, num_clusters, artifacts_path, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"auto_{datetime.utcnow().strftime('%Y%m%d%H%M')}",
                "kmeans",
                len(record_ids),
                num_clusters,
                str(model_path.relative_to(APP_ROOT)),
                json.dumps({"description": "Auto profiling gerado via CLI"}),
            ),
        )
        run_id = cursor.lastrowid
        rows = [
            (
                run_id,
                record_id,
                f"profile_{label}",
                float(1.0 / (1.0 + dist)),
                None,
            )
            for record_id, label, dist in zip(record_ids, labels, distances, strict=False)
        ]
        cursor.executemany(
            """
            INSERT INTO profile_membership (profile_run_id, record_id, profile_label, confidence, extra_metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina clusters de estilo (Auto-Profiling).")
    parser.add_argument("--num-clusters", type=int, default=5, help="Número de clusters KMeans.")
    parser.add_argument("--limit", type=int, help="Limita o nº de embeddings (debug).")
    args = parser.parse_args()

    record_ids = fetch_record_ids(limit=args.limit)
    if not record_ids:
        raise RuntimeError("Não existem registos para gerar perfis.")

    embeddings = load_embeddings()
    limit = min(len(record_ids), embeddings.shape[0])
    if args.limit:
        limit = min(limit, args.limit)
    embeddings = embeddings[:limit]
    record_ids = record_ids[:limit]

    scaler = StandardScaler()
    X = scaler.fit_transform(embeddings)

    logging.info("A treinar KMeans com %d clusters em %d amostras.", args.num_clusters, len(X))
    kmeans = KMeans(n_clusters=args.num_clusters, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(X)
    distances = kmeans.transform(X)[np.arange(len(X)), labels]

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    artifact_path = PROFILES_DIR / f"profiles_{timestamp}.joblib"
    joblib.dump({"scaler": scaler, "model": kmeans, "record_ids": record_ids}, artifact_path)
    logging.info("Artefacto guardado em %s", artifact_path)

    run_id = persist_results(labels, distances, record_ids, artifact_path, args.num_clusters)
    logging.info("Perfil run #%s registado em profile_runs/profile_membership.", run_id)


if __name__ == "__main__":
    main()
