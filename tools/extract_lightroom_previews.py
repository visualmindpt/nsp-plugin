"""
extract_lightroom_previews.py

Extrai os JPEGs pré-renderizados (previews) do Lightroom para uma pasta local.
Usado para gerar os dados de treino do modo Reference Match.

Uso:
    python tools/extract_lightroom_previews.py \
        --catalog "/path/to/Lightroom Catalog.lrcat" \
        --output data/previews \
        [--min-rating 3] \
        [--max-size 800] \
        [--limit 500]

Como funciona:
    O Lightroom guarda previews renderizados (com edições aplicadas) na pasta
    "[Catalog Name] Previews.lrdata" junto ao ficheiro .lrcat.
    Internamente é uma estrutura de SQLite + ficheiros JPEG com nomes baseados
    em UUID. Este script:
      1. Abre o catálogo SQLite e extrai os IDs e metadados das fotos
      2. Localiza o ficheiro .lrdata correspondente
      3. Mapeia cada foto ao seu ficheiro de preview JPEG (resolução 1:1 ou standard)
      4. Copia o preview para output/<image_id>.jpg

Nota: Os previews do Lightroom reflectem as edições actuais da foto
      (incluindo ajustes do Develop) — são exactamente o que o
      StyleFingerprintExtractor precisa.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Localizar pasta de previews
# ---------------------------------------------------------------------------

def find_previews_lrdata(catalog_path: Path) -> Optional[Path]:
    """Localiza a pasta [Catalog Name] Previews.lrdata."""
    name = catalog_path.stem
    candidates = [
        catalog_path.parent / f"{name} Previews.lrdata",
        catalog_path.parent / f"{name}.lrpreviews",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ---------------------------------------------------------------------------
# Ler metadados das fotos do catálogo
# ---------------------------------------------------------------------------

def read_catalog_photos(catalog_path: Path, min_rating: int = 0) -> list[dict]:
    """
    Lê IDs, paths e ratings das fotos do catálogo.
    Retorna lista de dicts: {image_id, filename, rating, uuid}.
    """
    conn = sqlite3.connect(str(catalog_path))
    conn.row_factory = sqlite3.Row
    try:
        # Tentar tabelas comuns do Lightroom (variam por versão)
        queries = [
            """
            SELECT f.id_local as image_id,
                   f.idx_filename as filename,
                   COALESCE(m.rating, 0) as rating,
                   f.lc_idx_filename as uuid_hint
            FROM AgLibraryFile f
            LEFT JOIN Adobe_images m ON m.rootFile = f.id_local
            WHERE COALESCE(m.rating, 0) >= ?
            ORDER BY f.id_local
            """,
            """
            SELECT id_local as image_id,
                   idx_filename as filename,
                   0 as rating,
                   lc_idx_filename as uuid_hint
            FROM AgLibraryFile
            ORDER BY id_local
            """,
        ]
        rows = []
        for q in queries:
            try:
                rows = conn.execute(q, (min_rating,)).fetchall()
                if rows:
                    break
            except sqlite3.OperationalError:
                continue

        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Mapear foto -> ficheiro de preview
# ---------------------------------------------------------------------------

def find_preview_for_image(
    image_id: int,
    filename: str,
    lrdata_dir: Path,
) -> Optional[Path]:
    """
    Procura o JPEG de preview mais adequado para a foto.

    Estratégias (por ordem de preferência):
      1. Ficheiro <image_id>.jpg directamente na raiz da lrdata
      2. Ficheiro com nome semelhante ao filename em qualquer subdirectório
      3. Qualquer JPEG dentro de subdirectórios com prefixo de UUID
    """
    # 1. Ficheiro directo pelo ID
    candidate = lrdata_dir / f"{image_id}.jpg"
    if candidate.exists():
        return candidate

    # 2. Procura por stem do filename
    stem = Path(filename).stem
    for p in lrdata_dir.rglob(f"{stem}*.jpg"):
        return p

    # 3. Procurar por ID como parte de nome de ficheiro
    id_str = str(image_id)
    for p in lrdata_dir.rglob(f"*{id_str}*.jpg"):
        return p

    # 4. Estrutura interna: Lightroom guarda em subdirectorios UUID-based
    # O mapeamento está em Previews.db dentro da lrdata
    previews_db = lrdata_dir / "previews.db"
    if not previews_db.exists():
        previews_db = lrdata_dir / "Previews.db"
    if previews_db.exists():
        try:
            conn = sqlite3.connect(str(previews_db))
            conn.row_factory = sqlite3.Row
            # Tentar diferentes schemas
            for table in ("ImageCacheEntry", "images", "Previews"):
                try:
                    row = conn.execute(
                        f"SELECT * FROM {table} WHERE imageId = ? OR filename LIKE ? LIMIT 1",
                        (image_id, f"%{stem}%")
                    ).fetchone()
                    if row:
                        # Tentar obter path relativo
                        for col in ("relativeDataPath", "filePath", "path", "uuid"):
                            val = row[col] if col in row.keys() else None
                            if val:
                                full = lrdata_dir / str(val)
                                if full.exists():
                                    conn.close()
                                    return full
                except sqlite3.OperationalError:
                    continue
            conn.close()
        except Exception as e:
            logger.debug(f"Erro ao ler previews.db: {e}")

    return None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def extract_previews(
    catalog_path: Path,
    output_dir: Path,
    min_rating: int = 0,
    max_size: int = 800,
    limit: Optional[int] = None,
) -> None:
    """Extrai previews do Lightroom para output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Catálogo: {catalog_path}")
    logger.info(f"Output:   {output_dir}")

    lrdata = find_previews_lrdata(catalog_path)
    if lrdata is None:
        logger.error(
            "Pasta de previews .lrdata não encontrada junto ao catálogo.\n"
            "Certifique-se que os previews estão gerados no Lightroom "
            "(Library → Previews → Build Standard-Sized Previews)."
        )
        return

    logger.info(f"Previews dir: {lrdata}")

    photos = read_catalog_photos(catalog_path, min_rating=min_rating)
    logger.info(f"{len(photos)} fotos no catálogo (rating ≥ {min_rating})")

    if limit:
        photos = photos[:limit]
        logger.info(f"Limitado a {limit} fotos")

    found, missing = 0, 0
    for photo in photos:
        image_id = photo['image_id']
        filename = photo.get('filename', str(image_id))

        preview_src = find_preview_for_image(image_id, filename, lrdata)

        if preview_src is None:
            missing += 1
            logger.debug(f"Preview não encontrado para {filename} (id={image_id})")
            continue

        dest = output_dir / f"{image_id}.jpg"
        if dest.exists():
            found += 1
            continue

        try:
            if max_size and max_size > 0:
                # Redimensionar com Pillow se disponível
                try:
                    from PIL import Image
                    img = Image.open(str(preview_src)).convert('RGB')
                    img.thumbnail((max_size, max_size), Image.LANCZOS)
                    img.save(str(dest), 'JPEG', quality=88)
                except ImportError:
                    # Sem Pillow — copiar directamente
                    shutil.copy2(str(preview_src), str(dest))
            else:
                shutil.copy2(str(preview_src), str(dest))
            found += 1
        except Exception as e:
            logger.warning(f"Erro ao copiar preview de {filename}: {e}")
            missing += 1

    logger.info(f"Completo: {found} previews extraídos, {missing} não encontrados")
    logger.info(f"JPEGs disponíveis em: {output_dir}")

    if missing > 0:
        logger.info(
            "\nDica: Para maximizar os previews disponíveis, no Lightroom:\n"
            "  Library → Previews → Build 1:1 Previews\n"
            "  (demora alguns minutos mas gera previews de alta qualidade)"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai previews do Lightroom para treino do modo Reference Match"
    )
    parser.add_argument(
        '--catalog', '-c',
        required=True,
        help="Path para o ficheiro .lrcat"
    )
    parser.add_argument(
        '--output', '-o',
        default='data/previews',
        help="Directório de output (default: data/previews)"
    )
    parser.add_argument(
        '--min-rating', '-r',
        type=int, default=3,
        help="Rating mínimo das fotos a exportar (default: 3)"
    )
    parser.add_argument(
        '--max-size', '-s',
        type=int, default=800,
        help="Lado máximo do JPEG exportado em píxeis (default: 800)"
    )
    parser.add_argument(
        '--limit', '-l',
        type=int, default=None,
        help="Limite de fotos a processar (default: todas)"
    )
    args = parser.parse_args()

    extract_previews(
        catalog_path=Path(args.catalog),
        output_dir=Path(args.output),
        min_rating=args.min_rating,
        max_size=args.max_size,
        limit=args.limit,
    )


if __name__ == '__main__':
    main()
