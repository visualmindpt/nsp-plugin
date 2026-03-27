"""
tools/extract_from_lrcat.py

Extract Lightroom catalog data into the NSP Plugin training database.
"""
import argparse
import json
import logging
import os
import plistlib
import re
import sqlite3
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ALL_SLIDER_NAMES: Sequence[str] = (
    "exposure",
    "contrast",
    "highlights",
    "shadows",
    "whites",
    "blacks",
    "texture",
    "clarity",
    "dehaze",
    "vibrance",
    "saturation",
    "temp",
    "tint",
    "sharpen_amount",
    "sharpen_radius",
    "sharpen_detail",
    "sharpen_masking",
    "nr_luminance",
    "nr_detail",
    "nr_color",
    "vignette",
    "grain",
    # Novos sliders da Fase 1: Calibração
    "shadow_tint",
    "red_primary_hue",
    "red_primary_saturation",
    "green_primary_hue",
    "green_primary_saturation",
    "blue_primary_hue",
    "blue_primary_saturation",
    # Novos sliders da Fase 1: HSL (Cores Primárias)
    "red_hue",
    "red_saturation",
    "red_luminance",
    "green_hue",
    "green_saturation",
    "green_luminance",
    "blue_hue",
    "blue_saturation",
    "blue_luminance",
)

LIGHTROOM_TO_SLIDER: Dict[str, str] = {
    "Exposure2012": "exposure",
    "Contrast2012": "contrast",
    "Highlights2012": "highlights",
    "Shadows2012": "shadows",
    "Whites2012": "whites",
    "Blacks2012": "blacks",
    "Texture": "texture",
    "Clarity2012": "clarity",
    "Dehaze": "dehaze",
    "Vibrance": "vibrance",
    "Saturation": "saturation",
    "Temperature": "temp",
    "Tint": "tint",
    "SharpenAmount": "sharpen_amount",
    "SharpenRadius": "sharpen_radius",
    "SharpenDetail": "sharpen_detail",
    "SharpenEdgeMasking": "sharpen_masking",
    "LuminanceSmoothing": "nr_luminance",
    "LuminanceDetail": "nr_detail",
    "ColorNoiseReduction": "nr_color",
    "PostCropVignetteAmount": "vignette",
    "GrainAmount": "grain",
    # Novos sliders da Fase 1: Calibração
    "ColorBalanceShadows": "shadow_tint", # Assuming this is the Lightroom key for shadow tint
    "RedHue": "red_primary_hue",
    "RedSat": "red_primary_saturation",
    "GreenHue": "green_primary_hue",
    "GreenSat": "green_primary_saturation",
    "BlueHue": "blue_primary_hue",
    "BlueSat": "blue_primary_saturation",
    # Novos sliders da Fase 1: HSL (Cores Primárias)
    "HueRed": "red_hue",
    "SatRed": "red_saturation",
    "LumRed": "red_luminance",
    "HueGreen": "green_hue",
    "SatGreen": "green_saturation",
    "LumGreen": "green_luminance",
    "HueBlue": "blue_hue",
    "SatBlue": "blue_saturation",
    "LumBlue": "blue_luminance",
}

NUMERIC_PAIR_RE = re.compile(r"([A-Za-z0-9_]+)\s*=\s*(-?\d+(?:\.\d+)?)")


def _blob_to_bytes(blob: Union[bytes, memoryview, str]) -> bytes:
    if isinstance(blob, bytes):
        return blob
    if isinstance(blob, memoryview):
        return blob.tobytes()
    if isinstance(blob, str):
        return blob.encode("latin1")
    raise TypeError(f"Unsupported blob type: {type(blob)}")


def _parse_settings_text(text: str) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for key, value in NUMERIC_PAIR_RE.findall(text):
        if key not in LIGHTROOM_TO_SLIDER:
            continue
        try:
            values[LIGHTROOM_TO_SLIDER[key]] = float(value)
        except ValueError:
            continue
    return values


