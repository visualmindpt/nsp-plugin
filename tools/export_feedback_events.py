#!/usr/bin/env python3
"""
Exporta eventos de feedback (predictions + feedback_events) para Parquet,
pronto para pipelines de retreino/analytics.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

DEFAULT_DB = Path("data/feedback.db")
DEFAULT_OUTPUT = Path("data/feedback_export/feedback_events.parquet")


def _load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def export_feedback(db_path: Path, output_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Base de dados não encontrada: {db_path}")

    db_path = db_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        query = """
            SELECT
                fe.id AS event_id,
                fe.prediction_id,
                fe.event_type,
                fe.rating,
                fe.tags,
                fe.issues,
                fe.notes,
                fe.delta_payload,
                fe.context,
                fe.created_at,
                p.image_path,
                p.timestamp AS prediction_timestamp,
                p.predicted_preset,
                p.preset_confidence,
                p.predicted_params
            FROM feedback_events fe
            JOIN predictions p ON p.id = fe.prediction_id
            ORDER BY fe.created_at ASC
        """
        df = pd.read_sql_query(query, conn)

    if df.empty:
        print("⚠️  Nenhum feedback encontrado. Nada para exportar.")
        return

    df["tags"] = df["tags"].apply(lambda v: _load_json(v, []))
    df["issues"] = df["issues"].apply(lambda v: _load_json(v, []))
    df["context"] = df["context"].apply(lambda v: _load_json(v, {}))
    df["predicted_params"] = df["predicted_params"].apply(lambda v: _load_json(v, {}))
    df["delta_payload"] = df["delta_payload"].apply(lambda v: _load_json(v, {}))

    delta_df = pd.json_normalize(df["delta_payload"]).add_prefix("delta_")
    pred_df = pd.json_normalize(df["predicted_params"]).add_prefix("pred_")
    context_df = pd.json_normalize(df["context"]).add_prefix("context_")

    final_df = pd.concat(
        [
            df.drop(columns=["delta_payload", "predicted_params", "context"]),
            delta_df,
            pred_df,
            context_df,
        ],
        axis=1,
    )

    final_df.to_parquet(output_path, index=False)
    print(f"✅ Export concluído: {output_path} ({len(final_df)} linhas)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta feedback_events para Parquet.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Caminho para feedback.db")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destino do ficheiro Parquet",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    export_feedback(args.db, args.output)
