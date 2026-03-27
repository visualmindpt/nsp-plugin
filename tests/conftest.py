"""
Pytest configuration and fixtures for NSP Plugin tests.
"""
import sys
import tempfile
from pathlib import Path
import sqlite3
import json
import numpy as np

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_core.feedback_collector import FeedbackCollector


@pytest.fixture(scope="session")
def project_root():
    """Project root directory."""
    return ROOT


@pytest.fixture
def temp_db():
    """Temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_local TEXT UNIQUE,
            image_path TEXT,
            develop_vector TEXT,
            exif TEXT,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE feedback_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_record_id INTEGER NOT NULL,
            corrected_develop_vector TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE consistency_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT UNIQUE NOT NULL,
            collection_name TEXT NOT NULL,
            summary TEXT NOT NULL,
            generated_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def sample_records(temp_db):
    """Insert sample records into temp database."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Sample develop vector (22 sliders)
    develop_vector = [0.5, 10, -20, 30, -15, 5, 20, 15, 10, 5000, 5, 1.0, 25, 10, 15, 10, 0, 5, -5, 10, -10, 0]

    # Sample EXIF
    exif = {"iso": 400, "width": 6000, "height": 4000}

    # Insert 10 sample records
    for i in range(10):
        cursor.execute(
            """
            INSERT INTO records (id_local, image_path, develop_vector, exif)
            VALUES (?, ?, ?, ?)
            """,
            (
                f"test_photo_{i}",
                f"/tmp/test_{i}.arw",
                json.dumps(develop_vector),
                json.dumps(exif),
            ),
        )

    conn.commit()
    conn.close()

    return temp_db


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample image for testing."""
    # Create a tiny PNG (1x1 pixel)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    image_path = tmp_path / "test_image.png"
    image_path.write_bytes(png_data)

    return image_path


@pytest.fixture
def sample_develop_vector():
    """Sample develop vector (22 sliders)."""
    return [0.5, 10, -20, 30, -15, 5, 20, 15, 10, 5000, 5, 1.0, 25, 10, 15, 10, 0, 5, -5, 10, -10, 0]


@pytest.fixture
def sample_exif():
    """Sample EXIF metadata."""
    return {"iso": 400, "width": 6000, "height": 4000}


@pytest.fixture
def mock_embeddings(tmp_path):
    """Mock embeddings file."""
    embeddings = np.random.randn(10, 512).astype(np.float32)
    embeddings_path = tmp_path / "embeddings_pca.npy"
    np.save(embeddings_path, embeddings)
    return embeddings_path


@pytest.fixture
def mock_models(tmp_path):
    """Mock model artifacts."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    # Create mock PCA model
    import joblib
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    pca = PCA(n_components=128)
    pca.fit(np.random.randn(100, 512))
    joblib.dump(pca, models_dir / "pca_model.pkl")

    # Create mock scaler
    scaler = StandardScaler()
    scaler.fit(np.random.randn(100, 3))
    joblib.dump(scaler, models_dir / "exif_scaler.pkl")

    return models_dir


@pytest.fixture
def feedback_db(tmp_path):
    """Feedback DB com schema moderno (predictions + feedback_events)."""
    db_path = tmp_path / "feedback.db"
    FeedbackCollector(feedback_db_path=db_path)  # cria tabelas necessárias
    return db_path


@pytest.fixture
def sample_prediction(feedback_db):
    """Cria uma predição registada e devolve (db_path, prediction_id)."""
    collector = FeedbackCollector(feedback_db_path=feedback_db)
    prediction_id = collector.log_prediction(
        "/tmp/test_image.arw",
        {
            "preset_id": 1,
            "preset_confidence": 0.95,
            "final_params": {"exposure": 0.1, "contrast": -5.0},
        },
    )
    return feedback_db, prediction_id
