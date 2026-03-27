"""
tools/db_migrations.py

Applies SQLite schema migrations required pelos módulos avançados
(profiling automático e relatórios de consistência). O script é idempotente
e pode ser executado sempre que o schema necessitar de atualização.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Iterable

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SCHEMA_STATEMENTS: Iterable[str] = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profile_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        algorithm TEXT NOT NULL,
        embedding_dim INTEGER,
        num_clusters INTEGER,
        notes TEXT,
        artifacts_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profile_membership (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_run_id INTEGER NOT NULL,
        record_id INTEGER NOT NULL,
        profile_label TEXT NOT NULL,
        confidence REAL,
        extra_metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_run_id) REFERENCES profile_runs(id),
        FOREIGN KEY (record_id) REFERENCES records(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_profile_membership_run ON profile_membership(profile_run_id)",
    "CREATE INDEX IF NOT EXISTS idx_profile_membership_record ON profile_membership(record_id)",
    """
    CREATE TABLE IF NOT EXISTS consistency_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection_name TEXT,
        description TEXT,
        summary_json TEXT NOT NULL,
        generated_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consistency_report_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        record_id INTEGER,
        metrics_json TEXT NOT NULL,
        FOREIGN KEY (report_id) REFERENCES consistency_reports(id),
        FOREIGN KEY (record_id) REFERENCES records(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_consistency_items_report ON consistency_report_items(report_id)",
]


def migrate(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Base de dados não encontrada em {db_path}")

    logging.info("A aplicar migrations em %s", db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()
    logging.info("Migrations aplicadas com sucesso.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aplica migrations ao nsp_plugin.db.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/nsp_plugin.db"),
        help="Caminho para a base de dados SQLite.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrate(args.db_path.resolve())


if __name__ == "__main__":
    main()
