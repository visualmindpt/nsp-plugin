"""
services/server.py

Servidor FastAPI unificado para o NSP Plugin V2.
Focado exclusivamente na nova arquitetura de Classificador + Refinador.
"""
from __future__ import annotations

# Adicionado para permitir execução direta e via uvicorn
import sys
from pathlib import Path

# Garante que a raiz do projeto está no sys.path
# Permite que 'from services...' funcione em qualquer contexto de execução
APP_ROOT_FIX = Path(__file__).resolve().parent.parent
if str(APP_ROOT_FIX) not in sys.path:
    sys.path.insert(0, str(APP_ROOT_FIX))

import atexit
import base64
import binascii
import json
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Body, WebSocket, WebSocketDisconnect
from typing import Annotated
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import threading
import asyncio
from typing import List as ListType

# Imports da arquitetura V2
from services.ai_core.predictor import LightroomAIPredictor
from services.ai_core.feedback_collector import FeedbackCollector
from services.ai_core.active_learning_retrainer import ActiveLearningRetrainer
from services.ai_core.xmp_generator import XMPGenerator
from services.ai_core.auto_straighten import detect_horizon_angle
from services.db_utils import enable_wal_mode, create_indexes_if_not_exist
from services.alert_manager import get_alert_manager, alert_monitoring_task, AlertType, AlertLevel

# Config Loader (Sistema centralizado de configuração)
from config_loader import config
from services.monitoring import get_monitoring_collector
from services.batch_processor import get_batch_processor, JobStatus

# ============================================================================
# Pydantic Models
# ============================================================================

class ImagePayload(BaseModel):
    image_path: Optional[str] = Field(None, description="Caminho para a imagem (RAW/JPEG).")
    preview_b64: Optional[str] = Field(None, description="Preview em base64.")

    @model_validator(mode="after")
    def validate_source(cls, values: "ImagePayload") -> "ImagePayload":
        if not values.image_path and not values.preview_b64:
            raise ValueError("Define 'image_path' ou 'preview_b64'.")
        return values

class PredictRequest(ImagePayload):
    exif: Dict[str, Any] = Field(default_factory=dict, description="Metadados EXIF (iso, aperture, shutter, focal, make, model, etc).")
    preset_id: Optional[int] = Field(None, description="ID do preset base aplicado à imagem.")

class PredictResponse(BaseModel):
    model: str
    sliders: Dict[str, float]
    preset_id: int
    preset_confidence: float
    prediction_id: Optional[int] = Field(None, description="ID da predição registada na BD (para feedback)")

class FeedbackSubmitRequest(BaseModel):
    prediction_id: Optional[int] = Field(None, description="ID da predição a que o feedback se refere. Opcional por agora (placeholder=0 aceite).")
    rating: int = Field(..., ge=1, le=5, description="Rating do utilizador (1-5).")
    user_params: Optional[Dict[str, float]] = Field(None, description="Parâmetros finais se o utilizador editou.")
    notes: Optional[str] = Field(None, description="Notas adicionais do utilizador.")
    feedback_type: str = Field(default="explicit", description="Tipo de feedback: explicit, implicit, bug_report, etc.")
    tags: List[str] = Field(default_factory=list, description="Etiquetas rápidas selecionadas pelo utilizador.")
    issues: List[str] = Field(default_factory=list, description="Lista de issues selecionadas no prompt.")
    feedback_context: Optional[Dict[str, object]] = Field(default=None, description="Contexto adicional enviado pelo plugin (razão do prompt, metadados, etc.).")
    seconds_to_submit: Optional[float] = Field(default=None, description="Tempo (segundos) que o utilizador demorou a submeter o feedback.")

class FeedbackSubmitResponse(BaseModel):
    success: bool
    message: str
    event_id: Optional[int] = Field(None, description="ID do evento de feedback registado.")

class RetrainRequest(BaseModel):
    min_samples: int = Field(50, description="Número mínimo de amostras para iniciar o re-treino.")
    epochs: int = Field(20, description="Número de epochs para o re-treino.")
    batch_size: int = Field(16, description="Tamanho do batch para o re-treino.")

class RetrainResponse(BaseModel):
    success: bool
    message: str
    samples_collected: Optional[int] = None

class GenerateXMPRequest(BaseModel):
    image_path: str = Field(..., description="Caminho da imagem para gerar o XMP.")
    parameters: Dict[str, float] = Field(..., description="Parâmetros de edição a aplicar.")

class GenerateXMPResponse(BaseModel):
    success: bool
    message: str
    xmp_path: Optional[str] = None

class FeedbackStatsResponse(BaseModel):
    total_predictions: int
    predictions_with_feedback: int
    average_rating: float
    preset_distribution: Dict[int, int]
    feedback_rate: float

class AutoStraightenRequest(BaseModel):
    image_path: str = Field(..., description="Caminho para a imagem a analisar.")
    min_line_length: int = Field(200, description="Comprimento mínimo de linha para detectar.")
    angle_threshold: float = Field(45.0, description="Ângulo máximo para considerar linha horizontal.")

AutoStraightenRequest.model_rebuild()
AutoStraightenPayload = Annotated[AutoStraightenRequest, Body(...)]

class AutoStraightenResponse(BaseModel):
    angle: float = Field(..., description="Ângulo de rotação necessário em graus.")
    confidence: float = Field(..., description="Confiança da detecção (0-1).")
    requires_correction: bool = Field(..., description="Se precisa correção (|angle| > 0.5°).")
    num_lines_detected: int = Field(..., description="Número de linhas horizontais detectadas.")
    recommendation: str = Field(..., description="Recomendação: 'rotate', 'none', ou 'manual_check'.")

class BatchPredictRequest(BaseModel):
    """Request para predição em batch (múltiplas imagens)"""
    images: List[ImagePayload] = Field(..., description="Lista de imagens a processar")
    exif_list: Optional[List[Dict[str, Any]]] = Field(None, description="Lista de EXIF correspondente (opcional)")

class BatchPredictResponse(BaseModel):
    """Response de predição em batch"""
    predictions: List[PredictResponse] = Field(..., description="Lista de predições")
    total_processed: int = Field(..., description="Total de imagens processadas")
    total_failed: int = Field(..., description="Total de imagens com erro")
    processing_time_ms: float = Field(..., description="Tempo total de processamento em ms")
    avg_time_per_image_ms: float = Field(..., description="Tempo médio por imagem em ms")

# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """
    Gestor de conexões WebSocket para updates em tempo real

    Ganhos:
    - Updates instantâneos (0ms latência vs. 2-5s polling)
    - -90% de requests HTTP
    - Dashboard muito mais responsivo
    - Gráficos atualizam em tempo real
    """

    def __init__(self):
        self.active_connections: ListType[WebSocket] = []
        self._lock = threading.Lock()

    async def connect(self, websocket: WebSocket):
        """Aceita nova conexão WebSocket"""
        await websocket.accept()
        with self._lock:
            self.active_connections.append(websocket)
        logging.info(f"WebSocket conectado. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove conexão WebSocket"""
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logging.info(f"WebSocket desconectado. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        Envia mensagem para todos os clientes conectados

        Args:
            message: Dict com tipo e dados da mensagem
        """
        if not self.active_connections:
            return

        disconnected = []
        with self._lock:
            connections = self.active_connections.copy()

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.warning(f"Erro ao enviar WebSocket: {e}")
                disconnected.append(connection)

        # Remover conexões falhadas
        if disconnected:
            with self._lock:
                for conn in disconnected:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)

    async def send_to_client(self, websocket: WebSocket, message: dict):
        """
        Envia mensagem para cliente específico

        Args:
            websocket: Cliente específico
            message: Mensagem a enviar
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logging.error(f"Erro ao enviar para cliente: {e}")
            self.disconnect(websocket)

# Instância global do manager
ws_manager = ConnectionManager()

# ============================================================================
# Application Setup
# ============================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"
DB_PATH = DATA_DIR / "feedback.db" # DB dedicada para o feedback V2
MODELS_DIR = APP_ROOT / "models"
TEMP_DIR = APP_ROOT / "tmp" / "previews"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Import do Dashboard API V2
try:
    sys.path.insert(0, str(APP_ROOT / "control-center-v2" / "backend"))
    from dashboard_api import router as dashboard_router
    DASHBOARD_AVAILABLE = True
except ImportError as exc:
    logging.warning(f"Dashboard API V2 não disponível: {exc}")
    DASHBOARD_AVAILABLE = False
    dashboard_router = None

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.arw', '.cr2', '.nef', '.dng', '.orf', '.raw', '.rw2'}
ALLOWED_BASE_PATHS = [Path("/Users"), Path("/Volumes"), Path.home()]

app = FastAPI(title="NSP Plugin V2 Inference API", version="2.2.0")

# Montar ficheiros estáticos do Dashboard V2
STATIC_DIR = APP_ROOT / "control-center-v2" / "static"
if STATIC_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(STATIC_DIR), html=True), name="dashboard")
    logging.info("Dashboard V2 static files mounted at /dashboard")

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Globals para os componentes V2
AI_PREDICTOR: Optional[LightroomAIPredictor] = None
FEEDBACK_COLLECTOR: Optional[FeedbackCollector] = None
XMP_GENERATOR: Optional[XMPGenerator] = None
ALERT_MANAGER = None  # AlertManager para alertas automáticos
MONITORING_COLLECTOR = None  # MonitoringCollector para métricas avançadas

