"""
services/retraining_api.py

Endpoints FastAPI para sistema de retreino automático.
Fornece API completa para:
- Trigger manual de retreino
- Monitorização de status em tempo real
- Verificação de readiness
- Rollback manual
- Histórico de retreinos
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.db_utils import get_db_connection
from services.model_manager import ModelManager
from services.retraining_scheduler import RetrainingScheduler
from train.ann.incremental_trainer import IncrementalTrainer

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class TriggerRetrainingRequest(BaseModel):
    """Request para disparar retreino."""
    training_type: str = Field("incremental", description="Tipo de retreino")
    min_feedback_quality: float = Field(0.7, ge=0.0, le=1.0, description="Qualidade mínima")
    use_feedback_only: bool = Field(False, description="Usar apenas feedback (sem dataset original)")
    force: bool = Field(False, description="Forçar retreino (ignorar thresholds)")
    notes: Optional[str] = Field(None, description="Notas sobre o retreino")


class RetrainingStatusResponse(BaseModel):
    """Response com status de retreino."""
    run_id: str
    status: str
    progress: float
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    current_loss: Optional[float] = None
    validation_loss: Optional[float] = None
    samples_used: Optional[int] = None
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    message: str


class ReadinessResponse(BaseModel):
    """Response com readiness do sistema."""
    ready: bool
    reason: str
    metrics: Dict


class RetrainingHistoryItem(BaseModel):
    """Item de histórico de retreino."""
    id: int
    started_at: str
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    trigger_type: str
    feedback_count: int
    validation_mae: Optional[float]
    status: str


# ============================================================================
# ESTADO GLOBAL (em memória)
# ============================================================================

# Dicionário de runs ativos: {run_id: {'status': ..., 'progress': ..., ...}}
active_runs: Dict[str, Dict] = {}

# Lock para acesso concorrente
runs_lock = asyncio.Lock()


# ============================================================================
# ROUTER
# ============================================================================

def create_retraining_router(db_path: Path, model_dir: Path) -> APIRouter:
    """
    Cria router FastAPI para endpoints de retreino.

    Args:
        db_path: Path da base de dados
        model_dir: Diretório dos modelos

    Returns:
        APIRouter configurado
    """
    router = APIRouter(prefix="/training", tags=["Retraining"])

    # Inicializar componentes
    scheduler = RetrainingScheduler(db_path)
    model_manager = ModelManager(model_dir)

    # ========================================================================
    # ENDPOINTS
    # ========================================================================

    @router.post("/trigger")
    async def trigger_retraining(request: TriggerRetrainingRequest) -> Dict:
        """
        Dispara um novo retreino (manual ou automático).

        Fluxo:
        1. Verificar se já há retreino em andamento
        2. Validar readiness (se não forçado)
        3. Criar run_id único
        4. Iniciar retreino em background (async)
        5. Retornar run_id para tracking

        **Exemplo:**
        ```json
        {
          "training_type": "incremental",
          "min_feedback_quality": 0.7,
          "use_feedback_only": false,
          "force": false,
          "notes": "Retreino manual após 100 feedbacks"
        }
        ```

        **Returns:**
            Dicionário com run_id e status inicial
        """
        logger.info(f"Trigger de retreino recebido | force={request.force}")

        async with runs_lock:
            # Verificar se já há retreino ativo
            running = [r for r in active_runs.values() if r['status'] == 'running']
            if running:
                raise HTTPException(
                    status_code=409,
                    detail=f"Retreino já em andamento: {running[0]['run_id']}"
                )

            # Verificar readiness (se não forçado)
            if not request.force:
                should_trigger, reason = scheduler.should_trigger_retraining(force=False)

                if not should_trigger:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Sistema não está pronto para retreino: {reason}"
                    )

            # Criar run_id único
            run_id = str(uuid.uuid4())

            # Inicializar estado do run
            active_runs[run_id] = {
                'run_id': run_id,
                'status': 'pending',
                'progress': 0.0,
                'started_at': datetime.now().isoformat(),
                'message': 'Retreino agendado',
                'request': request.dict()
            }

            # Iniciar retreino em background
            asyncio.create_task(
                _execute_retraining_background(
                    run_id=run_id,
                    request=request,
                    db_path=db_path,
                    model_dir=model_dir,
                    scheduler=scheduler,
                    model_manager=model_manager
                )
            )

            logger.info(f"Retreino iniciado | run_id={run_id}")

            return {
                'run_id': run_id,
                'status': 'pending',
                'message': 'Retreino iniciado em background'
            }

    @router.get("/status/{run_id}", response_model=RetrainingStatusResponse)
    async def get_retraining_status(run_id: str) -> RetrainingStatusResponse:
        """
        Retorna status em tempo real de um retreino.

        **Args:**
            run_id: ID do run de retreino

        **Returns:**
            RetrainingStatusResponse com estado atual

        **Exemplo:** GET /training/status/550e8400-e29b-41d4-a716-446655440000
        """
        async with runs_lock:
            if run_id not in active_runs:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run não encontrado: {run_id}"
                )

            run = active_runs[run_id]

            return RetrainingStatusResponse(
                run_id=run['run_id'],
                status=run['status'],
                progress=run['progress'],
                current_epoch=run.get('current_epoch'),
                total_epochs=run.get('total_epochs'),
                current_loss=run.get('current_loss'),
                validation_loss=run.get('validation_loss'),
                samples_used=run.get('samples_used'),
                started_at=run['started_at'],
                estimated_completion=run.get('estimated_completion'),
                message=run['message']
            )

    @router.get("/ready", response_model=ReadinessResponse)
    async def check_readiness() -> ReadinessResponse:
        """
        Verifica se o sistema está pronto para retreino.

        Analisa:
        - Volume de feedback validado
        - Qualidade média do feedback
        - Percentagem de outliers
        - Cooldown period
        - Drift score

        **Returns:**
            ReadinessResponse com estado de readiness e métricas

        **Exemplo:** GET /training/ready
        """
        readiness = scheduler.check_readiness()

        return ReadinessResponse(
            ready=readiness['ready'],
            reason=readiness['reason'],
            metrics=readiness['metrics']
        )

    @router.post("/rollback/{version}")
    async def rollback_model(version: str) -> Dict:
        """
        Faz rollback para uma versão anterior do modelo.

        **Args:**
            version: Nome da versão (ex: "v_backup_2025-11-12_10-30-00")

        **Returns:**
            Dicionário com resultado do rollback

        **Exemplo:** POST /training/rollback/v_backup_2025-11-12_10-30-00
        """
        logger.info(f"Rollback solicitado | version={version}")

        # Verificar se não há retreino ativo
        async with runs_lock:
            running = [r for r in active_runs.values() if r['status'] == 'running']
            if running:
                raise HTTPException(
                    status_code=409,
                    detail="Não é possível fazer rollback durante retreino"
                )

        # Executar rollback
        success = model_manager.rollback_to_version(version)

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Rollback falhou para versão: {version}"
            )

        logger.info(f"Rollback concluído | version={version}")

        return {
            'success': True,
            'version': version,
            'message': f'Rollback concluído para versão {version}'
        }

    @router.get("/history")
    async def get_retraining_history(
        limit: int = 20,
        status_filter: Optional[str] = None
    ) -> Dict:
        """
        Retorna histórico de retreinos.

        **Query Parameters:**
        - `limit`: Número máximo de registos (default: 20)
        - `status_filter`: Filtrar por status ('success', 'failed', 'running')

        **Returns:**
            Lista de retreinos com métricas

        **Exemplo:** GET /training/history?limit=10&status_filter=success
        """
        try:
            with get_db_connection(db_path) as conn:
                cursor = conn.cursor()

                # Query base
                query = """
                    SELECT
                        id,
                        started_at,
                        completed_at,
                        duration_seconds,
                        trigger_type,
                        feedback_count,
                        validation_mae,
                        status
                    FROM retraining_history
                """

                # Adicionar filtro
                params = []
                if status_filter:
                    query += " WHERE status = ?"
                    params.append(status_filter)

                query += " ORDER BY started_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                history = []
                for row in rows:
                    history.append({
                        'id': row['id'],
                        'started_at': row['started_at'],
                        'completed_at': row['completed_at'],
                        'duration_seconds': row['duration_seconds'],
                        'trigger_type': row['trigger_type'],
                        'feedback_count': row['feedback_count'],
                        'validation_mae': row['validation_mae'],
                        'status': row['status']
                    })

                return {
                    'history': history,
                    'count': len(history)
                }

        except sqlite3.Error as e:
            logger.error(f"Erro ao obter histórico: {e}")
            raise HTTPException(
                status_code=500,
                detail="Erro ao consultar histórico"
            )

    @router.get("/stats")
    async def get_retraining_stats() -> Dict:
        """
        Retorna estatísticas completas do sistema de retreino.

        Inclui:
        - Estatísticas de feedback
        - Info do último retreino
        - Readiness status
        - Configuração atual

        **Returns:**
            Dicionário com estatísticas completas

        **Exemplo:** GET /training/stats
        """
        stats = scheduler.get_retraining_stats()

        # Adicionar info de modelos disponíveis
        versions = model_manager.list_available_versions()
        current_version = model_manager.get_current_model_version()

        stats['models'] = {
            'current_version': current_version,
            'available_backups': len(versions),
            'backups': versions[:5]  # Últimos 5
        }

        return stats

    @router.get("/model/info")
    async def get_model_info() -> Dict:
        """
        Retorna informação sobre o modelo em produção.

        **Returns:**
            Dicionário com detalhes do modelo atual

        **Exemplo:** GET /training/model/info
        """
        info = model_manager.get_model_info()
        return info

    @router.get("/model/versions")
    async def list_model_versions() -> Dict:
        """
        Lista todas as versões/backups disponíveis.

        **Returns:**
            Lista de versões com metadados

        **Exemplo:** GET /training/model/versions
        """
        versions = model_manager.list_available_versions()
        return {
            'versions': versions,
            'count': len(versions)
        }

    return router


# ============================================================================
# BACKGROUND TASK
# ============================================================================

async def _execute_retraining_background(
    run_id: str,
    request: TriggerRetrainingRequest,
    db_path: Path,
    model_dir: Path,
    scheduler: RetrainingScheduler,
    model_manager: ModelManager
) -> None:
    """
    Executa retreino em background (async task).

    Args:
        run_id: ID único do run
        request: Request original
        db_path: Path da base de dados
        model_dir: Diretório dos modelos
        scheduler: Scheduler instance
        model_manager: ModelManager instance
    """
    try:
        # Atualizar status: running
        async with runs_lock:
            active_runs[run_id]['status'] = 'running'
            active_runs[run_id]['message'] = 'Retreino em execução...'
            active_runs[run_id]['progress'] = 0.1

        logger.info(f"Retreino iniciado | run_id={run_id}")

        # Criar trainer
        trainer = IncrementalTrainer(db_path=db_path, model_dir=model_dir)

        # Executar retreino (em thread separada para não bloquear)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,  # Usa default executor
            lambda: trainer.train_from_feedback(
                min_feedback_quality=request.min_feedback_quality,
                use_original_data=not request.use_feedback_only,
                original_data_ratio=0.3,
                epochs=30,
                batch_size=64,
                learning_rate=0.0001
            )
        )

        # Verificar sucesso
        if not result['success']:
            raise Exception(result.get('error', 'Retreino falhou'))

        # Deploy do novo modelo
        async with runs_lock:
            active_runs[run_id]['progress'] = 0.9
            active_runs[run_id]['message'] = 'Fazendo deploy do novo modelo...'

        new_onnx = Path(result['onnx_path'])
        new_pth = Path(result['pth_path'])

        deploy_success = model_manager.deploy_new_model(
            new_model_onnx=new_onnx,
            new_model_pth=new_pth,
            backup_first=True,
            validate_before=True
        )

        if not deploy_success:
            raise Exception("Deploy do novo modelo falhou")

        # Atualizar configuração (last_retrain_at)
        scheduler.update_last_retrain()

        # Marcar feedback como usado
        # (implementar em FeedbackManager)

        # Guardar métricas na BD
        _save_retraining_metrics(
            db_path=db_path,
            result=result,
            trigger_type='manual' if request.force else 'threshold',
            notes=request.notes
        )

        # Atualizar status: completed
        async with runs_lock:
            active_runs[run_id]['status'] = 'completed'
            active_runs[run_id]['progress'] = 1.0
            active_runs[run_id]['message'] = 'Retreino concluído com sucesso'
            active_runs[run_id]['validation_loss'] = result['new_loss']
            active_runs[run_id]['samples_used'] = result['total_samples']
            active_runs[run_id]['completed_at'] = datetime.now().isoformat()

        logger.info(f"Retreino concluído com sucesso | run_id={run_id}")

    except Exception as e:
        logger.error(f"Erro durante retreino | run_id={run_id} | error={e}", exc_info=True)

        async with runs_lock:
            active_runs[run_id]['status'] = 'failed'
            active_runs[run_id]['message'] = f'Erro: {str(e)}'
            active_runs[run_id]['completed_at'] = datetime.now().isoformat()


def _save_retraining_metrics(
    db_path: Path,
    result: Dict,
    trigger_type: str,
    notes: Optional[str]
) -> None:
    """
    Guarda métricas de retreino na base de dados.

    Args:
        db_path: Path da base de dados
        result: Resultado do retreino
        trigger_type: Tipo de trigger
        notes: Notas adicionais
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            status = 'success' if result['success'] else 'failed'

            cursor.execute("""
                INSERT INTO retraining_history (
                    started_at,
                    completed_at,
                    duration_seconds,
                    trigger_type,
                    feedback_count,
                    training_samples,
                    train_loss,
                    validation_loss,
                    config_snapshot,
                    model_path,
                    status,
                    error_message,
                    triggered_by,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['started_at'],
                result['completed_at'],
                result['duration_seconds'],
                trigger_type,
                result.get('feedback_count', 0),
                result.get('total_samples', 0),
                result['training_metrics']['final_train_loss'] if result['success'] else None,
                result['training_metrics']['best_val_loss'] if result['success'] else None,
                json.dumps({'epochs': result.get('epochs_trained')}),
                result.get('onnx_path'),
                status,
                result.get('error'),
                'api',
                notes
            ))

            logger.info("Métricas de retreino guardadas na BD")

    except Exception as e:
        logger.error(f"Erro ao guardar métricas: {e}", exc_info=True)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['create_retraining_router', 'active_runs']
