"""
Utilidades para validar registos do catálogo antes de alimentar os modelos.
Aplica verificações estruturais e deteta outliers suavizando o treino.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Iterable, List, Sequence, Tuple

import numpy as np

REQUIRED_EXIF_FIELDS = ("iso", "width", "height")


@dataclass
class ValidationReport:
    total_records: int
    kept_records: int
    dropped_missing_exif: int = 0
    dropped_short_vectors: int = 0
    dropped_outliers: int = 0
    dropped_parse_errors: int = 0

    def describe(self) -> str:
        return (
            f"{self.kept_records}/{self.total_records} registos válidos "
            f"(EXIF ausente: {self.dropped_missing_exif}, vetores incompletos: "
            f"{self.dropped_short_vectors}, outliers removidos: {self.dropped_outliers}, "
            f"erros de parsing: {self.dropped_parse_errors})"
        )

    def to_dict(self) -> dict:
        return asdict(self)


def _tukey_mask(column: np.ndarray, multiplier: float) -> np.ndarray:
    if column.size < 15:
        return np.zeros_like(column, dtype=bool)
    q1, q3 = np.percentile(column, [25, 75])
    iqr = q3 - q1
    if iqr < 1e-9:
        return np.zeros_like(column, dtype=bool)
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return (column < lower) | (column > upper)


def _coerce_float(value, default=None):
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(val):
        return default
    return val


def validate_records(
    records: Iterable[Sequence],
    slider_names: Sequence[str],
    iqr_multiplier: float = 3.5,
) -> Tuple[List[Tuple], ValidationReport]:
    """
    Filtra registos com EXIF inválido, develop_vector incompleto ou outliers extremos.
    Retorna a lista de registos válidos e um relatório agregado.
    """
    records_list = list(records)
    parsed_records = []
    dropped_missing_exif = 0
    dropped_short_vectors = 0
    dropped_outliers = 0
    dropped_parse_errors = 0

    for record in records_list:
        try:
            rec_id, exif_json, dv_json = record
        except ValueError:
            dropped_parse_errors += 1
            continue

        try:
            exif = json.loads(exif_json or "{}")
            develop_vector = json.loads(dv_json or "[]")
        except json.JSONDecodeError:
            dropped_parse_errors += 1
            continue

        if not isinstance(exif, dict):
            dropped_parse_errors += 1
            continue

        exif_vec: List[float] = []
        missing_field = False
        for field in REQUIRED_EXIF_FIELDS:
            value = _coerce_float(exif.get(field))
            if value is None or value <= 0:
                missing_field = True
                break
            exif_vec.append(value)
        if missing_field:
            dropped_missing_exif += 1
            continue

        if not isinstance(develop_vector, list) or len(develop_vector) < len(slider_names):
            dropped_short_vectors += 1
            continue

        try:
            slider_vec = [float(develop_vector[idx]) for idx in range(len(slider_names))]
        except (ValueError, TypeError):
            dropped_short_vectors += 1
            continue

        parsed_records.append((rec_id, exif_vec, slider_vec, tuple(record)))

    if not parsed_records:
        report = ValidationReport(
            total_records=len(records_list),
            kept_records=0,
            dropped_missing_exif=dropped_missing_exif,
            dropped_short_vectors=dropped_short_vectors,
            dropped_outliers=0,
            dropped_parse_errors=dropped_parse_errors,
        )
        return [], report

    exif_matrix = np.array([item[1] for item in parsed_records], dtype=np.float64)
    slider_matrix = np.array([item[2] for item in parsed_records], dtype=np.float64)

    outlier_mask = np.zeros(len(parsed_records), dtype=bool)
    for col_idx in range(exif_matrix.shape[1]):
        outlier_mask |= _tukey_mask(exif_matrix[:, col_idx], iqr_multiplier)
    for col_idx in range(slider_matrix.shape[1]):
        outlier_mask |= _tukey_mask(slider_matrix[:, col_idx], iqr_multiplier)

    filtered_records: List[Tuple] = []
    for idx, (_, _, _, original_record) in enumerate(parsed_records):
        if outlier_mask[idx]:
            dropped_outliers += 1
            continue
        filtered_records.append(original_record)

    report = ValidationReport(
        total_records=len(records_list),
        kept_records=len(filtered_records),
        dropped_missing_exif=dropped_missing_exif,
        dropped_short_vectors=dropped_short_vectors,
        dropped_outliers=dropped_outliers,
        dropped_parse_errors=dropped_parse_errors,
    )

    if report.kept_records == 0:
        logging.warning("Validação removeu todos os registos. Revê os dados de origem.")
    else:
        logging.info("Validação de dados: %s", report.describe())

    return filtered_records, report


__all__ = ["validate_records", "ValidationReport", "REQUIRED_EXIF_FIELDS"]