# ============================================================================
# Helper Functions
# ============================================================================

def cleanup_old_temp_files() -> None:
    try:
        cutoff = datetime.now() - timedelta(hours=1)
        for file_path in TEMP_DIR.glob("*"):
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff:
                    file_path.unlink(missing_ok=True)
    except Exception as exc:
        logging.error("Error during temp file cleanup: %s", exc)

atexit.register(cleanup_old_temp_files)

def _validate_image_path(image_path: Path) -> bool:
    try:
        resolved = image_path.resolve(strict=False)
        if resolved.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS: return False
        if ".." in image_path.parts: return False
        if not any(str(resolved).startswith(str(p)) for p in ALLOWED_BASE_PATHS): return False
        if not resolved.exists() or resolved.is_dir(): return False
        return True
    except (OSError, RuntimeError):
        return False

def _materialize_input(image_path_str: Optional[str], preview_b64: Optional[str]) -> Tuple[Path, Optional[Path]]:
    if image_path_str:
        image_path_obj = Path(image_path_str)
        if not _validate_image_path(image_path_obj):
            raise HTTPException(status_code=400, detail=f"Caminho de imagem inválido: {image_path_str}")
        return image_path_obj, None
    
    try:
        raw_bytes = base64.b64decode(preview_b64 or "", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"preview_b64 inválido: {exc}") from exc

    if len(raw_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="preview_b64 excede 50MB")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    tmp_path = TEMP_DIR / f"preview_{timestamp}.png"
    try:
        with open(tmp_path, 'wb') as f:
            f.write(raw_bytes)
        return tmp_path, tmp_path
    except IOError as exc:
        raise HTTPException(status_code=500, detail="Falha ao criar ficheiro temporário") from exc

# ============================================================================
# FastAPI Events and Routes
# ============================================================================

@app.on_event("startup")
def startup_event() -> None:
    global AI_PREDICTOR, FEEDBACK_COLLECTOR, XMP_GENERATOR, ALERT_MANAGER, MONITORING_COLLECTOR

    if DB_PATH.exists():
        try:
            enable_wal_mode(DB_PATH)
        except Exception as exc:
            logging.error(f"Falha ao configurar SQLite: {exc}")

    try:
        FEEDBACK_COLLECTOR = FeedbackCollector(feedback_db_path=DB_PATH)
        logging.info("FeedbackCollector (V2) inicializado com sucesso.")
    except Exception as exc:
        logging.error(f"Falha ao inicializar FeedbackCollector (V2): {exc}")

    try:
        XMP_GENERATOR = XMPGenerator()
        logging.info("XMPGenerator (V2) inicializado com sucesso.")
    except Exception as exc:
        logging.error(f"Falha ao inicializar XMPGenerator (V2): {exc}")

    # Carregar paths dos modelos a partir do config.json
    try:
        classifier_path = config.get_model_path('classifier')
        refinement_path = config.get_model_path('refiner')
        scaler_stat_path = MODELS_DIR / "scaler_stat.pkl"
        scaler_deep_path = MODELS_DIR / "scaler_deep.pkl"
        scaler_deltas_path = MODELS_DIR / "scaler_deltas.pkl"
        preset_centers_path = MODELS_DIR / "preset_centers.json"
        delta_columns_path = MODELS_DIR / "delta_columns.json"

        model_files = [
            classifier_path, refinement_path, scaler_stat_path, scaler_deep_path,
            scaler_deltas_path, preset_centers_path, delta_columns_path
        ]

        if all(Path(p).exists() for p in model_files):
            try:
                AI_PREDICTOR = LightroomAIPredictor(
                    classifier_path=str(classifier_path),
                    refinement_path=str(refinement_path),
                    preset_centers=str(preset_centers_path),
                    scaler_stat=str(scaler_stat_path),
                    scaler_deep=str(scaler_deep_path),
                    scaler_deltas=str(scaler_deltas_path),
                    delta_columns=str(delta_columns_path)
                )
                logging.info(f"✅ AI_PREDICTOR (V2) inicializado com sucesso.")
                logging.info(f"   Classifier: {config.get('models.classifier')}")
                logging.info(f"   Refiner: {config.get('models.refiner')}")
                logging.info(f"   Model Version: {config.get('models.version', 'unknown')}")
            except Exception as exc:
                logging.error(f"❌ Falha ao inicializar AI_PREDICTOR (V2): {exc}", exc_info=True)
                AI_PREDICTOR = None
        else:
            missing_files = [str(p) for p in model_files if not Path(p).exists()]
            logging.warning(f"⚠️ Ficheiros do modelo AI (V2) em falta. AI_PREDICTOR não será inicializado.")
            logging.warning(f"   Ficheiros em falta: {missing_files}")
            AI_PREDICTOR = None
    except Exception as exc:
        logging.error(f"❌ Erro ao carregar configuração de modelos: {exc}", exc_info=True)
        AI_PREDICTOR = None

    if DASHBOARD_AVAILABLE and dashboard_router:
        try:
            app.include_router(dashboard_router)
            logging.info("Dashboard API V2 registado com sucesso")
        except Exception as exc:
            logging.error(f"Falha ao registar Dashboard API V2: {exc}")

    # Inicializar PresetManager
    try:
        from services.preset_manager import PresetManager, ensure_default_preset_exists
        global PRESET_MANAGER
        # PresetManager usa presets_dir, não models_dir
        PRESET_MANAGER = PresetManager(presets_dir=APP_ROOT / "presets")

        # Garantir que preset default existe
        ensure_default_preset_exists(models_dir=APP_ROOT)

        logging.info("PresetManager inicializado com sucesso.")
    except Exception as exc:
        logging.error(f"Falha ao inicializar PresetManager: {exc}", exc_info=True)
        PRESET_MANAGER = None

    # Inicializar AlertManager e registar WebSocket manager
    try:
        ALERT_MANAGER = get_alert_manager()
        ALERT_MANAGER.set_websocket_manager(ws_manager)
        logging.info("AlertManager inicializado com sucesso.")

        # Iniciar background task de monitorização
        asyncio.create_task(alert_monitoring_task(interval_seconds=60))
        logging.info("Alert monitoring task iniciada (intervalo: 60s)")
    except Exception as exc:
        logging.error(f"Falha ao inicializar AlertManager: {exc}", exc_info=True)
        ALERT_MANAGER = None

    # Inicializar MonitoringCollector
    try:
        MONITORING_COLLECTOR = get_monitoring_collector()
        logging.info("MonitoringCollector inicializado com sucesso.")
    except Exception as exc:
        logging.error(f"Falha ao inicializar MonitoringCollector: {exc}", exc_info=True)
        MONITORING_COLLECTOR = None

    cleanup_old_temp_files()

@app.get("/health")
def healthcheck() -> Dict[str, object]:
    return {
        "status": "ok",
        "v2_predictor_loaded": AI_PREDICTOR is not None,
    }

@app.get("/version")
def get_version() -> Dict[str, Any]:
    """
    Retorna informações de versão do servidor e modelos

    Permite ao plugin validar compatibilidade antes de fazer predições
    """
    return {
        "server_version": "2.0.0",
        "api_version": "v2",
        "models": {
            "classifier": {
                "name": config.get('models.classifier', 'unknown'),
                "version": config.get('models.version', 'unknown'),
                "loaded": AI_PREDICTOR is not None
            },
            "refiner": {
                "name": config.get('models.refiner', 'unknown'),
                "version": config.get('models.version', 'unknown'),
                "loaded": AI_PREDICTOR is not None
            }
        },
        "features": {
            "feedback_system": True,
            "incremental_training": True,
            "batch_processing": True,
            "culling": True,
            "auto_straighten": True,
            "preset_management": True
        },
        "config": {
            "confidence_threshold": config.get('plugin.confidence_threshold', 0.5),
            "server_url": config.get_server_url()
        }
    }

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """
    WebSocket endpoint para updates em tempo real do dashboard

    Envia:
    - Notificações de novas predições
    - Progresso de treino
    - Alertas do sistema
    - Métricas em tempo real
    """
    await ws_manager.connect(websocket)
    try:
        # Enviar mensagem de boas-vindas
        await ws_manager.send_to_client(websocket, {
            'type': 'connected',
            'message': 'Conectado ao servidor NSP',
            'timestamp': datetime.now().isoformat()
        })

        # Keep-alive loop
        while True:
            try:
                # Receber mensagens do cliente (principalmente para keep-alive)
                data = await websocket.receive_text()
                # Pode processar comandos do cliente aqui se necessário
            except WebSocketDisconnect:
                break
            except Exception as e:
                logging.error(f"Erro no WebSocket loop: {e}")
                break

    except WebSocketDisconnect:
        logging.info("Cliente desconectado")
    finally:
        ws_manager.disconnect(websocket)