def decode_develop_settings(blob: Optional[Union[bytes, memoryview, str]], text: Optional[str]) -> Dict[str, float]:
    if text:
        parsed = _parse_settings_text(text)
        if parsed:
            return parsed

    data: Optional[bytes] = None
    if blob:
        try:
            raw = _blob_to_bytes(blob)
        except TypeError as exc:
            logging.debug("Unsupported develop blob type: %s", exc)
            raw = None
        if raw:
            try:
                data = zlib.decompress(raw)
            except zlib.error:
                data = raw

    if not data:
        return {}

    try:
        plist = plistlib.loads(data)
    except Exception as exc:
        logging.warning("Could not decode develop settings data: %s", exc)
        return {}

    values: Dict[str, float] = {}
    for lr_key, slider_name in LIGHTROOM_TO_SLIDER.items():
        raw_value = plist.get(lr_key)
        if raw_value is None:
            continue
        try:
            values[slider_name] = float(raw_value)
        except (TypeError, ValueError):
            logging.debug("Non-numeric value for %s (%s) -> %s", slider_name, lr_key, raw_value)
    return values


def compose_image_path(root: Optional[str], folder_rel: Optional[str], base_name: Optional[str], extension: Optional[str]) -> Optional[str]:
    if not base_name:
        return None

    root = (root or "").rstrip("/\\")
    folder_rel = (folder_rel or "").strip("/\\")
    ext = (extension or "").lstrip(".")

    filename = base_name
    if ext:
        filename = f"{base_name}.{ext}"

    parts: List[str] = []
    if root:
        parts.append(root)
    if folder_rel:
        parts.append(folder_rel)
    parts.append(filename)

    try:
        return str(Path(parts[0]).joinpath(*parts[1:])) if parts else None
    except Exception as exc:
        logging.warning("Failed to compose image path for %s: %s", filename, exc)
        return None


