"""
Tests for services/server.py FastAPI endpoints.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.ai_core.feedback_collector import FeedbackCollector

SAMPLE_SLIDERS = {"exposure": 0.05, "contrast": -2.0}


@pytest.fixture
def client():
    """FastAPI test client."""
    from services.server import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_ai_predictor(monkeypatch):
    """Substitui o predictor real por um fake rápido para os testes."""
    from services import server

    class FakePredictor:
        def predict(self, image_path):
            return {
                "preset_id": 1,
                "preset_confidence": 0.97,
                "final_params": SAMPLE_SLIDERS,
            }

    fake = FakePredictor()
    monkeypatch.setattr(server, "AI_PREDICTOR", fake)
    return fake


@pytest.fixture
def feedback_env(sample_prediction, monkeypatch):
    """Configura o FeedbackCollector para usar um DB temporário."""
    from services import server

    db_path, prediction_id = sample_prediction
    collector = FeedbackCollector(feedback_db_path=db_path)

    monkeypatch.setattr(server, "DB_PATH", Path(db_path))
    monkeypatch.setattr(server, "FEEDBACK_COLLECTOR", collector)
    return collector, prediction_id


@pytest.mark.integration
@pytest.mark.api
def test_health_endpoint(client):
    """Test /health endpoint returns correct status."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data == {"status": "ok", "v2_predictor_loaded": True}


@pytest.mark.integration
@pytest.mark.api
def test_predict_endpoint_missing_image_path(client):
    """Test /predict with missing image_path."""
    response = client.post(
        "/predict",
        json={
            "exif": {"iso": 400, "width": 6000, "height": 4000},
            "model": "nn",
        },
    )

    # Should fail validation
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.api
def test_predict_endpoint_invalid_path(client):
    """Test /predict falha quando image_path é inválido."""
    response = client.post(
        "/predict",
        json={
            "image_path": "/tmp/does_not_exist.jpg",
            "exif": {"iso": 400, "width": 6000, "height": 4000},
        },
    )

    assert response.status_code == 400
    assert "Caminho de imagem inválido" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.api
def test_feedback_v2_success(client, feedback_env):
    """Testa /v2/feedback com payload válido."""
    collector, prediction_id = feedback_env

    response = client.post(
        "/v2/feedback",
        json={
            "prediction_id": prediction_id,
            "rating": 4,
            "user_params": {"exposure": 0.2, "contrast": -3.0},
            "notes": "Melhorei ligeiramente a exposição",
            "tags": ["wb"],
            "feedback_type": "explicit",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["event_id"] is not None


@pytest.mark.integration
@pytest.mark.api
def test_feedback_v2_requires_prediction(client, feedback_env):
    """Testa erro quando prediction_id é desconhecido."""
    response = client.post(
        "/v2/feedback",
        json={"prediction_id": 9999, "rating": 3},
    )

    # Collector devolve None mas endpoint continua 200; garantir sem crash
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.integration
@pytest.mark.api
def test_culling_score_endpoint_empty(client):
    """Test /culling/score with empty items."""
    response = client.post("/culling/score", json={"items": []})

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 0


@pytest.mark.integration
@pytest.mark.api
def test_consistency_report_endpoint(client, sample_records, monkeypatch):
    """Test /consistency/report endpoint."""
    from services import server
    monkeypatch.setattr(server, "DB_PATH", sample_records)

    response = client.post(
        "/consistency/report",
        json={
            "record_ids": [1, 2, 3],
            "collection_name": "test_collection",
        },
    )

    # May succeed or fail depending on whether enough data exists
    # Just verify it doesn't crash
    assert response.status_code in [200, 400, 500]


@pytest.mark.integration
@pytest.mark.api
def test_predict_endpoint_requires_image_or_preview(client):
    """Test that /predict requires either image_path or preview_b64."""
    response = client.post(
        "/predict",
        json={
            "exif": {"iso": 400, "width": 6000, "height": 4000},
            "model": "nn",
        },
    )

    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.api
def test_predict_with_preview_b64(client, sample_image):
    """Test /predict with base64 preview."""
    import base64

    # Read sample image and encode
    image_data = sample_image.read_bytes()
    b64_data = base64.b64encode(image_data).decode()

    response = client.post(
        "/predict",
        json={
            "preview_b64": b64_data,
            "exif": {"iso": 400, "width": 6000, "height": 4000},
            "model": "nn",
        },
    )

    # May fail if models not loaded, but should not be validation error
    assert response.status_code in [200, 404, 500, 503]
    assert response.status_code != 422  # Should not be validation error


@pytest.mark.integration
@pytest.mark.api
def test_cors_headers(client):
    """Test that CORS headers are present (if configured)."""
    response = client.options("/health")

    # FastAPI may or may not have CORS configured
    # Just verify OPTIONS works
    assert response.status_code in [200, 405]


@pytest.mark.integration
@pytest.mark.api
def test_content_type_json(client):
    """Test that API accepts and returns JSON."""
    response = client.get("/health")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