@app.post("/predict_batch", response_model=BatchPredictResponse)
@limiter.limit("50/minute")
async def predict_batch(request: Request, payload: BatchPredictRequest) -> BatchPredictResponse:
    """
    Predição em batch (múltiplas imagens)

    Ganhos:
    - 4-6x mais rápido que chamadas individuais
    - Processamento interno otimizado em batches de 8
    - Paralelização quando possível

    Example:
        POST /predict_batch
        {
            "images": [
                {"image_path": "/path/1.jpg"},
                {"image_path": "/path/2.jpg"},
                ...
            ],
            "exif_list": [{...}, {...}, ...]
        }
    """
    import time

    if AI_PREDICTOR is None:
        raise HTTPException(status_code=503, detail="AI_PREDICTOR não está carregado")

    start_time = time.time()
    predictions = []
    failed = 0
    exif_list = payload.exif_list or [{} for _ in payload.images]

    # Garantir que exif_list tem o mesmo tamanho que images
    if len(exif_list) < len(payload.images):
        exif_list.extend([{} for _ in range(len(payload.images) - len(exif_list))])

    logging.info(f"📦 Batch prediction: {len(payload.images)} imagens")

    # Processar em mini-batches de 8 para otimização
    MINI_BATCH_SIZE = 8

    for i in range(0, len(payload.images), MINI_BATCH_SIZE):
        batch_images = payload.images[i:i+MINI_BATCH_SIZE]
        batch_exif = exif_list[i:i+MINI_BATCH_SIZE]

        for img_payload, exif in zip(batch_images, batch_exif):
            try:
                # Materializar imagem
                image_path, tmp_path = _materialize_input(img_payload.image_path, img_payload.preview_b64)

                # Fazer predição
                prediction_result = AI_PREDICTOR.predict(image_path)

                # Guardar predição na BD
                prediction_db_id = None
                if FEEDBACK_COLLECTOR:
                    try:
                        prediction_db_id = FEEDBACK_COLLECTOR.log_prediction(image_path, prediction_result)
                    except Exception as db_exc:
                        logging.warning(f"Erro ao guardar predição: {db_exc}")

                # Adicionar à lista
                predictions.append(PredictResponse(
                    model="V2_AI_Predictor",
                    sliders=prediction_result['final_params'],
                    preset_id=prediction_result['preset_id'],
                    preset_confidence=prediction_result['preset_confidence'],
                    prediction_id=prediction_db_id
                ))

                # Limpar ficheiro temporário
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)

            except Exception as exc:
                logging.error(f"Erro ao processar imagem no batch: {exc}")
                failed += 1

    end_time = time.time()
    processing_time_ms = (end_time - start_time) * 1000
    avg_time_ms = processing_time_ms / len(payload.images) if payload.images else 0

    logging.info(f"✅ Batch completo: {len(predictions)} sucesso, {failed} falhas, {processing_time_ms:.1f}ms total ({avg_time_ms:.1f}ms/img)")

    # Broadcast via WebSocket
    try:
        await ws_manager.broadcast({
            'type': 'batch_prediction',
            'data': {
                'total': len(payload.images),
                'success': len(predictions),
                'failed': failed,
                'avg_time_ms': avg_time_ms,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as broadcast_exc:
        logging.warning(f"Erro ao fazer broadcast: {broadcast_exc}")

    return BatchPredictResponse(
        predictions=predictions,
        total_processed=len(predictions),
        total_failed=failed,
        processing_time_ms=processing_time_ms,
        avg_time_per_image_ms=avg_time_ms
    )


@app.post("/predict", response_model=PredictResponse)
@limiter.limit("10/minute")
async def predict(request: Request) -> PredictResponse:
    try:
        body_json = await request.json()
        payload = PredictRequest.model_validate(body_json)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Corpo do pedido inválido: {exc}")

    if AI_PREDICTOR is None:
        # Gerar alerta de modelo não carregado
        if ALERT_MANAGER:
            await ALERT_MANAGER.create_alert(
                alert_type=AlertType.MODEL_NOT_LOADED,
                level=AlertLevel.ERROR,
                message="AI_PREDICTOR não está carregado. Impossível fazer predições.",
                metadata={"endpoint": "/predict"}
            )
        raise HTTPException(status_code=503, detail="AI_PREDICTOR (V2) não está carregado.")

    image_path, tmp_path = _materialize_input(payload.image_path, payload.preview_b64)
    request_id = uuid4().hex[:8]
    logging.info(
        "👉 [%s] predict | preset_hint=%s | exif=%s | path=%s",
        request_id,
        payload.preset_id,
        payload.exif,
        image_path,
    )

    # Track inference time para alertas
    import time
    inference_start = time.time()

    try:
        prediction_result = AI_PREDICTOR.predict(image_path)

        # Calcular tempo de inferência
        inference_time_ms = (time.time() - inference_start) * 1000

        # Registar no AlertManager
        if ALERT_MANAGER:
            ALERT_MANAGER.track_inference_time(inference_time_ms)

        # Registar no MonitoringCollector
        if MONITORING_COLLECTOR:
            MONITORING_COLLECTOR.record_inference(
                inference_time_ms=inference_time_ms,
                confidence=prediction_result.get('preset_confidence', 0),
                preset_id=prediction_result.get('preset_id', 0)
            )

        # Guardar predição na BD e obter ID
        prediction_db_id = None
        if FEEDBACK_COLLECTOR:
            try:
                prediction_db_id = FEEDBACK_COLLECTOR.log_prediction(image_path, prediction_result)
                logging.info(f"Predição registada na BD com ID: {prediction_db_id}")
            except Exception as db_exc:
                logging.error(f"Erro ao guardar previsão com FeedbackCollector: {db_exc}")

        logging.info(
            "[%s] preset=%s confidence=%.3f | prediction_id=%s",
            request_id,
            prediction_result.get("preset_id"),
            prediction_result.get("preset_confidence"),
            prediction_db_id,
        )

        # Broadcast predição para dashboard via WebSocket
        try:
            await ws_manager.broadcast({
                'type': 'prediction',
                'data': {
                    'preset_id': prediction_result['preset_id'],
                    'confidence': prediction_result['preset_confidence'],
                    'prediction_id': prediction_db_id,
                    'timestamp': datetime.now().isoformat(),
                    'image_path': str(image_path)
                }
            })
        except Exception as broadcast_exc:
            logging.warning(f"Erro ao fazer broadcast da predição: {broadcast_exc}")

        return PredictResponse(
            model="V2_AI_Predictor",
            sliders=prediction_result['final_params'],
            preset_id=prediction_result['preset_id'],
            preset_confidence=prediction_result['preset_confidence'],
            prediction_id=prediction_db_id
        )
    except Exception as exc:
        logging.exception("Erro inesperado no endpoint /predict")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ============================================================================
# BATCH PROCESSING ASSÍNCRONO
# ============================================================================

@app.post("/batch/submit", tags=["Batch"])
@limiter.limit("5/minute")
async def submit_batch_job(request: Request):
    """
    Submete um batch job para processamento assíncrono

    Body: {
        "images": [
            {"image_path": "...", "exif": {...}},
            ...
        ]
    }

    Returns: {"job_id": "uuid", "total_images": N}
    """
    try:
        body = await request.json()
        images = body.get('images', [])

        if not images:
            raise HTTPException(status_code=400, detail="Lista de imagens vazia")

        if len(images) > 1000:
            raise HTTPException(status_code=400, detail="Máximo de 1000 imagens por batch")

        # Obter batch processor
        batch_processor = get_batch_processor(predictor=AI_PREDICTOR)

        # Criar job
        job_id = batch_processor.create_job(images)

        # Iniciar processamento em background
        await batch_processor.start_job(job_id)

        return {
            "job_id": job_id,
            "total_images": len(images),
            "status": "submitted",
            "message": "Batch job submetido. Use /batch/{job_id}/status para monitorar."
        }

    except Exception as exc:
        logging.error(f"Erro ao submeter batch job: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/batch/{job_id}/status", tags=["Batch"])
async def get_batch_job_status(job_id: str):
    """
    Obtém status de um batch job

    Returns: {
        "job_id": "...",
        "status": "pending|running|completed|failed",
        "progress_pct": 45.5,
        "processed_images": 45,
        "total_images": 100,
        "eta_seconds": 120,
        ...
    }
    """
    batch_processor = get_batch_processor()
    job = batch_processor.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} não encontrado")

    return job.to_dict()


@app.get("/batch/{job_id}/results", tags=["Batch"])
async def get_batch_job_results(job_id: str):
    """
    Obtém resultados de um batch job (apenas se completo)

    Returns: {
        "job_id": "...",
        "status": "completed",
        "results": [
            {"image_path": "...", "preset_id": 1, "sliders": {...}},
            ...
        ],
        "successful_images": 95,
        "failed_images": 5,
        "errors": ["..."]
    }
    """
    batch_processor = get_batch_processor()
    job = batch_processor.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} não encontrado")

    if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(
            status_code=400,
            detail=f"Job ainda não concluído (status: {job.status.value})"
        )

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "results": job.results,
        "successful_images": job.successful_images,
        "failed_images": job.failed_images,
        "errors": job.errors,
        "total_time_seconds": (
            (job.completed_at - job.started_at).total_seconds()
            if job.completed_at and job.started_at else None
        )
    }


