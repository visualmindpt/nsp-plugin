"""
control-center-v2/backend/dashboard_api.py

Endpoints da API para o NSP Control Center V2
Fornecem dados para o dashboard web: métricas, logs, configurações, etc.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import json
import psutil
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Configurar logger
logger = logging.getLogger(__name__)

# Router para os endpoints do dashboard
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard V2"])

# ============================================================================
# MODELS
# ============================================================================

class ServerStatus(BaseModel):
    status: str  # "online" | "offline"
    uptime_seconds: float
    memory_mb: float
    cpu_percent: float
    timestamp: str

class PredictionMetrics(BaseModel):
    total_today: int
    total_week: int
    total_month: int
    average_time_ms: float
    success_rate: float
    confidence_average: float
    preset_distribution: Dict[str, int]

class TrainingStatus(BaseModel):
    is_training: bool
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    current_loss: Optional[float] = None
    progress_percent: Optional[float] = None
    eta_seconds: Optional[int] = None

class FeedbackStats(BaseModel):
    total_feedbacks: int
    positive_count: int
    negative_count: int
    average_correction: float
    most_corrected_preset: str
    most_corrected_slider: str

class Settings(BaseModel):
    server_url: str
    server_port: int
    num_presets: int
    min_rating: int
    classifier_epochs: int
    refiner_epochs: int
    batch_size: int
    patience: int
    confidence_threshold: float
    active_learning_enabled: bool

# ============================================================================
# ESTADO GLOBAL (em produção, usar Redis ou DB)
# ============================================================================

class DashboardState:
    """Estado global do dashboard (simplified for MVP)"""
    def __init__(self):
        self.server_start_time = datetime.now()
        self.predictions_today = []
        self.predictions_week = []
        self.training_status = TrainingStatus(is_training=False)
        self.settings = Settings(
            server_url="http://127.0.0.1",
            server_port=5000,
            num_presets=4,
            min_rating=3,
            classifier_epochs=50,
            refiner_epochs=100,
            batch_size=32,
            patience=7,
            confidence_threshold=0.5,
            active_learning_enabled=False
        )

# Estado global
dashboard_state = DashboardState()

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/status", response_model=ServerStatus)
async def get_server_status():
    """
    Retorna o estado atual do servidor
    """
    try:
        # Obter métricas do sistema
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)

        # Calcular uptime
        uptime = (datetime.now() - dashboard_state.server_start_time).total_seconds()

        return ServerStatus(
            status="online",
            uptime_seconds=uptime,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Erro ao obter status do servidor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=PredictionMetrics)
async def get_prediction_metrics():
    """
    Retorna métricas de predições
    """
    try:
        # Filtrar predições de hoje, semana e mês
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        predictions_today = [p for p in dashboard_state.predictions_today if p['timestamp'] >= today_start]
        predictions_week = [p for p in dashboard_state.predictions_week if p['timestamp'] >= week_start]

        # Calcular métricas
        total_today = len(predictions_today)
        total_week = len(predictions_week)

        # Tempo médio
        if predictions_today:
            avg_time = sum(p.get('time_ms', 0) for p in predictions_today) / len(predictions_today)
        else:
            avg_time = 0.0

        # Taxa de sucesso
        if predictions_today:
            success_count = sum(1 for p in predictions_today if p.get('success', False))
            success_rate = success_count / len(predictions_today)
        else:
            success_rate = 0.0

        # Confiança média
        if predictions_today:
            confidences = [p.get('confidence', 0) for p in predictions_today if 'confidence' in p]
            confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
        else:
            confidence_avg = 0.0

        # Distribuição de presets
        preset_dist = {}
        for p in predictions_today:
            preset_id = p.get('preset_id')
            if preset_id is not None:
                preset_name = f"Preset {preset_id}"
                preset_dist[preset_name] = preset_dist.get(preset_name, 0) + 1

        return PredictionMetrics(
            total_today=total_today,
            total_week=total_week,
            total_month=len(dashboard_state.predictions_week),  # Placeholder
            average_time_ms=avg_time,
            success_rate=success_rate,
            confidence_average=confidence_avg,
            preset_distribution=preset_dist
        )
    except Exception as e:
        logger.error(f"Erro ao obter métricas de predição: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/status", response_model=TrainingStatus)
async def get_training_status():
    """
    Retorna o estado atual do treino
    """
    return dashboard_state.training_status


@router.post("/training/start")
async def start_training(
    num_presets: int = 4,
    min_rating: int = 3,
    epochs_classifier: int = 50,
    epochs_refiner: int = 100
):
    """
    Inicia um novo treino (placeholder - integrar com train/train_models_v2.py)
    """
    if dashboard_state.training_status.is_training:
        raise HTTPException(status_code=400, detail="Treino já em execução")

    # TODO: Integrar com train/train_models_v2.py
    dashboard_state.training_status = TrainingStatus(
        is_training=True,
        current_epoch=0,
        total_epochs=epochs_classifier + epochs_refiner,
        current_loss=None,
        progress_percent=0.0,
        eta_seconds=None
    )

    return {"message": "Treino iniciado com sucesso", "status": "started"}


@router.post("/training/stop")
async def stop_training():
    """
    Para o treino atual (placeholder)
    """
    if not dashboard_state.training_status.is_training:
        raise HTTPException(status_code=400, detail="Nenhum treino em execução")

    dashboard_state.training_status = TrainingStatus(is_training=False)
    return {"message": "Treino parado com sucesso", "status": "stopped"}


@router.get("/feedback/stats", response_model=FeedbackStats)
async def get_feedback_stats():
    """
    Retorna estatísticas de feedback
    """
    # TODO: Integrar com FeedbackManager
    return FeedbackStats(
        total_feedbacks=0,
        positive_count=0,
        negative_count=0,
        average_correction=0.0,
        most_corrected_preset="N/A",
        most_corrected_slider="N/A"
    )


@router.get("/settings", response_model=Settings)
async def get_settings():
    """
    Retorna as configurações atuais
    """
    return dashboard_state.settings


@router.put("/settings")
async def update_settings(settings: Settings):
    """
    Atualiza as configurações
    """
    dashboard_state.settings = settings
    return {"message": "Configurações atualizadas com sucesso", "settings": settings}


@router.get("/logs/recent")
async def get_recent_logs(limit: int = 100):
    """
    Retorna os logs mais recentes
    """
    # TODO: Integrar com sistema de logging real
    return {
        "logs": [
            {"level": "INFO", "message": "Servidor iniciado", "timestamp": datetime.now().isoformat()},
            {"level": "INFO", "message": "Dashboard V2 carregado", "timestamp": datetime.now().isoformat()},
        ]
    }


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket para streaming de logs em tempo real
    """
    await websocket.accept()
    try:
        while True:
            # TODO: Implementar streaming real de logs
            # Por agora, enviar logs de exemplo
            import asyncio
            await asyncio.sleep(2)

            log_entry = {
                "level": "INFO",
                "message": f"Log de teste - {datetime.now().isoformat()}",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(log_entry)
    except WebSocketDisconnect:
        logger.info("WebSocket desconectado")


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def record_prediction(
    preset_id: Optional[int],
    confidence: float,
    time_ms: float,
    success: bool
):
    """
    Regista uma predição no estado do dashboard
    (Chamar esta função após cada predição no endpoint /predict)
    """
    prediction_data = {
        'preset_id': preset_id,
        'confidence': confidence,
        'time_ms': time_ms,
        'success': success,
        'timestamp': datetime.now()
    }

    dashboard_state.predictions_today.append(prediction_data)
    dashboard_state.predictions_week.append(prediction_data)

    # Limpar dados antigos (manter apenas últimos 7 dias)
    week_ago = datetime.now() - timedelta(days=7)
    dashboard_state.predictions_week = [
        p for p in dashboard_state.predictions_week
        if p['timestamp'] >= week_ago
    ]

    # Limitar tamanho (manter no máximo 10000 registos)
    if len(dashboard_state.predictions_week) > 10000:
        dashboard_state.predictions_week = dashboard_state.predictions_week[-10000:]


def update_training_progress(epoch: int, total_epochs: int, loss: float):
    """
    Atualiza o progresso do treino
    (Chamar durante o treino para atualizar o estado)
    """
    progress = (epoch / total_epochs) * 100
    dashboard_state.training_status = TrainingStatus(
        is_training=True,
        current_epoch=epoch,
        total_epochs=total_epochs,
        current_loss=loss,
        progress_percent=progress,
        eta_seconds=None  # TODO: Calcular ETA
    )
