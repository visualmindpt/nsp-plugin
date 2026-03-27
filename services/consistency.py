"""
services/consistency.py

Utilitários para calcular relatórios de consistência reutilizáveis pela CLI
e pelo servidor FastAPI.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from .inference import ALL_SLIDER_NAMES

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"
DB_PATH = DATA_DIR / "nsp_plugin.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _open_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Base de dados não encontrada: {DB_PATH}")
    return sqlite3.connect(DB_PATH)


@dataclass
class ConsistencyReport:
    collection_name: str
    summary: dict
    report_id: int


class ConsistencyAnalyzer:
    def __init__(self, collection: str = "ad-hoc") -> None:
        self.collection = collection

    def _fetch_vectors(self, record_ids: Optional[List[int]]) -> List[List[float]]:
        conn = _open_db()
        try:
            cursor = conn.cursor()
            if record_ids:
                # SEGURANÇA: Validar explicitamente que todos os IDs são inteiros
                validated_ids = []
                for rid in record_ids:
                    try:
                        validated_ids.append(int(rid))
                    except (ValueError, TypeError):
                        logging.warning("ID de registo inválido ignorado: %s", rid)
                        continue

                if not validated_ids:
                    return []

                placeholders = ",".join("?" for _ in validated_ids)
                query = f"SELECT id, develop_vector FROM records WHERE id IN ({placeholders})"
                rows = cursor.execute(query, validated_ids).fetchall()
            else:
                rows = cursor.execute("SELECT id, develop_vector FROM records").fetchall()
        finally:
            conn.close()

        vectors: List[List[float]] = []
        for record_id, payload in rows:
            try:
                vector = json.loads(payload)
            except json.JSONDecodeError:
                logging.warning("Falha ao parsear develop_vector para record %d", record_id)
                continue

            if not isinstance(vector, list) or len(vector) < len(ALL_SLIDER_NAMES):
                logging.warning("develop_vector inválido para record %d", record_id)
                continue

            # SEGURANÇA: Verificar que todos os valores são finitos
            truncated = vector[: len(ALL_SLIDER_NAMES)]
            try:
                numeric_vector = [float(v) for v in truncated]
                if not all(np.isfinite(v) for v in numeric_vector):
                    logging.warning("develop_vector contém valores não-finitos para record %d", record_id)
                    continue
                vectors.append(numeric_vector)
            except (ValueError, TypeError) as exc:
                logging.warning("develop_vector contém valores não-numéricos para record %d: %s", record_id, exc)
                continue

        return vectors

    @staticmethod
    def _build_summary(vectors: List[List[float]]) -> dict:
        matrix = np.array(vectors, dtype=np.float32)
        means = np.mean(matrix, axis=0)
        stds = np.std(matrix, axis=0)
        normalized_std = np.clip(stds / 100.0, 0.0, 1.0)
        consistency_score = float(1.0 - np.mean(normalized_std))
        per_slider = {
            slider: {
                "mean": float(means[idx]),
                "std": float(stds[idx]),
                "normalized_std": float(normalized_std[idx]),
            }
            for idx, slider in enumerate(ALL_SLIDER_NAMES)
        }
        return {"score": consistency_score, "per_slider": per_slider, "samples": len(vectors)}

    def analyze(self, record_ids: Optional[List[int]] = None) -> dict:
        vectors = self._fetch_vectors(record_ids)
        if not vectors:
            raise RuntimeError("Sem dados suficientes para gerar o relatório de consistência.")
        return self._build_summary(vectors)

    def persist(self, summary: dict, generated_by: str = "api") -> int:
        conn = _open_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO consistency_reports (collection_name, description, summary_json, generated_by)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.collection,
                    f"Relatório gerado para {summary['samples']} imagens",
                    json.dumps(summary),
                    generated_by,
                ),
            )
            report_id = cursor.lastrowid
            conn.commit()
            return report_id
        finally:
            conn.close()

    def analyze_and_persist(self, record_ids: Optional[List[int]] = None, generated_by: str = "api") -> ConsistencyReport:
        summary = self.analyze(record_ids)
        report_id = self.persist(summary, generated_by)
        return ConsistencyReport(collection_name=self.collection, summary=summary, report_id=report_id)


__all__ = ["ConsistencyAnalyzer", "ConsistencyReport"]