@app.delete("/batch/{job_id}", tags=["Batch"])
async def cancel_batch_job(job_id: str):
    """
    Cancela um batch job (apenas se ainda não iniciou)

    Returns: {"success": true/false, "message": "..."}
    """
    batch_processor = get_batch_processor()
    cancelled = batch_processor.cancel_job(job_id)

    if cancelled:
        return {"success": True, "message": f"Job {job_id} cancelado"}
    else:
        return {
            "success": False,
            "message": f"Job {job_id} não pode ser cancelado (já em execução ou concluído)"
        }


@app.get("/batch/jobs", tags=["Batch"])
async def list_batch_jobs(active_only: bool = False):
    """
    Lista todos os batch jobs

    Query params:
        active_only: Se True, retorna apenas jobs pending/running

    Returns: {"jobs": [...]}
    """
    batch_processor = get_batch_processor()

    if active_only:
        jobs = batch_processor.get_active_jobs()
    else:
        jobs = batch_processor.get_all_jobs()

    return {"jobs": jobs, "total": len(jobs)}


@app.post("/v2/feedback", response_model=FeedbackSubmitResponse, tags=["V2"])
@limiter.limit("30/minute")
async def submit_feedback_v2(request: Request, payload: FeedbackSubmitRequest) -> FeedbackSubmitResponse:
    if FEEDBACK_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="FEEDBACK_COLLECTOR não está carregado.")
    try:
        event_id = FEEDBACK_COLLECTOR.add_feedback(
            prediction_id=payload.prediction_id,
            rating=payload.rating,
            user_params=payload.user_params,
            notes=payload.notes,
            feedback_type=payload.feedback_type,
            tags=payload.tags,
            issues=payload.issues,
            context={
                **(payload.feedback_context or {}),
                "seconds_to_submit": payload.seconds_to_submit,
                "source_ip": request.client.host if request.client else None,
            }
        )
        return FeedbackSubmitResponse(
            success=True,
            message="Feedback registado com sucesso.",
            event_id=event_id
        )
    except Exception as exc:
        logging.error(f"Erro ao registar feedback V2: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao registar feedback: {exc}")

@app.post("/retrain", response_model=RetrainResponse, tags=["V2"])
@limiter.limit("1/minute")
async def trigger_retrain(
    request: Request,
    payload: Dict[str, object] = Body(...)
) -> RetrainResponse:
    """
    Endpoint de re-treino (aceita JSON plano). Mantém permissivo para chamadas do plugin.
    """
    if FEEDBACK_COLLECTOR is None or AI_PREDICTOR is None:
        raise HTTPException(status_code=503, detail="FEEDBACK_COLLECTOR ou AI_PREDICTOR não estão carregados.")

    try:
        parsed = RetrainRequest.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Payload inválido: {exc}")

    retrainer = ActiveLearningRetrainer(FEEDBACK_COLLECTOR, AI_PREDICTOR)
    new_data = retrainer.collect_retraining_data(min_samples=parsed.min_samples)

    if new_data is None:
        return RetrainResponse(success=False, message="Dados insuficientes para re-treino.")

    thread = threading.Thread(target=retrainer.incremental_retrain, args=(new_data, parsed.epochs, parsed.batch_size))
    thread.start()

    return RetrainResponse(success=True, message="Re-treino iniciado em background.", samples_collected=len(new_data['image_paths']))

@app.post("/generate_xmp", response_model=GenerateXMPResponse, tags=["V2"])
@limiter.limit("10/minute")
async def generate_xmp_file(request: Request, payload: GenerateXMPRequest) -> GenerateXMPResponse:
    if XMP_GENERATOR is None:
        raise HTTPException(status_code=503, detail="XMP_GENERATOR não está carregado.")
    try:
        xmp_path = XMP_GENERATOR.generate_for_image(payload.image_path, payload.parameters)
        return GenerateXMPResponse(success=True, message="Ficheiro XMP gerado com sucesso.", xmp_path=str(xmp_path))
    except Exception as exc:
        logging.error(f"Erro ao gerar XMP: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar ficheiro XMP: {exc}")

@app.get("/stats", response_model=FeedbackStatsResponse, tags=["V2"])
@limiter.limit("5/minute")
async def get_feedback_stats(request: Request) -> FeedbackStatsResponse:
    if FEEDBACK_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="FEEDBACK_COLLECTOR não está carregado.")
    try:
        stats = FEEDBACK_COLLECTOR.get_stats()
        return FeedbackStatsResponse(**stats)
    except Exception as exc:
        logging.error(f"Erro ao obter estatísticas: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatísticas: {exc}")

@app.post("/auto-straighten", response_model=AutoStraightenResponse, tags=["V2"])
@limiter.limit("10/minute")
async def auto_straighten(request: Request, payload: AutoStraightenPayload) -> AutoStraightenResponse:
    """
    Detecta automaticamente o ângulo do horizonte na imagem e sugere correção.

    Usa OpenCV HoughLines para detectar linhas horizontais e calcular o ângulo de rotação necessário.
    """
    image_path = Path(payload.image_path)

    # Validar caminho da imagem
    if not _validate_image_path(image_path):
        raise HTTPException(status_code=400, detail=f"Caminho de imagem inválido: {payload.image_path}")

    try:
        # Detectar ângulo do horizonte
        result = detect_horizon_angle(
            str(image_path),
            min_line_length=payload.min_line_length,
            angle_threshold=payload.angle_threshold
        )

        logging.info(f"Auto-straighten para {image_path.name}: ângulo={result['angle']}°, confiança={result['confidence']}")

        return AutoStraightenResponse(**result)

    except Exception as exc:
        logging.error(f"Erro no auto-straighten para {payload.image_path}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao analisar imagem: {exc}")

# ============================================================================
# Alert Management Endpoints
# ============================================================================

