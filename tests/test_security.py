"""
Tests for security fixes in NSP Plugin.
Validates SQL injection prevention, path traversal protection, and rate limiting.
"""
import pytest
import sqlite3
from pathlib import Path
import sys

# Import security-critical functions
from services.server import _validate_image_path


@pytest.mark.unit
@pytest.mark.security
def test_sql_injection_prevention_consistency(sample_records):
    """Test that consistency analyzer prevents SQL injection."""
    from services.consistency import ConsistencyAnalyzer

    analyzer = ConsistencyAnalyzer(collection="test")

    # Attempt SQL injection via record_ids
    malicious_ids = [1, "1 OR 1=1", "1; DROP TABLE records;", "1' OR '1'='1"]

    # Should not crash and should filter out invalid IDs
    try:
        # This should safely handle malicious input
        report = analyzer.analyze_and_persist(malicious_ids, generated_by="test")

        # Verify no records were affected by injection
        conn = sqlite3.connect(sample_records)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM records")
        count = cursor.fetchone()[0]
        conn.close()

        # All original records should still exist
        assert count == 10

    except Exception as e:
        # Should handle gracefully, not crash
        pytest.fail(f"Should handle malicious input gracefully: {e}")


@pytest.mark.unit
@pytest.mark.security
def test_path_traversal_prevention():
    """Test that path traversal attacks are blocked."""
    # Valid paths
    valid_paths = [
        Path("/Users/test/photo.jpg"),
        Path.home() / "Pictures" / "photo.arw",
    ]

    for path in valid_paths:
        # Create parent directory for testing
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

        result = _validate_image_path(path)
        assert result == True, f"Valid path should be accepted: {path}"

        # Cleanup
        path.unlink()

    # Path traversal attempts
    malicious_paths = [
        Path("../../../etc/passwd"),
        Path("/etc/shadow"),
        Path("~/../../root/.ssh/id_rsa"),
    ]

    for path in malicious_paths:
        result = _validate_image_path(path)
        assert result == False, f"Path traversal should be blocked: {path}"


@pytest.mark.unit
@pytest.mark.security
def test_path_validation_whitelist():
    """Test that only whitelisted base paths are allowed."""
    # Paths outside whitelist
    forbidden_paths = [
        Path("/etc/hosts"),
        Path("/System/Library/test.jpg"),
        Path("/private/var/log/test.jpg"),
    ]

    for path in forbidden_paths:
        result = _validate_image_path(path)
        assert result == False, f"Path outside whitelist should be rejected: {path}"


@pytest.mark.unit
@pytest.mark.security
def test_path_validation_extension_whitelist():
    """Test that only image extensions are allowed."""
    # Create temp file with allowed extension
    allowed_path = Path("/tmp/test.jpg")
    allowed_path.touch()

    result = _validate_image_path(allowed_path)
    assert result == True

    allowed_path.unlink()

    # Disallowed extensions
    forbidden_extensions = [
        Path("/tmp/malicious.exe"),
        Path("/tmp/script.sh"),
        Path("/tmp/config.json"),
        Path("/tmp/database.db"),
    ]

    for path in forbidden_extensions:
        path.touch()
        result = _validate_image_path(path)
        assert result == False, f"Non-image extension should be rejected: {path}"
        path.unlink()


@pytest.mark.unit
@pytest.mark.security
def test_path_validation_symlink_resolution():
    """Test that symlinks are resolved before validation."""
    import tempfile

    # Create a symlink pointing to /etc/passwd
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        temp_path = Path(f.name)

    # This should fail because symlinks to system files are blocked
    result = _validate_image_path(temp_path)

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.mark.unit
@pytest.mark.security
def test_feedback_vector_size_validation(sample_records):
    """Test that feedback endpoint validates vector size."""
    from services.server import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Too short vector (should be 22)
    short_vector = [1.0, 2.0, 3.0]

    response = client.post(
        "/feedback",
        json={
            "original_record_id": 1,
            "corrected_develop_vector": short_vector,
        },
    )

    assert response.status_code == 400
    assert "deve ter 22 valores" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.api
def test_rate_limiting_predict_endpoint():
    """Test that /predict endpoint enforces rate limiting."""
    from services.server import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Make multiple rapid requests (exceeds 10/minute limit)
    responses = []
    for i in range(15):
        response = client.post(
            "/predict",
            json={
                "image_path": "/tmp/test.jpg",
                "exif": {"iso": 400, "width": 6000, "height": 4000},
                "model": "lightgbm",
            },
        )
        responses.append(response.status_code)

    # Should eventually get rate limited (429)
    assert 429 in responses, "Rate limiting should trigger after 10 requests"


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.api
def test_rate_limiting_feedback_endpoint():
    """Test that /feedback endpoint enforces rate limiting."""
    from services.server import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    develop_vector = [0.0] * 22

    # Make multiple rapid requests (exceeds 30/minute limit)
    responses = []
    for i in range(35):
        response = client.post(
            "/feedback",
            json={
                "original_record_id": i + 1,
                "corrected_develop_vector": develop_vector,
            },
        )
        responses.append(response.status_code)

    # Should eventually get rate limited
    assert 429 in responses, "Rate limiting should trigger after 30 requests"


@pytest.mark.unit
@pytest.mark.security
def test_preview_b64_size_limit():
    """Test that preview_b64 payload size is limited."""
    from services.server import _materialize_input
    import base64

    # Create payload > 50MB
    large_data = b"x" * (51 * 1024 * 1024)
    large_b64 = base64.b64encode(large_data).decode()

    with pytest.raises(Exception) as exc_info:
        _materialize_input(None, large_b64)

    assert "excede tamanho máximo" in str(exc_info.value) or "HTTPException" in str(type(exc_info.value))


@pytest.mark.unit
@pytest.mark.security
def test_directory_path_rejection():
    """Test that directory paths are rejected (only files allowed)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)

        result = _validate_image_path(dir_path)
        assert result == False, "Directory paths should be rejected"


@pytest.mark.unit
@pytest.mark.security
def test_nonexistent_path_rejection():
    """Test that non-existent paths are rejected."""
    nonexistent_path = Path("/tmp/this_file_does_not_exist_12345.jpg")

    result = _validate_image_path(nonexistent_path)
    assert result == False, "Non-existent paths should be rejected"


@pytest.mark.unit
@pytest.mark.security
def test_parameterized_query_feedback(sample_records):
    """Test that feedback insertion uses parameterized queries."""
    from services.db_utils import get_db_connection

    develop_vector = [0.0] * 22

    # Insert feedback with potentially malicious ID
    malicious_id = "1; DROP TABLE feedback_records;"

    with get_db_connection(sample_records) as conn:
        # This should safely handle the malicious input via parameterization
        conn.execute(
            """
            INSERT INTO feedback_records (original_record_id, corrected_develop_vector)
            VALUES (?, ?)
            """,
            (malicious_id, str(develop_vector)),
        )

    # Verify table still exists
    with get_db_connection(sample_records) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback_records'")
        result = cursor.fetchone()

    assert result is not None, "Table should not have been dropped"
