"""
services/db_utils.py

Utilitários para gestão segura e robusta de conexões SQLite.
Implementa WAL mode, retry logic e connection pooling.
"""

import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enable_wal_mode(db_path: Path) -> None:
    """
    Ativa Write-Ahead Logging para melhor concorrência.
    WAL permite leituras concorrentes com escritas.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()

        # Ativar WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")
        result = cursor.fetchone()
        logger.info(f"WAL mode ativado para {db_path}: {result}")

        # Configurar para melhor performance
        cursor.execute("PRAGMA synchronous=NORMAL")  # Mais rápido que FULL, ainda seguro
        cursor.execute("PRAGMA temp_store=MEMORY")   # Temporários em memória
        cursor.execute("PRAGMA mmap_size=30000000000")  # 30GB memory-mapped I/O
        cursor.execute("PRAGMA page_size=4096")      # 4KB pages

        conn.commit()
        conn.close()
        logger.info(f"Configurações de performance aplicadas para {db_path}")
    except sqlite3.Error as exc:
        logger.error(f"Falha ao ativar WAL mode: {exc}")
        raise


@contextmanager
def get_db_connection(
    db_path: Path,
    retries: int = 5,
    delay: float = 0.1,
    timeout: float = 10.0
) -> Iterator[sqlite3.Connection]:
    """
    Context manager para obter conexão SQLite com retry logic.

    Args:
        db_path: Caminho para o ficheiro da base de dados
        retries: Número de tentativas em caso de lock
        delay: Delay inicial entre tentativas (exponential backoff)
        timeout: Timeout da conexão em segundos

    Yields:
        Conexão SQLite aberta

    Example:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM records")
            # conn.commit() é automático no exit sem exceção
    """
    conn = None
    last_exception = None

    for attempt in range(retries):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            # Configurar row factory para acesso por nome de coluna
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()  # Auto-commit no sucesso
            return
        except sqlite3.OperationalError as exc:
            last_exception = exc
            if "database is locked" in str(exc) and attempt < retries - 1:
                backoff = delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Database locked, retry {attempt + 1}/{retries} após {backoff:.2f}s"
                )
                time.sleep(backoff)
                continue
            raise
        except Exception as exc:
            last_exception = exc
            if conn:
                conn.rollback()  # Rollback em caso de erro
            raise
        finally:
            if conn:
                conn.close()

    # Se chegamos aqui, esgotaram-se as tentativas
    if last_exception:
        raise last_exception


def create_indexes_if_not_exist(db_path: Path) -> None:
    """Cria índices de performance se não existirem."""
    indexes = [
        # Índice para lookups por image_path
        """CREATE INDEX IF NOT EXISTS idx_records_image_path
           ON records(image_path)""",

        # Índice para lookups por id (usado pelo feedback)
        """CREATE INDEX IF NOT EXISTS idx_records_id
           ON records(id)""",

        # Índice para queries de feedback por original_record_id
        """CREATE INDEX IF NOT EXISTS idx_feedback_original_id
           ON feedback_records(original_record_id)""",

        # Índice para queries temporais de feedback
        """CREATE INDEX IF NOT EXISTS idx_feedback_timestamp
           ON feedback_records(timestamp DESC)""",

        # Índice para culling results (se a tabela existir)
        """CREATE INDEX IF NOT EXISTS idx_culling_score
           ON culling_results(score DESC, keep_flag)""",

        # Índice para consistency reports
        """CREATE INDEX IF NOT EXISTS idx_consistency_collection
           ON consistency_reports(collection_name, created_at DESC)""",
    ]

    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except sqlite3.OperationalError as exc:
                    # Ignorar se a tabela não existir
                    if "no such table" not in str(exc):
                        logger.warning(f"Falha ao criar índice: {exc}")

        logger.info(f"Índices de performance criados/verificados para {db_path}")
    except sqlite3.Error as exc:
        logger.error(f"Falha ao criar índices: {exc}")


def optimize_database(db_path: Path) -> None:
    """
    Otimiza a base de dados (VACUUM, ANALYZE).
    Deve ser executado periodicamente (ex: semanalmente).
    """
    try:
        with get_db_connection(db_path, timeout=60.0) as conn:
            cursor = conn.cursor()

            # ANALYZE atualiza estatísticas do query planner
            logger.info("A executar ANALYZE...")
            cursor.execute("ANALYZE")

            # VACUUM compacta a base de dados (pode demorar)
            logger.info("A executar VACUUM...")
            cursor.execute("VACUUM")

        logger.info(f"Base de dados otimizada: {db_path}")
    except sqlite3.Error as exc:
        logger.error(f"Falha ao otimizar base de dados: {exc}")


def get_database_stats(db_path: Path) -> dict:
    """Retorna estatísticas da base de dados."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Tamanho do ficheiro
            stats['file_size_mb'] = db_path.stat().st_size / (1024 * 1024)

            # Número de records
            cursor.execute("SELECT COUNT(*) FROM records")
            stats['total_records'] = cursor.fetchone()[0]

            # Número de feedbacks
            cursor.execute("SELECT COUNT(*) FROM feedback_records")
            stats['total_feedbacks'] = cursor.fetchone()[0]

            # Journal mode
            cursor.execute("PRAGMA journal_mode")
            stats['journal_mode'] = cursor.fetchone()[0]

            # Page size
            cursor.execute("PRAGMA page_size")
            stats['page_size'] = cursor.fetchone()[0]

            return stats
    except sqlite3.Error as exc:
        logger.error(f"Falha ao obter estatísticas: {exc}")
        return {}


__all__ = [
    'enable_wal_mode',
    'get_db_connection',
    'create_indexes_if_not_exist',
    'optimize_database',
    'get_database_stats',
]