@app.get("/api/alerts", tags=["Alerts"])
@limiter.limit("20/minute")
async def get_all_alerts(request: Request, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Retorna todos os alertas (histórico)

    Query params:
    - limit: Número máximo de alertas (mais recentes primeiro)
    """
    if ALERT_MANAGER is None:
        raise HTTPException(status_code=503, detail="ALERT_MANAGER não está carregado.")

    try:
        alerts = ALERT_MANAGER.get_all_alerts(limit=limit)
        return {
            "success": True,
            "total": len(alerts),
            "alerts": alerts
        }
    except Exception as exc:
        logging.error(f"Erro ao obter alertas: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter alertas: {exc}")


@app.get("/api/alerts/active", tags=["Alerts"])
@limiter.limit("30/minute")
async def get_active_alerts(request: Request) -> Dict[str, Any]:
    """
    Retorna alertas ativos (não acknowledged)
    """
    if ALERT_MANAGER is None:
        raise HTTPException(status_code=503, detail="ALERT_MANAGER não está carregado.")

    try:
        alerts = ALERT_MANAGER.get_active_alerts()
        return {
            "success": True,
            "total": len(alerts),
            "alerts": alerts
        }
    except Exception as exc:
        logging.error(f"Erro ao obter alertas ativos: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter alertas ativos: {exc}")


@app.post("/api/alerts/{alert_id}/acknowledge", tags=["Alerts"])
@limiter.limit("30/minute")
async def acknowledge_alert(request: Request, alert_id: str) -> Dict[str, Any]:
    """
    Marca alerta como acknowledged

    Path params:
    - alert_id: ID do alerta
    """
    if ALERT_MANAGER is None:
        raise HTTPException(status_code=503, detail="ALERT_MANAGER não está carregado.")

    try:
        success = ALERT_MANAGER.acknowledge_alert(alert_id)

        if success:
            # Broadcast update via WebSocket
            await ws_manager.broadcast({
                'type': 'alert_acknowledged',
                'data': {'alert_id': alert_id}
            })

            return {
                "success": True,
                "message": f"Alerta {alert_id} acknowledged"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Alerta {alert_id} não encontrado")

    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Erro ao acknowledge alerta: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao acknowledge alerta: {exc}")


@app.get("/api/alerts/stats", tags=["Alerts"])
@limiter.limit("20/minute")
async def get_alert_stats(request: Request) -> Dict[str, Any]:
    """
    Retorna estatísticas de alertas e sistema
    """
    if ALERT_MANAGER is None:
        raise HTTPException(status_code=503, detail="ALERT_MANAGER não está carregado.")

    try:
        stats = ALERT_MANAGER.get_stats()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as exc:
        logging.error(f"Erro ao obter estatísticas de alertas: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter estatísticas: {exc}")


@app.post("/api/alerts/trigger", tags=["Alerts"])
@limiter.limit("10/minute")
async def trigger_manual_alert(
    request: Request,
    alert_type: str,
    level: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Cria alerta manual (para testes ou triggers externos)

    Body params:
    - alert_type: Tipo de alerta (system, training_failed, etc)
    - level: Nível (info, warning, error, critical)
    - message: Mensagem do alerta
    - metadata: Dados adicionais (opcional)
    """
    if ALERT_MANAGER is None:
        raise HTTPException(status_code=503, detail="ALERT_MANAGER não está carregado.")

    try:
        # Validar inputs
        try:
            alert_type_enum = AlertType(alert_type)
            level_enum = AlertLevel(level)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Tipo ou nível inválido: {e}")

        # Criar alerta
        alert = await ALERT_MANAGER.create_alert(
            alert_type=alert_type_enum,
            level=level_enum,
            message=message,
            metadata=metadata,
            force=True  # Ignora cooldown para alertas manuais
        )

        if alert:
            return {
                "success": True,
                "message": "Alerta criado com sucesso",
                "alert": alert.to_dict()
            }
        else:
            return {
                "success": False,
                "message": "Alerta não foi criado (possível cooldown)"
            }

    except HTTPException:
        raise
    except Exception as exc:
        logging.error(f"Erro ao criar alerta manual: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar alerta: {exc}")

# ============================================================================
# Monitoring Endpoints
# ============================================================================

@app.get("/api/monitoring/metrics", tags=["Monitoring"])
@limiter.limit("20/minute")
async def get_all_monitoring_metrics(request: Request) -> Dict[str, Any]:
    """
    Retorna todas as métricas de monitorização (GPU, modelo, sistema)
    """
    if MONITORING_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="MONITORING_COLLECTOR não está carregado.")

    try:
        metrics = MONITORING_COLLECTOR.get_all_metrics()
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as exc:
        logging.error(f"Erro ao obter métricas de monitorização: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter métricas: {exc}")


@app.get("/api/monitoring/summary", tags=["Monitoring"])
@limiter.limit("30/minute")
async def get_monitoring_summary(request: Request) -> Dict[str, Any]:
    """
    Retorna resumo das métricas principais (para dashboard)
    """
    if MONITORING_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="MONITORING_COLLECTOR não está carregado.")

    try:
        summary = MONITORING_COLLECTOR.get_summary()
        return {
            "success": True,
            "summary": summary
        }
    except Exception as exc:
        logging.error(f"Erro ao obter resumo de monitorização: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter resumo: {exc}")


@app.get("/api/monitoring/gpu", tags=["Monitoring"])
@limiter.limit("30/minute")
async def get_gpu_metrics(request: Request) -> Dict[str, Any]:
    """
    Retorna métricas de GPU
    """
    if MONITORING_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="MONITORING_COLLECTOR não está carregado.")

    try:
        gpu_metrics = MONITORING_COLLECTOR.gpu_monitor.get_metrics()
        return {
            "success": True,
            "gpu": gpu_metrics
        }
    except Exception as exc:
        logging.error(f"Erro ao obter métricas de GPU: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter métricas de GPU: {exc}")


@app.get("/api/monitoring/model", tags=["Monitoring"])
@limiter.limit("30/minute")
async def get_model_metrics(request: Request) -> Dict[str, Any]:
    """
    Retorna métricas do modelo (latência, throughput, distribuição)
    """
    if MONITORING_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="MONITORING_COLLECTOR não está carregado.")

    try:
        model_metrics = MONITORING_COLLECTOR.model_monitor.get_metrics()
        return {
            "success": True,
            "model": model_metrics
        }
    except Exception as exc:
        logging.error(f"Erro ao obter métricas do modelo: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter métricas do modelo: {exc}")


@app.get("/api/monitoring/system", tags=["Monitoring"])
@limiter.limit("30/minute")
async def get_system_metrics(request: Request) -> Dict[str, Any]:
    """
    Retorna métricas de sistema (CPU, memória, disco, network)
    """
    if MONITORING_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="MONITORING_COLLECTOR não está carregado.")

    try:
        system_metrics = MONITORING_COLLECTOR.system_monitor.get_metrics()
        return {
            "success": True,
            "system": system_metrics
        }
    except Exception as exc:
        logging.error(f"Erro ao obter métricas de sistema: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter métricas de sistema: {exc}")


@app.post("/api/monitoring/reset", tags=["Monitoring"])
@limiter.limit("5/minute")
async def reset_model_metrics(request: Request) -> Dict[str, Any]:
    """
    Reset das métricas do modelo (para testes ou após manutenção)
    """
    if MONITORING_COLLECTOR is None:
        raise HTTPException(status_code=503, detail="MONITORING_COLLECTOR não está carregado.")

    try:
        MONITORING_COLLECTOR.model_monitor.reset()
        return {
            "success": True,
            "message": "Métricas do modelo resetadas com sucesso"
        }
    except Exception as exc:
        logging.error(f"Erro ao resetar métricas: {exc}")
        raise HTTPException(status_code=500, detail=f"Erro ao resetar métricas: {exc}")

# ============================================================================
# Plugin Logging Endpoint
# ============================================================================

class PluginLogRequest(BaseModel):
    level: str = Field(..., description="Nível do log: INFO, WARN, ERROR, DEBUG")
    source: str = Field(..., description="Origem do log: ApplyAIPresetV2, Common_V2, etc")
    message: str = Field(..., description="Mensagem do log")
    timestamp: Optional[str] = Field(None, description="Timestamp do log")

@app.post("/plugin-log", tags=["Debug"])
async def receive_plugin_log(log: PluginLogRequest):
    """
    Recebe logs do plugin Lightroom para debug.

    Este endpoint permite que o plugin Lua envie logs diretamente para o servidor,
    facilitando o debug de problemas quando os logs do Lightroom não são acessíveis.
    """
    timestamp = log.timestamp or datetime.now().isoformat()
    formatted = f"[{timestamp}] {log.source}: {log.message}"

    # Log para console do servidor (com cores se possível)
    if log.level == "ERROR":
        logging.error(f"PLUGIN: {formatted}")
    elif log.level == "WARN":
        logging.warning(f"PLUGIN: {formatted}")
    elif log.level == "DEBUG":
        logging.debug(f"PLUGIN: {formatted}")
    else:
        logging.info(f"PLUGIN: {formatted}")

    return {"status": "logged"}

# ============================================================================
# Preset Management Endpoints
# ============================================================================

from services.preset_manager import (
    PresetManager,
    PresetNotFoundError,
    PresetAlreadyInstalledError,
    ensure_default_preset_exists
)
from services.preset_package import PresetPackageError

# Inicializar PresetManager global
PRESET_MANAGER: Optional[PresetManager] = None

class PresetListResponse(BaseModel):
    presets: List[Dict]
    total: int

class PresetDetailResponse(BaseModel):
    preset: Dict

class PresetInstallResponse(BaseModel):
    success: bool
    message: str
    preset_id: Optional[str] = None

class PresetUninstallResponse(BaseModel):
    success: bool
    message: str

class PresetExportRequest(BaseModel):
    preset_id: Optional[str] = Field(None, description="ID do preset a exportar. Se None, exporta modelos actuais.")
    output_filename: str = Field(..., description="Nome do ficheiro .nsppreset a criar")
    use_current_models: bool = Field(False, description="Se True, usa modelos actuais em vez dos do preset")

