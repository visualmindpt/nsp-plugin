"""
Tests for services/db_utils.py
Validates WAL mode, retry logic, and database utilities.
"""
import pytest
import sqlite3
import time
from pathlib import Path

from services.db_utils import (
    enable_wal_mode,
    get_db_connection,
    create_indexes_if_not_exist,
    optimize_database,
    get_database_stats,
)


@pytest.mark.unit
@pytest.mark.db
def test_enable_wal_mode(temp_db):
    """Test that WAL mode is enabled correctly."""
    enable_wal_mode(temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    result = cursor.fetchone()[0]
    conn.close()

    assert result.upper() == "WAL"


@pytest.mark.unit
@pytest.mark.db
def test_get_db_connection_success(temp_db):
    """Test successful database connection."""
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]

    assert result == 1


@pytest.mark.unit
@pytest.mark.db
def test_get_db_connection_auto_commit(temp_db):
    """Test that get_db_connection auto-commits on success."""
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO records (id_local, image_path) VALUES ('test', '/tmp/test.png')")

    # Verify data was committed
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM records")
        count = cursor.fetchone()[0]

    assert count == 1


@pytest.mark.unit
@pytest.mark.db
def test_get_db_connection_rollback_on_error(temp_db):
    """Test that get_db_connection rolls back on error."""
    try:
        with get_db_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO records (id_local, image_path) VALUES ('test', '/tmp/test.png')")
            raise RuntimeError("Simulated error")
    except RuntimeError:
        pass

    # Verify data was NOT committed
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM records")
        count = cursor.fetchone()[0]

    assert count == 0


@pytest.mark.unit
@pytest.mark.db
def test_get_db_connection_retry_on_lock(temp_db):
    """Test that get_db_connection retries when database is locked."""
    import threading

    def lock_database():
        conn = sqlite3.connect(temp_db, timeout=0.1)
        conn.execute("BEGIN EXCLUSIVE")
        time.sleep(0.5)  # Hold lock for 500ms
        conn.rollback()
        conn.close()

    # Start thread that locks database
    thread = threading.Thread(target=lock_database)
    thread.start()

    # Give thread time to acquire lock
    time.sleep(0.1)

    # This should retry and eventually succeed
    start_time = time.time()
    with get_db_connection(temp_db, retries=5, delay=0.1) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
    elapsed = time.time() - start_time

    thread.join()

    # Should have waited for lock to be released
    assert elapsed >= 0.3  # At least one retry


@pytest.mark.unit
@pytest.mark.db
def test_get_db_connection_fails_after_max_retries(temp_db):
    """Test that get_db_connection fails after max retries."""
    import threading

    def lock_database():
        conn = sqlite3.connect(temp_db, timeout=0.1)
        conn.execute("BEGIN EXCLUSIVE")
        time.sleep(5.0)  # Hold lock longer than retries
        conn.rollback()
        conn.close()

    thread = threading.Thread(target=lock_database)
    thread.start()

    time.sleep(0.1)

    # Should fail after exhausting retries
    with pytest.raises(sqlite3.OperationalError):
        with get_db_connection(temp_db, retries=3, delay=0.1, timeout=0.5) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")

    thread.join()


@pytest.mark.unit
@pytest.mark.db
def test_create_indexes_if_not_exist(sample_records):
    """Test that indexes are created correctly."""
    create_indexes_if_not_exist(sample_records)

    # Verify indexes exist
    conn = sqlite3.connect(sample_records)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
    indexes = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected_indexes = {
        'idx_records_image_path',
        'idx_records_id_local',
        'idx_feedback_original_id',
        'idx_feedback_timestamp',
    }

    # At least the records indexes should exist
    assert 'idx_records_image_path' in indexes
    assert 'idx_records_id_local' in indexes


@pytest.mark.integration
@pytest.mark.db
@pytest.mark.slow
def test_optimize_database(sample_records):
    """Test database optimization (VACUUM + ANALYZE)."""
    # This is slow but important
    optimize_database(sample_records)

    # Just verify it doesn't crash
    assert sample_records.exists()


@pytest.mark.unit
@pytest.mark.db
def test_get_database_stats(sample_records):
    """Test database statistics retrieval."""
    stats = get_database_stats(sample_records)

    assert 'file_size_mb' in stats
    assert 'total_records' in stats
    assert 'total_feedbacks' in stats
    assert 'journal_mode' in stats
    assert 'page_size' in stats

    assert stats['total_records'] == 10
    assert stats['total_feedbacks'] == 0
    assert isinstance(stats['file_size_mb'], float)


@pytest.mark.unit
@pytest.mark.db
def test_get_db_connection_row_factory(temp_db):
    """Test that Row factory allows dict-like access."""
    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO records (id_local, image_path) VALUES ('test', '/tmp/test.png')")

    with get_db_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_local, image_path FROM records WHERE id_local = 'test'")
        row = cursor.fetchone()

    # Test both indexed and named access
    assert row[0] == 'test'
    assert row['id_local'] == 'test'
    assert row['image_path'] == '/tmp/test.png'
