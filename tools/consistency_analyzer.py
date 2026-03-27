"""
tools/consistency_analyzer.py

CLI para gerar relatórios de consistência reutilizando a mesma lógica do
servidor FastAPI.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from services.consistency import ConsistencyAnalyzer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera relatório de consistência para um lote de imagens.")
    parser.add_argument("--collection", default="ad-hoc", help="Nome da coleção/lote analisado.")
    parser.add_argument(
        "--record-ids",
        nargs="*",
        type=int,
        help="IDs específicos de records. Se omitido, usa todas as imagens do DB.",
    )
    parser.add_argument("--out", type=Path, help="Guarda o JSON resultante no caminho indicado.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyzer = ConsistencyAnalyzer(collection=args.collection)
    report = analyzer.analyze_and_persist(args.record_ids, generated_by="cli")
    summary = report.summary
    logging.info(
        "Relatório #%s registado em consistency_reports (score=%.3f).",
        report.report_id,
        summary["score"],
    )
    if args.out:
        args.out.write_text(json.dumps(summary, indent=2))
        logging.info("Resumo gravado em %s", args.out)


if __name__ == "__main__":
    main()
