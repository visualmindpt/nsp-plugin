
import requests
import sqlite3
import json
import logging
from pathlib import Path
import random

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / 'data'
DB_PATH = DATA_DIR / 'nsp_plugin.db'
API_URL = "http://127.0.0.1:8000/feedback"
NUM_FEEDBACK_RECORDS = 5 # Number of feedback records to generate

ALL_SLIDER_NAMES = [
    'exposure', 'contrast', 'highlights', 'shadows', 'whites', 'blacks',
    'texture', 'clarity', 'dehaze', 'vibrance', 'saturation',
    'temp', 'tint', 'sharpen_amount', 'sharpen_radius', 'sharpen_detail', 'sharpen_masking',
    'nr_luminance', 'nr_detail', 'nr_color', 'vignette', 'grain'
]

def get_random_records_from_db():
    """Fetches a few random records from the 'records' table."""
    if not DB_PATH.exists():
        logging.error(f"Database not found at {DB_PATH}. Please run `tools/ingest_catalog.py` first.")
        return []

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # SEGURANÇA: Usar parameterização em vez de f-string
        cursor.execute("SELECT id, develop_vector FROM records ORDER BY RANDOM() LIMIT ?", (NUM_FEEDBACK_RECORDS,))
        records = cursor.fetchall()
        logging.info(f"Fetched {len(records)} random records from the database.")
        return records
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return []
    finally:
        if conn:
            conn.close()

def generate_and_send_feedback(records):
    """Generates slightly modified develop vectors and sends them to the /feedback endpoint."""
    if not records:
        logging.warning("No records provided to generate feedback for.")
        return

    headers = {'Content-Type': 'application/json'}
    success_count = 0

    for record_id, original_vector_json in records:
        try:
            original_vector = json.loads(original_vector_json)
            if len(original_vector) != len(ALL_SLIDER_NAMES):
                logging.warning(f"Skipping record {record_id} due to mismatched vector length.")
                continue

            # Create a corrected vector with a slight modification
            corrected_vector = original_vector.copy()
            # Modify a key slider like exposure by a small random amount
            exposure_index = ALL_SLIDER_NAMES.index('exposure')
            correction = round(random.uniform(-0.25, 0.25), 4)
            corrected_vector[exposure_index] += correction
            logging.info(f"Record {record_id}: Correcting exposure by {correction:.4f}")

            # Prepare payload
            payload = {
                "original_record_id": record_id,
                "corrected_develop_vector": corrected_vector
            }

            # Send request to the API
            response = requests.post(API_URL, data=json.dumps(payload), headers=headers)

            if response.status_code == 200:
                logging.info(f"Successfully sent feedback for record {record_id}. Response: {response.json()}")
                success_count += 1
            else:
                logging.error(f"Failed to send feedback for record {record_id}. Status: {response.status_code}, Response: {response.text}")

        except (json.JSONDecodeError, IndexError, requests.RequestException) as e:
            logging.error(f"An error occurred while processing record {record_id}: {e}")

    logging.info(f"--- Feedback generation complete. {success_count}/{len(records)} requests were successful. ---")

def main():
    logging.info("Starting feedback generation process...")
    # First, check if the server is reachable
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if response.status_code != 200:
            logging.error(f"Server at http://127.0.0.1:8000 is not healthy. Status: {response.status_code}. Aborting.")
            return
        logging.info("Server is healthy. Proceeding to generate feedback.")
    except requests.ConnectionError:
        logging.error("Could not connect to the server at http://127.0.0.1:8000. Please ensure the server is running. Aborting.")
        return

    records_to_update = get_random_records_from_db()
    generate_and_send_feedback(records_to_update)

if __name__ == '__main__':
    main()
