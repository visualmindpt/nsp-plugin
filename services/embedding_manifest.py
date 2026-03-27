"""
Utilitários para lidar com o manifesto de embeddings gerado em tools/generate_real_embeddings.py.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = APP_ROOT / "data" / "embeddings_manifest.json"


def load_manifest(path: Optional[Path] = None) -> Optional[Dict[str, Sequence]]:
    manifest_path = path or DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        logging.warning("Manifesto de embeddings não encontrado em %s.", manifest_path)
        return None
    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        logging.error("Não foi possível ler o manifesto de embeddings (%s): %s", manifest_path, exc)
        return None
    if "record_ids" not in data or not isinstance(data["record_ids"], list):
        logging.error("Manifesto inválido em %s: falta o campo 'record_ids'.", manifest_path)
        return None
    return data


def record_id_to_index(manifest: Dict[str, Sequence]) -> Dict[int, int]:
    return {int(record_id): idx for idx, record_id in enumerate(manifest.get("record_ids", []))}


def resolve_manifest_ids(manifest: Optional[Dict[str, Sequence]], embeddings_len: int) -> List[int]:
    """
    Retorna a lista de record_ids alinhada com o array de embeddings.
    Se o manifesto estiver ausente ou desalinhado, gera um fallback sequencial
    e emite avisos no log para facilitar a depuração.
    """
    if not manifest or "record_ids" not in manifest:
        logging.warning("Manifesto ausente; a assumir mapeamento sequencial 0..n-1.")
        return list(range(embeddings_len))

    raw_ids = []
    for raw in manifest.get("record_ids", []):
        try:
            raw_ids.append(int(raw))
        except (TypeError, ValueError):
            logging.warning("ID inválido no manifesto (%s); ignorado.", raw)

    if not raw_ids:
        logging.warning("Manifesto não contém IDs válidos; a assumir mapeamento sequencial.")
        return list(range(embeddings_len))

    if len(raw_ids) < embeddings_len:
        logging.warning(
            "Manifesto contém %d IDs mas existem %d embeddings. Apenas os primeiros %d serão utilizados.",
            len(raw_ids),
            embeddings_len,
            len(raw_ids),
        )
    elif len(raw_ids) > embeddings_len:
        logging.warning(
            "Manifesto contém mais IDs (%d) do que embeddings (%d). Os IDs extra serão ignorados.",
            len(raw_ids),
            embeddings_len,
        )
        raw_ids = raw_ids[:embeddings_len]

    seen = set()
    deduped: List[int] = []
    for rid in raw_ids:
        if rid in seen:
            logging.warning("ID duplicado no manifesto (%s); mantendo apenas a primeira ocorrência.", rid)
            continue
        seen.add(rid)
        deduped.append(rid)

    if len(deduped) != len(raw_ids):
        logging.warning("Foram removidos IDs duplicados do manifesto (total único: %d).", len(deduped))

    return deduped