def ensure_database(db_path: Path, overwrite: bool) -> sqlite3.Connection:
    if overwrite and db_path.exists():
        db_path.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY,
            image_path TEXT,
            exif TEXT,
            develop_vector TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_record_id INTEGER,
            corrected_develop_vector TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (original_record_id) REFERENCES records (id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS culling_results (
            record_id INTEGER PRIMARY KEY,
            score REAL NOT NULL,
            sharpness REAL,
            exposure REAL,
            contrast REAL,
            keep_flag INTEGER NOT NULL,
            evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            FOREIGN KEY (record_id) REFERENCES records (id)
        )
        """
    )
    conn.commit()
    if overwrite:
        cur.execute("DELETE FROM records")
        cur.execute("DELETE FROM feedback_records")
        cur.execute("DELETE FROM culling_results")
        conn.commit()
    return conn


def fetch_catalog_rows(conn: sqlite3.Connection, limit: Optional[int]) -> Iterable[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    query = """
        SELECT
            ai.id_local AS image_id,
            rf.absolutePath AS root_path,
            af.pathFromRoot AS folder_rel,
            f.baseName AS base_name,
            f.extension AS extension,
            settings.settingsID AS develop_blob,
            settings.text AS develop_text,
            exif.isoSpeedRating AS iso,
            exif.aperture AS aperture,
            exif.shutterSpeed AS shutter_speed,
            exif.focalLength AS focal_length,
            exif.cameraModelRef AS camera_model_ref,
            ai.fileWidth AS file_width,
            ai.fileHeight AS file_height
        FROM Adobe_images AS ai
        JOIN AgLibraryFile AS f ON ai.rootFile = f.id_local
        JOIN AgLibraryFolder AS af ON f.folder = af.id_local
        JOIN AgLibraryRootFolder AS rf ON af.rootFolder = rf.id_local
        LEFT JOIN Adobe_imageDevelopSettings AS settings ON settings.image = ai.id_local
        LEFT JOIN AgHarvestedExifMetadata AS exif ON exif.image = ai.id_local
        WHERE settings.settingsID IS NOT NULL OR settings.text IS NOT NULL
        ORDER BY ai.id_local ASC
    """
    params: Tuple[object, ...] = ()
    if limit:
        query += " LIMIT ?"
        params = (limit,)
    yield from cur.execute(query, params)


def build_exif(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "iso": row["iso"] or 0,
        "aperture": row["aperture"] or 0.0,
        "shutter_speed": row["shutter_speed"] or 0.0,
        "focal_length": row["focal_length"] or 0.0,
        "camera_model": row["camera_model_ref"] or "",
        "width": row["file_width"] or 0,
        "height": row["file_height"] or 0,
    }


def build_develop_vector(develop_values: Dict[str, float]) -> List[float]:
    return [float(develop_values.get(name, 0.0)) for name in ALL_SLIDER_NAMES]


def insert_records(
    conn: sqlite3.Connection,
    records: Iterable[Tuple[int, str, Dict[str, object], List[float]]],
    skip_missing_images: bool,
    missing_limit: Optional[int],
) -> int:
    cur = conn.cursor()
    total_inserted = 0
    missing_count = 0
    for idx, image_path, exif, develop_vector in records:
        if skip_missing_images and (not image_path or not os.path.exists(image_path)):
            missing_count += 1
            if missing_limit and missing_count >= missing_limit:
                logging.warning("Reached missing image limit (%d). Aborting.", missing_limit)
                break
            logging.warning("Skipping missing image: %s", image_path)
            continue

        cur.execute(
            "INSERT OR REPLACE INTO records (id, image_path, exif, develop_vector) VALUES (?, ?, ?, ?)",
            (idx, image_path, json.dumps(exif), json.dumps(develop_vector)),
        )
        total_inserted += 1

    conn.commit()
    return total_inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Lightroom catalog data for NSP Plugin.")
    parser.add_argument("--catalog_path", required=True, help="Path to the Lightroom .lrcat file.")
    parser.add_argument("--db_out", default="data/nsp_plugin.db", help="Output SQLite database path.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of photos processed.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing records table.")
    parser.add_argument("--skip-missing-images", action="store_true", help="Ignore missing image files.")
    parser.add_argument("--missing-limit", type=int, default=None, help="Max missing images before aborting.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog_path = Path(args.catalog_path).expanduser().resolve()
    db_out = Path(args.db_out).expanduser().resolve()

    if not catalog_path.exists():
        raise FileNotFoundError(f"Lightroom catalog not found at {catalog_path}")

    logging.info("Opening Lightroom catalog (read-only): %s", catalog_path)
    catalog_conn = sqlite3.connect(str(catalog_path))

    try:
        rows = list(fetch_catalog_rows(catalog_conn, args.limit))
        if not rows:
            logging.warning("No develop settings found in catalog. Nothing to do.")
            return
        logging.info("Fetched %d records from catalog.", len(rows))
    finally:
        catalog_conn.close()

    logging.info("Preparing output database at %s", db_out)
    out_conn = ensure_database(db_out, overwrite=args.overwrite)

    try:
        prepared_records: List[Tuple[int, Optional[str], Dict[str, object], List[float]]] = []
        for row in rows:
            develop_values = decode_develop_settings(row["develop_blob"], row["develop_text"])
            if not develop_values:
                logging.debug("No develop settings for Lightroom image id %s; skipping.", row["image_id"])
                continue

            develop_vector = build_develop_vector(develop_values)
            image_path = compose_image_path(row["root_path"], row["folder_rel"], row["base_name"], row["extension"])
            if not image_path:
                logging.warning("Could not compose image path for Lightroom image id %s", row["image_id"])
                continue

            exif = build_exif(row)
            prepared_records.append((int(row["image_id"]), image_path, exif, develop_vector))

        if not prepared_records:
            logging.warning("No valid records assembled. Exiting without changes.")
            return

        inserted = insert_records(
            out_conn,
            prepared_records,
            skip_missing_images=args.skip_missing_images,
            missing_limit=args.missing_limit,
        )
        logging.info("Inserted %d records into %s", inserted, db_out)

    finally:
        out_conn.close()


if __name__ == "__main__":
    main()
