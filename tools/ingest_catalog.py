import numpy as np
import sqlite3
import json
import logging
from pathlib import Path
from sklearn.cluster import KMeans

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = APP_ROOT / 'data' / 'nsp_plugin.db'
EMBEDDINGS_PATH = APP_ROOT / 'data' / 'embeddings.npy'
NUM_RECORDS = 5000

# --- Editing Style Definitions ---
# Define a few base 'styles' as develop vectors. These represent common editing aesthetics.
EDITING_STYLES = {
    "High-Contrast B&W": [
        0.5, 50, -100, 100, 80, -80,  # exposure, contrast, highlights, shadows, whites, blacks
        20, 30, 10, 0, -100,         # texture, clarity, dehaze, vibrance, saturation
        6500, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 # color & other sliders (neutral for B&W)
    ],
    "Warm & Soft": [
        0.2, -20, -30, 40, 20, -10, # exposure, contrast, highlights, shadows, whites, blacks
        -10, -15, -5, 30, 15,       # texture, clarity, dehaze, vibrance, saturation
        7500, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 # temp, tint & others
    ],
    "Cool & Moody": [
        -0.3, 15, -50, 25, -20, 5,  # exposure, contrast, highlights, shadows, whites, blacks
        10, 5, 15, -20, -10,        # texture, clarity, dehaze, vibrance, saturation
        5500, -10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 # temp, tint & others
    ],
    "Vibrant Landscape": [
        0.1, 25, -20, 30, 10, -5,   # exposure, contrast, highlights, shadows, whites, blacks
        30, 20, 10, 40, 20,         # texture, clarity, dehaze, vibrance, saturation
        6000, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 # temp, tint & others
    ],
    "Faded Film": [
        0.0, -30, 20, 50, 40, -30,  # exposure, contrast, highlights, shadows, whites, blacks
        -5, -10, -15, -15, -25,     # texture, clarity, dehaze, vibrance, saturation
        6800, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 # temp, tint & others
    ]
}

# Ensure all style vectors have the correct length (22)
for name, style in EDITING_STYLES.items():
    if len(style) != 22:
        # Pad with zeros if too short, or truncate if too long
        EDITING_STYLES[name] = (style + [0] * 22)[:22]

STYLE_NAMES = list(EDITING_STYLES.keys())
NUM_STYLES = len(STYLE_NAMES)

def create_mock_develop_vector(style_vector, noise_level=5.0):
    """Generates a develop vector by adding noise to a base style vector."""
    noise = np.random.normal(0, noise_level, len(style_vector))
    # Add noise, but clamp to reasonable Lightroom slider ranges
    # This is a simplified clamping, a more robust solution would be per-slider
    noisy_vector = np.clip(style_vector + noise, -100, 100)
    # Special case for temp (larger range)
    temp_index = 11 # The index for 'temp' slider
    noisy_vector[temp_index] = np.clip(style_vector[temp_index] + noise[temp_index] * 100, 2000, 50000)
    return noisy_vector.tolist()

def create_mock_exif():
    """Generates a mock EXIF data dictionary with native Python types."""
    return json.dumps({
        "iso": int(np.random.choice([100, 200, 400, 800, 1600])),
        "shutter_speed": float(round(np.random.uniform(0.001, 0.1), 4)),
        "aperture": float(round(np.random.uniform(1.8, 8.0), 1)),
        "focal_length": int(np.random.choice([24, 35, 50, 85, 135])),
        "camera_model": "MockCamera_v3",
        "width": 6000,
        "height": 4000
    })

def main():
    """Main function to generate and ingest data."""
    logging.info("Starting data ingestion process with style-based generation.")
    
    # 1. Load embeddings
    logging.info(f"Loading embeddings from {EMBEDDINGS_PATH}")
    all_embeddings = np.load(EMBEDDINGS_PATH)
    if len(all_embeddings) != NUM_RECORDS:
        logging.error(f"Mismatch between NUM_RECORDS ({NUM_RECORDS}) and number of embeddings ({len(all_embeddings)}).")
        return

    # 2. Cluster embeddings into N styles
    logging.info(f"Clustering {NUM_RECORDS} embeddings into {NUM_STYLES} styles using KMeans...")
    kmeans = KMeans(n_clusters=NUM_STYLES, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(all_embeddings)
    logging.info("Clustering complete.")

    # 3. Setup database
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS records")
    cursor.execute("""
    CREATE TABLE records (
        id INTEGER PRIMARY KEY,
        exif TEXT,
        develop_vector TEXT
    )
    """)
    # Also drop feedback records to ensure a clean state
    cursor.execute("DROP TABLE IF EXISTS feedback_records")
    cursor.execute("""
        CREATE TABLE feedback_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_record_id INTEGER,
            corrected_develop_vector TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (original_record_id) REFERENCES records (id)
        );
    """)
    conn.commit()
    logging.info("Database tables re-created.")

    # 4. Generate and insert records based on clusters
    logging.info(f"Generating and inserting {NUM_RECORDS} records...")
    records_to_insert = []
    for i in range(NUM_RECORDS):
        record_id = i
        cluster_id = cluster_labels[i]
        style_name = STYLE_NAMES[cluster_id]
        base_style_vector = EDITING_STYLES[style_name]
        
        develop_vector = create_mock_develop_vector(base_style_vector)
        exif_data = create_mock_exif()
        
        records_to_insert.append((record_id, exif_data, json.dumps(develop_vector)))

    cursor.executemany("INSERT INTO records (id, exif, develop_vector) VALUES (?, ?, ?)", records_to_insert)
    conn.commit()
    conn.close()

    logging.info(f"Successfully inserted {len(records_to_insert)} records into the database.")
    logging.info("Data ingestion process complete.")

if __name__ == "__main__":
    main()
