#!/usr/bin/env python3
"""
Gera e valida o manifesto de modelos consumido pelo Control Center e pelo packaging.
Pode ser usado via CLI ou importado pelos scripts de treino para atualizar o lockfile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

DEFAULT_MODELS_DIR = Path("models")
DEFAULT_OUTPUT = Path("models/model_bundle.lock.json")
DEFAULT_INCLUDE = ("requirements.txt", "requirements.fixed.txt")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_entries(files: Iterable[Path], project_root: Path) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for file_path in sorted(files):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(project_root)
        entries.append(
            {
                "path": rel_path.as_posix(),
                "size": file_path.stat().st_size,
                "sha256": sha256_file(file_path),
            }
        )
    return entries


def _resolve_paths(
    project_root: Path,
    models_dir: Path | None,
    include: Sequence[str | Path] | None,
    output: Path | None,
) -> tuple[Path, Path, List[Path], Path]:
    project_root = project_root.resolve()
    models_path = (project_root / (models_dir or DEFAULT_MODELS_DIR)).resolve()
    output_path = (project_root / (output or DEFAULT_OUTPUT)).resolve()
    include_files = [
        (project_root / Path(item)).resolve()
        for item in (include or DEFAULT_INCLUDE)
        if (project_root / Path(item)).exists()
    ]
    return project_root, models_path, include_files, output_path


def generate_manifest(
    project_root: Path,
    models_dir: Path | None = None,
    include: Sequence[str | Path] | None = None,
    output: Path | None = None,
    bundle_version: str | None = None,
) -> Path:
    project_root, models_path, include_files, output_path = _resolve_paths(
        project_root, models_dir, include, output
    )

    if not models_path.exists():
        raise FileNotFoundError(f"Diretório de modelos não encontrado: {models_path}")

    model_files = [p for p in models_path.rglob("*") if p.is_file()]

    manifest = {
        "schema_version": 1,
        "bundle_version": bundle_version
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models_root": models_path.relative_to(project_root).as_posix(),
        "files": build_entries(model_files, project_root),
        "lockfiles": build_entries(include_files, project_root),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2))
    return output_path


def verify_manifest(project_root: Path, manifest_path: Path | None = None) -> bool:
    project_root = project_root.resolve()
    manifest_path = (project_root / (manifest_path or DEFAULT_OUTPUT)).resolve()

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifesto não encontrado em {manifest_path}")
    manifest = json.loads(manifest_path.read_text())

    failures: List[str] = []
    for section in ("files", "lockfiles"):
        for entry in manifest.get(section, []):
            rel_path = Path(entry["path"])
            file_path = project_root / rel_path
            if not file_path.exists():
                failures.append(f"[missing] {rel_path}")
                continue
            current_hash = sha256_file(file_path)
            if current_hash != entry["sha256"]:
                failures.append(f"[hash mismatch] {rel_path}")

    if failures:
        print("Manifesto inválido:")
        for failure in failures:
            print(f" - {failure}")
        return False

    print("Manifesto verificado com sucesso.")
    return True


def regenerate_default_manifest(bundle_version: str | None = None) -> Path:
    """
    Helper a ser chamado pelos scripts de treino localizados na raiz do projeto.
    """
    project_root = Path(__file__).resolve().parent.parent
    return generate_manifest(project_root, bundle_version=bundle_version)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gerador/validador do manifesto de modelos NSP.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Raiz do projeto.")
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR, help="Diretório dos modelos.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Destino do manifesto.")
    parser.add_argument(
        "--include",
        nargs="*",
        default=list(DEFAULT_INCLUDE),
        help="Ficheiros adicionais para travar (ex.: requirements).",
    )
    parser.add_argument("--bundle-version", help="Etiqueta opcional para o bundle.")
    parser.add_argument("--verify", action="store_true", help="Apenas verifica o manifesto atual.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None):
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    include = [Path(item) for item in args.include]

    if args.verify:
        ok = verify_manifest(project_root, args.output)
        sys.exit(0 if ok else 1)
    else:
        manifest_path = generate_manifest(
            project_root,
            args.models_dir,
            include,
            args.output,
            args.bundle_version,
        )
        print(f"Manifesto gerado em {manifest_path}")


__all__ = [
    "generate_manifest",
    "verify_manifest",
    "regenerate_default_manifest",
    "DEFAULT_OUTPUT",
    "DEFAULT_MODELS_DIR",
    "DEFAULT_INCLUDE",
]


if __name__ == "__main__":
    main()