class PresetExportResponse(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None

class ActivePresetResponse(BaseModel):
    preset: Optional[Dict]

class SetActivePresetRequest(BaseModel):
    preset_id: str = Field(..., description="ID do preset a activar")

class SetActivePresetResponse(BaseModel):
    success: bool
    message: str

@app.get("/api/presets", response_model=PresetListResponse, tags=["Presets"])
@limiter.limit("30/minute")
async def list_presets(request: Request) -> PresetListResponse:
    """
    Lista todos os presets instalados.

    Returns:
        Lista de presets com informação básica (id, name, version, author, etc.)
    """
    if PRESET_MANAGER is None:
        raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

    try:
        presets = PRESET_MANAGER.list_presets()
        return PresetListResponse(presets=presets, total=len(presets))
    except Exception as exc:
        logging.error(f"Erro ao listar presets: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao listar presets: {exc}")

@app.get("/api/presets/{preset_id}", response_model=PresetDetailResponse, tags=["Presets"])
@limiter.limit("30/minute")
async def get_preset_detail(request: Request, preset_id: str) -> PresetDetailResponse:
    """
    Obtém informação detalhada de um preset específico.

    Args:
        preset_id: ID do preset

    Returns:
        Informação completa do preset (manifest.json + metadata)
    """
    if PRESET_MANAGER is None:
        raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

    try:
        preset = PRESET_MANAGER.get_preset(preset_id)
        return PresetDetailResponse(preset=preset)
    except PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logging.error(f"Erro ao obter preset {preset_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao obter preset: {exc}")

# TEMPORARIAMENTE COMENTADO - UploadFile issue
# @app.post("/api/presets/install", tags=["Presets"])
# @limiter.limit("5/minute")
# async def install_preset(
#     request: Request,
#     file: UploadFile = File(..., description="Ficheiro .nsppreset a instalar"),
#     force: bool = False
# ):
#     """
#     Instala um preset a partir de um ficheiro .nsppreset.

#     Args:
#         file: Ficheiro .nsppreset (upload)
#         force: Se True, reinstala mesmo se já existir

#     Returns:
#         Resultado da instalação com ID do preset
#     """
#     if PRESET_MANAGER is None:
#         raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

#     # Validar extensão do ficheiro
#     if not file.filename or not file.filename.endswith('.nsppreset'):
#         raise HTTPException(status_code=400, detail="Ficheiro deve ter extensão .nsppreset")

#     # Guardar ficheiro temporário
#     import tempfile
#     with tempfile.NamedTemporaryFile(delete=False, suffix='.nsppreset') as tmp_file:
#         tmp_path = Path(tmp_file.name)
#         try:
#             # Ler e guardar ficheiro
#             content = await file.read()
#             tmp_file.write(content)
#             tmp_file.flush()

#             # Instalar preset
#             preset_id = PRESET_MANAGER.install_preset(tmp_path, force=force)

#             return PresetInstallResponse(
#                 success=True,
#                 message=f"Preset instalado com sucesso: {preset_id}",
#                 preset_id=preset_id
#             )

#         except PresetAlreadyInstalledError as exc:
#             raise HTTPException(status_code=409, detail=str(exc))
#         except PresetPackageError as exc:
#             logging.error(f"Erro ao instalar preset: {exc}")
#             raise HTTPException(status_code=400, detail=str(exc))
#         except Exception as exc:
#             logging.error(f"Erro inesperado ao instalar preset: {exc}", exc_info=True)
#             raise HTTPException(status_code=500, detail=f"Erro ao instalar preset: {exc}")
#         finally:
#             # Limpar ficheiro temporário
#             if tmp_path.exists():
#                 tmp_path.unlink()

@app.delete("/api/presets/{preset_id}", response_model=PresetUninstallResponse, tags=["Presets"])
@limiter.limit("10/minute")
async def uninstall_preset(request: Request, preset_id: str) -> PresetUninstallResponse:
    """
    Remove um preset instalado.

    Args:
        preset_id: ID do preset a remover

    Returns:
        Resultado da remoção
    """
    if PRESET_MANAGER is None:
        raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

    try:
        PRESET_MANAGER.uninstall_preset(preset_id)
        return PresetUninstallResponse(success=True, message=f"Preset removido: {preset_id}")
    except PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logging.error(f"Erro ao remover preset {preset_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao remover preset: {exc}")

@app.get("/api/presets/active", response_model=ActivePresetResponse, tags=["Presets"])
@limiter.limit("30/minute")
async def get_active_preset(request: Request) -> ActivePresetResponse:
    """
    Obtém o preset actualmente activo.

    Returns:
        Informação do preset activo, ou None se nenhum activo
    """
    if PRESET_MANAGER is None:
        raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

    try:
        preset = PRESET_MANAGER.get_active_preset()
        return ActivePresetResponse(preset=preset)
    except Exception as exc:
        logging.error(f"Erro ao obter preset activo: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao obter preset activo: {exc}")

@app.put("/api/presets/active", response_model=SetActivePresetResponse, tags=["Presets"])
@limiter.limit("10/minute")
async def set_active_preset(request: Request, payload: SetActivePresetRequest) -> SetActivePresetResponse:
    """
    Define o preset activo.

    Args:
        payload: Payload com preset_id

    Returns:
        Resultado da operação
    """
    if PRESET_MANAGER is None:
        raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

    try:
        PRESET_MANAGER.set_active_preset(payload.preset_id)
        return SetActivePresetResponse(success=True, message=f"Preset activo definido: {payload.preset_id}")
    except PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logging.error(f"Erro ao definir preset activo {payload.preset_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao definir preset activo: {exc}")

@app.post("/api/presets/export", response_model=PresetExportResponse, tags=["Presets"])
@limiter.limit("5/minute")
async def export_preset(request: Request, payload: PresetExportRequest) -> PresetExportResponse:
    """
    Exporta um preset como ficheiro .nsppreset.

    Args:
        payload: Payload com preset_id (opcional), output_filename e use_current_models

    Returns:
        URL para download do ficheiro .nsppreset
    """
    if PRESET_MANAGER is None:
        raise HTTPException(status_code=503, detail="PRESET_MANAGER não está carregado.")

    # Validar nome do ficheiro
    if not payload.output_filename.endswith('.nsppreset'):
        payload.output_filename += '.nsppreset'

    # Criar diretório de exports
    exports_dir = TEMP_DIR / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    output_path = exports_dir / payload.output_filename

    try:
        PRESET_MANAGER.export_preset(
            preset_id=payload.preset_id,
            output_path=output_path,
            use_current_models=payload.use_current_models
        )

        # URL para download
        download_url = f"/downloads/exports/{payload.output_filename}"

        return PresetExportResponse(
            success=True,
            message=f"Preset exportado com sucesso: {payload.output_filename}",
            download_url=download_url
        )

    except PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PresetPackageError as exc:
        logging.error(f"Erro ao exportar preset: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logging.error(f"Erro inesperado ao exportar preset: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro ao exportar preset: {exc}")

# Montar diretório de downloads para exports
EXPORTS_DIR = TEMP_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/downloads/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# ============================================================================
# Culling Endpoints
# ============================================================================

class CullingImageInput(BaseModel):
    image_path: str = Field(..., description="Caminho para a imagem a analisar")
    exif: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadados EXIF opcionais")

class CullingScoreRequest(BaseModel):
    images: List[CullingImageInput] = Field(..., description="Lista de imagens para análise de qualidade")

class CullingScoreResponse(BaseModel):
    scores: List[float] = Field(..., description="Lista de scores de qualidade (0-100) para cada imagem")
    analysis_time: float = Field(..., description="Tempo de análise em segundos")

@app.post("/api/culling/score", response_model=CullingScoreResponse, tags=["Culling"])
async def culling_score_batch(payload: CullingScoreRequest) -> CullingScoreResponse:
    """
    Análise de qualidade em lote para culling inteligente.

    Avalia a qualidade técnica e estética de múltiplas imagens usando modelo de culling AI.
    Retorna scores de 0-100 onde valores mais altos indicam melhor qualidade.

    Args:
        payload: Lista de imagens com caminhos e metadados EXIF opcionais

    Returns:
        Lista de scores de qualidade correspondente a cada imagem
    """
    import time
    start_time = time.time()

    if not payload.images or len(payload.images) == 0:
        raise HTTPException(status_code=400, detail="Nenhuma imagem fornecida para análise")

    logging.info(f"Culling: A analisar {len(payload.images)} imagens")

    try:
        # Importar módulo de culling
        from services.culling import CullingPredictor

        # Inicializar predictor (cache interno para reutilização)
        culling_predictor = CullingPredictor(
            model_path=MODELS_DIR / "culling_model.pth",
            device="cpu"  # Usar GPU se disponível
        )

        scores = []

        for img_input in payload.images:
            image_path = Path(img_input.image_path)

            # Validar caminho
            if not _validate_image_path(image_path):
                logging.warning(f"Caminho inválido ignorado: {img_input.image_path}")
                scores.append(0.0)  # Score mínimo para imagens inválidas
                continue

            try:
                # Fazer predição de qualidade
                score = culling_predictor.predict_quality(
                    image_path=str(image_path),
                    exif=img_input.exif
                )

                # Normalizar score para 0-100
                normalized_score = max(0.0, min(100.0, score * 100))
                scores.append(normalized_score)

            except Exception as img_exc:
                logging.error(f"Erro ao analisar {image_path.name}: {img_exc}")
                scores.append(0.0)  # Score mínimo em caso de erro

        analysis_time = time.time() - start_time

        logging.info(f"Culling: {len(scores)} imagens analisadas em {analysis_time:.2f}s")

        return CullingScoreResponse(
            scores=scores,
            analysis_time=analysis_time
        )

    except ImportError:
        # Modelo de culling não disponível - usar fallback baseado em EXIF
        logging.warning("Modelo de culling não disponível, usando análise simplificada baseada em EXIF")

        scores = []
        for img_input in payload.images:
            # Score simplificado baseado em metadados
            exif = img_input.exif
            score = 50.0  # Base score

            # Ajustar baseado em ISO (menor ISO = melhor)
            iso = exif.get("iso", 0)
            if iso > 0:
                if iso <= 400:
                    score += 20
                elif iso <= 1600:
                    score += 10
                elif iso >= 6400:
                    score -= 20

            # Ajustar baseado em abertura
            aperture = exif.get("aperture", 0)
            if aperture > 0:
                if 1.4 <= aperture <= 8.0:
                    score += 10

            # Normalizar
            score = max(0.0, min(100.0, score))
            scores.append(score)

        analysis_time = time.time() - start_time

        return CullingScoreResponse(
            scores=scores,
            analysis_time=analysis_time
        )

# ============================================================================
# Advanced AI Culling Endpoints
# ============================================================================

from services.ai_core.culling_ai import CullingAI, PhotoScore

# Global culling instance
CULLING_AI: Optional[CullingAI] = None

class CullingBatchRequest(BaseModel):
    """Request para culling em batch"""
    image_paths: List[str] = Field(..., description="Lista de caminhos das imagens")
    keep_percent: float = Field(0.5, ge=0.0, le=1.0, description="Percentagem a manter (0.0-1.0)")
    remove_duplicates: bool = Field(True, description="Detectar e remover duplicatas")
    use_aesthetic_model: bool = Field(False, description="Usar modelo deep learning (mais lento)")

class PhotoScoreResponse(BaseModel):
    """Score de uma foto individual"""
    path: str
    technical_score: float
    aesthetic_score: float
    face_score: float
    overall_score: float
    keep: bool
    is_duplicate: bool
    duplicate_of: Optional[str] = None

class CullingBatchResponse(BaseModel):
    """Response de culling em batch"""
    scores: List[PhotoScoreResponse]
    keep_list: List[str]
    discard_list: List[str]
    total_processed: int
    total_kept: int
    total_discarded: int
    duplicates_found: int
    processing_time_s: float

@app.on_event("startup")
def initialize_culling():
    """Inicializa CullingAI no startup"""
    global CULLING_AI
    try:
        CULLING_AI = CullingAI(use_aesthetic_model=False)
        logging.info("✅ CullingAI inicializado com sucesso")
    except Exception as e:
        logging.error(f"❌ Erro ao inicializar CullingAI: {e}")
        CULLING_AI = None

@app.post("/api/culling/batch", response_model=CullingBatchResponse, tags=["Culling"])
@limiter.limit("5/minute")
async def culling_batch(request: Request, payload: CullingBatchRequest) -> CullingBatchResponse:
    """
    AI Culling em batch - seleciona automaticamente as melhores fotos

    Analisa:
    - Qualidade técnica (sharpness, exposure, noise)
    - Aesthetic score (composição, cores)
    - Face detection (para portraits)
    - Duplicate detection (perceptual hashing)

    Returns:
        Rankings com recomendações keep/discard
    """
    import time

    if CULLING_AI is None:
        raise HTTPException(status_code=503, detail="CullingAI não está disponível")

    if len(payload.image_paths) == 0:
        raise HTTPException(status_code=400, detail="Lista de imagens vazia")

    if len(payload.image_paths) > 1000:
        raise HTTPException(status_code=400, detail="Máximo 1000 imagens por batch")

    logging.info(f"🔍 Culling batch: {len(payload.image_paths)} imagens")

    start_time = time.time()

    try:
        # Se pedido aesthetic model e não está carregado, carregar
        if payload.use_aesthetic_model and not CULLING_AI.aesthetic_scorer:
            logging.info("Carregando aesthetic model...")
            try:
                from services.ai_core.culling_ai import AestheticScorer
                CULLING_AI.aesthetic_scorer = AestheticScorer()
                CULLING_AI.use_aesthetic_model = True
            except Exception as e:
                logging.warning(f"Não foi possível carregar aesthetic model: {e}")

        # Run culling
        all_scores, keep_list, discard_list = CULLING_AI.cull_batch(
            image_paths=payload.image_paths,
            keep_top_percent=payload.keep_percent,
            remove_duplicates=payload.remove_duplicates
        )

        processing_time = time.time() - start_time

        # Convert scores to response format
        scores_response = [
            PhotoScoreResponse(
                path=score.path,
                technical_score=score.technical_score,
                aesthetic_score=score.aesthetic_score,
                face_score=score.face_score,
                overall_score=score.overall_score,
                keep=score.keep,
                is_duplicate=score.is_duplicate,
                duplicate_of=score.duplicate_of
            )
            for score in all_scores
        ]

        duplicates_count = sum(1 for s in all_scores if s.is_duplicate)

        logging.info(f"✅ Culling completo em {processing_time:.2f}s")
        logging.info(f"   Keep: {len(keep_list)}, Discard: {len(discard_list)}, Duplicates: {duplicates_count}")

        return CullingBatchResponse(
            scores=scores_response,
            keep_list=keep_list,
            discard_list=discard_list,
            total_processed=len(all_scores),
            total_kept=len(keep_list),
            total_discarded=len(discard_list),
            duplicates_found=duplicates_count,
            processing_time_s=processing_time
        )

    except Exception as e:
        logging.error(f"❌ Erro no culling: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no culling: {str(e)}")

@app.post("/api/culling/single", response_model=PhotoScoreResponse, tags=["Culling"])
@limiter.limit("30/minute")
async def culling_single(request: Request, image_path: str = Body(..., embed=True)) -> PhotoScoreResponse:
    """
    Analisa qualidade de uma foto individual

    Returns:
        Score detalhado (technical, aesthetic, faces, overall)
    """
    if CULLING_AI is None:
        raise HTTPException(status_code=503, detail="CullingAI não está disponível")

    if not Path(image_path).exists():
        raise HTTPException(status_code=404, detail=f"Imagem não encontrada: {image_path}")

    try:
        score = CULLING_AI.score_photo(image_path)

        return PhotoScoreResponse(
            path=score.path,
            technical_score=score.technical_score,
            aesthetic_score=score.aesthetic_score,
            face_score=score.face_score,
            overall_score=score.overall_score,
            keep=score.keep,
            is_duplicate=score.is_duplicate,
            duplicate_of=score.duplicate_of
        )

    except Exception as e:
        logging.error(f"❌ Erro ao analisar foto: {e}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.post("/api/culling/export", tags=["Culling"])
@limiter.limit("5/minute")
async def culling_export_report(
    request: Request,
    payload: CullingBatchRequest,
    output_filename: str = "culling_report.csv"
) -> Dict[str, str]:
    """
    Exporta relatório de culling para CSV

    Returns:
        URL para download do relatório
    """
    if CULLING_AI is None:
        raise HTTPException(status_code=503, detail="CullingAI não está disponível")

    try:
        # Run culling
        all_scores, _, _ = CULLING_AI.cull_batch(
            image_paths=payload.image_paths,
            keep_top_percent=payload.keep_percent,
            remove_duplicates=payload.remove_duplicates
        )

        # Export to temp directory
        reports_dir = TEMP_DIR / "culling_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        output_path = reports_dir / output_filename

        CULLING_AI.export_report(all_scores, str(output_path))

        # Return download URL
        download_url = f"/downloads/culling_reports/{output_filename}"

        return {
            "success": True,
            "message": f"Relatório exportado: {output_filename}",
            "download_url": download_url,
            "total_photos": len(all_scores)
        }

    except Exception as e:
        logging.error(f"❌ Erro ao exportar relatório: {e}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

# Mount culling reports directory
CULLING_REPORTS_DIR = TEMP_DIR / "culling_reports"
CULLING_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/downloads/culling_reports", StaticFiles(directory=str(CULLING_REPORTS_DIR)), name="culling_reports")

# ============================================================================
# Face Detection & Grouping API
# ============================================================================

from services.ai_core.face_detection import (
    FaceAnalysisSystem,
    FaceDetection,
    Person,
    DetectionMethod
)

# Global face analysis instance
FACE_ANALYSIS: Optional[FaceAnalysisSystem] = None

class FaceDetectRequest(BaseModel):
    """Request para detecção de faces em uma imagem"""
    image_path: str = Field(..., description="Caminho da imagem")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Confiança mínima para detecção")
    method: str = Field("dnn", description="Método de detecção: 'dnn' ou 'haar'")

class FaceDetectBatchRequest(BaseModel):
    """Request para detecção de faces em batch"""
    image_paths: List[str] = Field(..., description="Lista de caminhos das imagens")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)
    method: str = Field("dnn", description="Método: 'dnn' ou 'haar'")

class FaceGroupRequest(BaseModel):
    """Request para agrupamento de faces"""
    image_paths: List[str] = Field(..., description="Caminhos das imagens")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)
    similarity_threshold: float = Field(0.6, ge=0.0, le=1.0, description="Threshold de similaridade")
    min_faces_per_person: int = Field(1, ge=1, description="Mínimo de faces por pessoa")

class FaceDetectionResponse(BaseModel):
    """Resposta de detecção de face"""
    bbox: List[int] = Field(..., description="[x, y, width, height]")
    confidence: float
    quality_score: float
    method: str
    has_embedding: bool

class FaceDetectSingleResponse(BaseModel):
    """Resposta de detecção única"""
    image_path: str
    faces: List[FaceDetectionResponse]
    total_faces: int
    processing_time_ms: float

class FaceDetectBatchResponse(BaseModel):
    """Resposta de detecção em batch"""
    results: List[FaceDetectSingleResponse]
    total_images: int
    total_faces: int
    processing_time_s: float

class PersonGroupResponse(BaseModel):
    """Informação de um grupo de pessoa"""
    person_id: int
    total_faces: int
    avg_quality: float
    best_face_path: str
    all_images: List[str]

class FaceGroupResponse(BaseModel):
    """Resposta de agrupamento de faces"""
    persons: List[PersonGroupResponse]
    total_persons: int
    total_faces: int
    processing_time_s: float

@app.on_event("startup")
def initialize_face_detection():
    """Inicializa Face Detection no startup"""
    global FACE_ANALYSIS
    try:
        FACE_ANALYSIS = FaceAnalysisSystem(
            dnn_model_path="models/opencv_face_detector.caffemodel",
            dnn_config_path="models/opencv_face_detector.prototxt",
            recognition_model_path="services/ai_core/models/face_recognition/openface.nn4.small2.v1.t7"
        )
        logging.info("✅ Face Detection inicializado com sucesso")
    except Exception as e:
        logging.warning(f"⚠️ Face Detection não disponível: {e}")
        FACE_ANALYSIS = None

@app.post("/api/faces/detect", response_model=FaceDetectSingleResponse, tags=["Face Detection"])
@limiter.limit("10/minute")
async def detect_faces_single(request: Request, payload: FaceDetectRequest) -> FaceDetectSingleResponse:
    """
    Detecta faces em uma única imagem.

    Retorna lista de bounding boxes, confiança e score de qualidade para cada face.
    """
    if not FACE_ANALYSIS:
        raise HTTPException(status_code=503, detail="Face Detection não disponível")

    try:
        import time
        start = time.time()

        # Validate method
        try:
            method = DetectionMethod[payload.method.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Método inválido: {payload.method}")

        # Detect faces
        faces = FACE_ANALYSIS.detector.detect_faces(
            payload.image_path,
            method=method,
            min_confidence=payload.min_confidence
        )

        # Extract embeddings for grouping capability
        if faces:
            faces = FACE_ANALYSIS.recognizer.extract_embeddings_for_faces(
                payload.image_path,
                faces
            )

        # Convert to response format
        face_responses = [
            FaceDetectionResponse(
                bbox=[f.bbox[0], f.bbox[1], f.bbox[2], f.bbox[3]],
                confidence=f.confidence,
                quality_score=f.quality_score,
                method=f.method.value,
                has_embedding=(f.embedding is not None)
            )
            for f in faces
        ]

        elapsed_ms = (time.time() - start) * 1000

        return FaceDetectSingleResponse(
            image_path=payload.image_path,
            faces=face_responses,
            total_faces=len(faces),
            processing_time_ms=round(elapsed_ms, 2)
        )

    except Exception as e:
        logging.error(f"❌ Erro na detecção de faces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.post("/api/faces/detect/batch", response_model=FaceDetectBatchResponse, tags=["Face Detection"])
@limiter.limit("5/minute")
async def detect_faces_batch(request: Request, payload: FaceDetectBatchRequest) -> FaceDetectBatchResponse:
    """
    Detecta faces em múltiplas imagens (batch).

    Retorna detecções para cada imagem processada.
    """
    if not FACE_ANALYSIS:
        raise HTTPException(status_code=503, detail="Face Detection não disponível")

    try:
        import time
        start = time.time()

        # Validate method
        try:
            method = DetectionMethod[payload.method.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Método inválido: {payload.method}")

        results = []
        total_faces = 0

        for image_path in payload.image_paths:
            try:
                img_start = time.time()

                # Detect faces
                faces = FACE_ANALYSIS.detector.detect_faces(
                    image_path,
                    method=method,
                    min_confidence=payload.min_confidence
                )

                # Extract embeddings
                if faces:
                    faces = FACE_ANALYSIS.recognizer.extract_embeddings_for_faces(
                        image_path,
                        faces
                    )

                # Convert to response
                face_responses = [
                    FaceDetectionResponse(
                        bbox=[f.bbox[0], f.bbox[1], f.bbox[2], f.bbox[3]],
                        confidence=f.confidence,
                        quality_score=f.quality_score,
                        method=f.method.value,
                        has_embedding=(f.embedding is not None)
                    )
                    for f in faces
                ]

                img_elapsed_ms = (time.time() - img_start) * 1000

                results.append(FaceDetectSingleResponse(
                    image_path=image_path,
                    faces=face_responses,
                    total_faces=len(faces),
                    processing_time_ms=round(img_elapsed_ms, 2)
                ))

                total_faces += len(faces)

            except Exception as e:
                logging.warning(f"⚠️ Erro ao processar {image_path}: {e}")
                results.append(FaceDetectSingleResponse(
                    image_path=image_path,
                    faces=[],
                    total_faces=0,
                    processing_time_ms=0.0
                ))

        elapsed_s = time.time() - start

        return FaceDetectBatchResponse(
            results=results,
            total_images=len(payload.image_paths),
            total_faces=total_faces,
            processing_time_s=round(elapsed_s, 2)
        )

    except Exception as e:
        logging.error(f"❌ Erro no batch de detecção: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.post("/api/faces/group", response_model=FaceGroupResponse, tags=["Face Detection"])
@limiter.limit("3/minute")
async def group_faces(request: Request, payload: FaceGroupRequest) -> FaceGroupResponse:
    """
    Detecta e agrupa faces por pessoa em múltiplas imagens.

    Usa embeddings faciais e clustering DBSCAN para identificar pessoas únicas.
    Retorna grupos ordenados por qualidade média das faces.
    """
    if not FACE_ANALYSIS:
        raise HTTPException(status_code=503, detail="Face Detection não disponível")

    try:
        import time
        start = time.time()

        # Detect all faces
        all_faces = []
        for image_path in payload.image_paths:
            try:
                faces = FACE_ANALYSIS.detector.detect_faces(
                    image_path,
                    method=DetectionMethod.DNN,
                    min_confidence=payload.min_confidence
                )

                # Extract embeddings (required for grouping)
                if faces:
                    faces = FACE_ANALYSIS.recognizer.extract_embeddings_for_faces(
                        image_path,
                        faces
                    )
                    all_faces.extend(faces)

            except Exception as e:
                logging.warning(f"⚠️ Erro ao processar {image_path}: {e}")

        if not all_faces:
            return FaceGroupResponse(
                persons=[],
                total_persons=0,
                total_faces=0,
                processing_time_s=0.0
            )

        # Group faces by person
        persons = FACE_ANALYSIS.grouper.group_faces(
            all_faces,
            similarity_threshold=payload.similarity_threshold,
            min_faces_per_person=payload.min_faces_per_person
        )

        # Rank faces within each person
        for person in persons:
            person.faces = FACE_ANALYSIS.quality_scorer.rank_faces(person.faces)

        # Sort persons by average quality
        persons.sort(key=lambda p: p.avg_quality, reverse=True)

        # Convert to response format
        person_responses = []
        for i, person in enumerate(persons):
            # Get unique image paths for this person
            unique_images = list(set(f.image_path for f in person.faces))

            person_responses.append(PersonGroupResponse(
                person_id=i,
                total_faces=person.face_count,
                avg_quality=round(person.avg_quality, 2),
                best_face_path=person.faces[0].image_path if person.faces else "",
                all_images=unique_images
            ))

        elapsed_s = time.time() - start

        return FaceGroupResponse(
            persons=person_responses,
            total_persons=len(persons),
            total_faces=len(all_faces),
            processing_time_s=round(elapsed_s, 2)
        )

    except Exception as e:
        logging.error(f"❌ Erro no agrupamento de faces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ============================================================================
# Main - Start Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Load config
    host = config.get('server.host', '127.0.0.1')
    port = config.get('server.port', 5678)
    workers = config.get('server.workers', 1)
    log_level = config.get('server.log_level', 'info')

    logging.info(f"🚀 Iniciando NSP Plugin Server em {host}:{port}")

    uvicorn.run(
        "services.server:app",
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
        reload=False
    )
