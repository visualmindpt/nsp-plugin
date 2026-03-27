#!/usr/bin/env python3
"""
tools/database_migration.py

Sistema de migrações de base de dados para NSP Plugin.
Aplica migrações SQL de forma idempotente e trackable.
"""

import argparse
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Adicionar path do projeto ao sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.db_utils import get_db_connection, enable_wal_mode

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """
    Gestor de migrações de base de dados.

    Responsabilidades:
    - Criar tabela de tracking de migrações
    - Descobrir migrações disponíveis
    - Aplicar migrações pendentes
    - Registar migrações aplicadas
    - Validar integridade da base de dados

    Atributos:
        db_path: Caminho para a base de dados
        migrations_dir: Diretório com scripts SQL de migração
    """

    def __init__(
        self,
        db_path: Path,
        migrations_dir: Optional[Path] = None
    ):
        """
        Inicializa o gestor de migrações.

        Args:
            db_path: Caminho para o ficheiro da base de dados
            migrations_dir: Diretório com scripts SQL (default: PROJECT_ROOT/migrations)
        """
        self.db_path = Path(db_path)
        self.migrations_dir = migrations_dir or PROJECT_ROOT / "migrations"

        # Verificar se paths existem
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Diretório da base de dados criado: {self.db_path.parent}")

        if not self.migrations_dir.exists():
            self.migrations_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Diretório de migrações criado: {self.migrations_dir}")

        # Ativar WAL mode
        self._ensure_wal_mode()

        # Criar tabela de tracking
        self._ensure_migrations_table()

        logger.info(
            f"DatabaseMigration inicializado | "
            f"db={self.db_path} | "
            f"migrations_dir={self.migrations_dir}"
        )

    def _ensure_wal_mode(self) -> None:
        """Garante que WAL mode está ativo."""
        try:
            enable_wal_mode(self.db_path)
        except Exception as e:
            logger.warning(f"Não foi possível ativar WAL mode: {e}")

    def _ensure_migrations_table(self) -> None:
        """
        Cria tabela de tracking de migrações se não existir.

        A tabela 'schema_migrations' guarda histórico de migrações aplicadas.
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        migration_name TEXT NOT NULL UNIQUE,
                        applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        execution_time_seconds REAL,
                        status TEXT NOT NULL DEFAULT 'success',
                        error_message TEXT,
                        checksum TEXT,
                        CHECK (status IN ('success', 'failed', 'pending'))
                    )
                """)

                # Criar índice para queries rápidas
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_schema_migrations_name
                    ON schema_migrations(migration_name)
                """)

                logger.debug("Tabela schema_migrations garantida")

        except sqlite3.Error as e:
            logger.error(f"Erro ao criar tabela de migrações: {e}")
            raise

    # ========================================================================
    # DESCOBERTA DE MIGRAÇÕES
    # ========================================================================

    def discover_migrations(self) -> List[Tuple[str, Path]]:
        """
        Descobre todos os scripts SQL no diretório de migrações.

        Migrações devem seguir o padrão: NNN_description.sql
        Ex: 001_feedback_granular.sql, 002_add_indexes.sql

        Returns:
            Lista de tuplas (migration_name, file_path) ordenadas por número
        """
        migrations = []

        if not self.migrations_dir.exists():
            logger.warning(f"Diretório de migrações não existe: {self.migrations_dir}")
            return migrations

        # Procurar todos os ficheiros .sql
        for sql_file in sorted(self.migrations_dir.glob("*.sql")):
            migration_name = sql_file.stem  # Nome sem extensão
            migrations.append((migration_name, sql_file))

        logger.info(f"Migrações descobertas: {len(migrations)}")
        for name, path in migrations:
            logger.debug(f"  - {name} ({path})")

        return migrations

    def get_applied_migrations(self) -> List[str]:
        """
        Obtém lista de migrações já aplicadas.

        Returns:
            Lista de nomes de migrações aplicadas com sucesso
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT migration_name
                    FROM schema_migrations
                    WHERE status = 'success'
                    ORDER BY applied_at
                """)

                rows = cursor.fetchall()
                applied = [row['migration_name'] for row in rows]

                logger.debug(f"Migrações aplicadas: {len(applied)}")
                return applied

        except sqlite3.Error as e:
            logger.error(f"Erro ao obter migrações aplicadas: {e}")
            return []

    def get_pending_migrations(self) -> List[Tuple[str, Path]]:
        """
        Obtém lista de migrações pendentes (ainda não aplicadas).

        Returns:
            Lista de tuplas (migration_name, file_path) para migrações pendentes
        """
        all_migrations = self.discover_migrations()
        applied_migrations = set(self.get_applied_migrations())

        pending = [
            (name, path)
            for name, path in all_migrations
            if name not in applied_migrations
        ]

        logger.info(f"Migrações pendentes: {len(pending)}")
        for name, _ in pending:
            logger.debug(f"  - {name}")

        return pending

    # ========================================================================
    # APLICAÇÃO DE MIGRAÇÕES
    # ========================================================================

    def apply_migration(
        self,
        migration_name: str,
        migration_file: Path
    ) -> bool:
        """
        Aplica uma migração individual.

        Args:
            migration_name: Nome da migração
            migration_file: Caminho para o ficheiro SQL

        Returns:
            True se sucesso, False se falhou
        """
        logger.info(f"A aplicar migração: {migration_name}")

        start_time = datetime.now()

        try:
            # Ler conteúdo do ficheiro SQL
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # Calcular checksum para validação futura
            import hashlib
            checksum = hashlib.md5(sql_content.encode()).hexdigest()

            # Aplicar migração
            with get_db_connection(self.db_path, timeout=60.0) as conn:
                cursor = conn.cursor()

                # Executar SQL (pode conter múltiplos statements)
                cursor.executescript(sql_content)

                # Registar migração como aplicada
                execution_time = (datetime.now() - start_time).total_seconds()

                cursor.execute("""
                    INSERT INTO schema_migrations (
                        migration_name,
                        applied_at,
                        execution_time_seconds,
                        status,
                        checksum
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    migration_name,
                    datetime.now(),
                    execution_time,
                    'success',
                    checksum
                ))

                logger.info(
                    f"Migração aplicada com sucesso: {migration_name} "
                    f"({execution_time:.2f}s)"
                )

                return True

        except sqlite3.Error as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Erro ao aplicar migração {migration_name}: {e}")

            # Registar falha
            try:
                with get_db_connection(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO schema_migrations (
                            migration_name,
                            applied_at,
                            execution_time_seconds,
                            status,
                            error_message
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        migration_name,
                        datetime.now(),
                        execution_time,
                        'failed',
                        str(e)
                    ))
            except Exception as inner_e:
                logger.error(f"Erro ao registar falha: {inner_e}")

            return False

        except Exception as e:
            logger.error(f"Erro inesperado ao aplicar migração {migration_name}: {e}")
            return False

    def apply_all_pending(self) -> Tuple[int, int]:
        """
        Aplica todas as migrações pendentes.

        Returns:
            Tupla (num_sucesso, num_falhas)
        """
        pending = self.get_pending_migrations()

        if not pending:
            logger.info("Nenhuma migração pendente")
            return (0, 0)

        logger.info(f"A aplicar {len(pending)} migrações pendentes...")

        num_success = 0
        num_failed = 0

        for migration_name, migration_file in pending:
            success = self.apply_migration(migration_name, migration_file)

            if success:
                num_success += 1
            else:
                num_failed += 1
                logger.error(f"Migração falhou: {migration_name}")

                # Parar em caso de erro
                logger.error("A parar aplicação de migrações devido a erro")
                break

        logger.info(
            f"Migrações aplicadas: {num_success} sucesso, {num_failed} falhas"
        )

        return (num_success, num_failed)

    # ========================================================================
    # VALIDAÇÃO E INFORMAÇÃO
    # ========================================================================

    def get_migration_status(self) -> dict:
        """
        Obtém status completo das migrações.

        Returns:
            Dicionário com informação de status
        """
        all_migrations = self.discover_migrations()
        applied_migrations = self.get_applied_migrations()
        pending_migrations = self.get_pending_migrations()

        status = {
            'total_migrations': len(all_migrations),
            'applied_count': len(applied_migrations),
            'pending_count': len(pending_migrations),
            'applied_list': applied_migrations,
            'pending_list': [name for name, _ in pending_migrations],
            'database_path': str(self.db_path),
            'migrations_directory': str(self.migrations_dir)
        }

        return status

    def print_status(self) -> None:
        """Imprime status das migrações de forma formatada."""
        status = self.get_migration_status()

        print("\n" + "="*70)
        print("DATABASE MIGRATION STATUS")
        print("="*70)
        print(f"Database: {status['database_path']}")
        print(f"Migrations Directory: {status['migrations_directory']}")
        print("-"*70)
        print(f"Total Migrations: {status['total_migrations']}")
        print(f"Applied: {status['applied_count']}")
        print(f"Pending: {status['pending_count']}")
        print("-"*70)

        if status['applied_list']:
            print("\nApplied Migrations:")
            for name in status['applied_list']:
                print(f"  ✓ {name}")

        if status['pending_list']:
            print("\nPending Migrations:")
            for name in status['pending_list']:
                print(f"  ⦿ {name}")
        else:
            print("\n✓ All migrations are up to date!")

        print("="*70 + "\n")

    def validate_database(self) -> bool:
        """
        Valida integridade da base de dados.

        Returns:
            True se base de dados está válida
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                # Verificar integridade
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()

                if result and result[0] == 'ok':
                    logger.info("Integridade da base de dados: OK")
                    return True
                else:
                    logger.error(f"Problemas de integridade: {result}")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Erro ao validar base de dados: {e}")
            return False


# ============================================================================
# CLI
# ============================================================================


def main():
    """Função principal do CLI."""
    parser = argparse.ArgumentParser(
        description="NSP Plugin - Database Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Ver status das migrações
  python tools/database_migration.py --status

  # Aplicar todas as migrações pendentes
  python tools/database_migration.py --apply

  # Aplicar uma migração específica
  python tools/database_migration.py --apply --migration 001_feedback_granular

  # Validar integridade da base de dados
  python tools/database_migration.py --validate

  # Usar base de dados custom
  python tools/database_migration.py --db /path/to/custom.db --status
        """
    )

    parser.add_argument(
        '--db',
        type=Path,
        default=PROJECT_ROOT / 'data' / 'nsp_plugin.db',
        help='Caminho para a base de dados (default: data/nsp_plugin.db)'
    )

    parser.add_argument(
        '--migrations-dir',
        type=Path,
        default=PROJECT_ROOT / 'migrations',
        help='Diretório de migrações (default: migrations/)'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Mostrar status das migrações'
    )

    parser.add_argument(
        '--apply',
        action='store_true',
        help='Aplicar migrações pendentes'
    )

    parser.add_argument(
        '--migration',
        type=str,
        help='Nome da migração específica a aplicar'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validar integridade da base de dados'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Logging verbose (DEBUG level)'
    )

    args = parser.parse_args()

    # Configurar logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Criar gestor de migrações
    migrator = DatabaseMigration(
        db_path=args.db,
        migrations_dir=args.migrations_dir
    )

    # Executar comandos
    if args.status:
        migrator.print_status()

    elif args.apply:
        if args.migration:
            # Aplicar migração específica
            migration_file = migrator.migrations_dir / f"{args.migration}.sql"
            if not migration_file.exists():
                logger.error(f"Migração não encontrada: {migration_file}")
                sys.exit(1)

            success = migrator.apply_migration(args.migration, migration_file)
            sys.exit(0 if success else 1)
        else:
            # Aplicar todas pendentes
            num_success, num_failed = migrator.apply_all_pending()
            sys.exit(0 if num_failed == 0 else 1)

    elif args.validate:
        valid = migrator.validate_database()
        sys.exit(0 if valid else 1)

    else:
        # Default: mostrar status
        migrator.print_status()


if __name__ == '__main__':
    main()
