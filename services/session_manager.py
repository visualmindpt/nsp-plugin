import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TrainingSession:
    """Representa uma sessão de treino (um catálogo processado)."""

    session_id: str
    catalog_path: str
    catalog_name: str
    session_dir: Path
    dataset_path: Path
    features_csv_path: Path
    features_npy_path: Path
    deep_features_path: Path
    metadata_path: Path


class TrainingSessionManager:
    """Gere sessões de treino persistidas com dataset + features."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Session Lifecycle
    # ------------------------------------------------------------------ #
    def start_session(self, catalog_path: Path) -> TrainingSession:
        """Cria diretório e metadata inicial para uma nova sessão."""
        catalog_path = Path(catalog_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._sanitize_name(catalog_path.stem or "catalog")
        session_id = f"{timestamp}_{safe_name}"
        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        session = TrainingSession(
            session_id=session_id,
            catalog_path=str(catalog_path),
            catalog_name=catalog_path.stem,
            session_dir=session_dir,
            dataset_path=session_dir / "dataset.csv",
            features_csv_path=session_dir / "features.csv",
            features_npy_path=session_dir / "features.npy",
            deep_features_path=session_dir / "deep_features.npy",
            metadata_path=session_dir / "session.json"
        )

        metadata = {
            "session_id": session_id,
            "catalog_path": str(catalog_path),
            "catalog_name": catalog_path.stem,
            "created_at": datetime.now().isoformat(),
            "status": "created",
            "num_images": 0,
            "notes": "",
        }
        self._write_metadata(session.metadata_path, metadata)
        return session

    def update_metadata(self, session: TrainingSession, **updates):
        """Atualiza metadata da sessão com campos arbitrários."""
        metadata = self._load_metadata(session.metadata_path)
        metadata.update(updates)
        metadata["updated_at"] = datetime.now().isoformat()
        self._write_metadata(session.metadata_path, metadata)

    def list_sessions(self) -> List[Dict]:
        """Lista metadata de todas as sessões existentes."""
        sessions = []
        for meta_file in sorted(self.base_dir.glob("*/session.json"), reverse=True):
            try:
                with open(meta_file, "r") as f:
                    data = json.load(f)
                    data["session_dir"] = str(meta_file.parent)
                    data["dataset_path"] = str(meta_file.parent / "dataset.csv")
                    data["features_csv_path"] = str(meta_file.parent / "features.csv")
                    data["features_npy_path"] = str(meta_file.parent / "features.npy")
                    data["deep_features_path"] = str(meta_file.parent / "deep_features.npy")
                    sessions.append(data)
            except Exception:
                continue
        return sessions

    def get_session(self, session_id: str) -> Optional[TrainingSession]:
        """Recupera objeto de sessão pelo ID, se existir."""
        session_dir = self.base_dir / session_id
        if not session_dir.exists():
            return None
        return TrainingSession(
            session_id=session_id,
            catalog_path="",
            catalog_name="",
            session_dir=session_dir,
            dataset_path=session_dir / "dataset.csv",
            features_csv_path=session_dir / "features.csv",
            features_npy_path=session_dir / "features.npy",
            deep_features_path=session_dir / "deep_features.npy",
            metadata_path=session_dir / "session.json"
        )

    def get_metadata(self, session: TrainingSession) -> Dict:
        """Retorna metadata completa da sessão."""
        data = self._load_metadata(session.metadata_path)
        data.setdefault("session_id", session.session_id)
        data["session_dir"] = str(session.session_dir)
        data.setdefault("dataset_path", str(session.dataset_path))
        data.setdefault("features_csv_path", str(session.features_csv_path))
        data.setdefault("features_npy_path", str(session.features_npy_path))
        data.setdefault("deep_features_path", str(session.deep_features_path))
        return data

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _sanitize_name(self, name: str) -> str:
        name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
        name = name.strip("_") or "catalog"
        return name[:50]

    def _write_metadata(self, path: Path, data: Dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_metadata(self, path: Path) -> Dict:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return {}

    def export_summary(self) -> Dict:
        """Retorna sumário útil para UI (contagem, últimas sessões, etc.)."""
        sessions = self.list_sessions()
        total_images = sum(s.get("num_images", 0) for s in sessions)
        ready_sessions = [s for s in sessions if s.get("status") == "trained"]
        return {
            "total_sessions": len(sessions),
            "total_images": total_images,
            "ready_sessions": len(ready_sessions),
            "latest_sessions": sessions[:5],
        }
