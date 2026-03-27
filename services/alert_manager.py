"""
Alert Manager - Sistema de Alertas Automáticos
Monitoriza sistema e envia alertas em tempo real

Features:
- Alertas de memória alta (>85%)
- Alertas de inferência lenta (>500ms)
- Alertas de modelo não carregado
- Alertas de disco quase cheio (>90%)
- Histórico de alertas
- Sistema de acknowledgment

Data: 21 Novembro 2025
"""

import logging
import psutil
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Níveis de alerta"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Tipos de alerta"""
    HIGH_MEMORY = "high_memory"
    SLOW_INFERENCE = "slow_inference"
    MODEL_NOT_LOADED = "model_not_loaded"
    DISK_FULL = "disk_full"
    GPU_ERROR = "gpu_error"
    TRAINING_FAILED = "training_failed"
    SYSTEM = "system"


@dataclass
class Alert:
    """Estrutura de um alerta"""
    id: str
    type: AlertType
    level: AlertLevel
    message: str
    timestamp: str
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dict"""
        return asdict(self)


class AlertManager:
    """
    Gestor de alertas automáticos

    Monitoriza sistema e gera alertas quando necessário
    Mantém histórico e permite acknowledgment
    """

    def __init__(self, max_history: int = 100):
        """
        Args:
            max_history: Número máximo de alertas no histórico
        """
        self.max_history = max_history
        self.alerts: List[Alert] = []
        self.alert_counter = 0
        self.websocket_manager = None  # Será injetado pelo servidor

        # Thresholds
        self.memory_threshold = 85.0  # %
        self.inference_time_threshold = 500  # ms
        self.disk_threshold = 90.0  # %

        # Tracking de estado
        self.last_alerts: Dict[str, float] = {}  # Para evitar spam
        self.cooldown_seconds = 300  # 5 minutos entre alertas do mesmo tipo

        # Estatísticas de inferência
        self.inference_times: List[float] = []
        self.max_inference_samples = 100

        logger.info("AlertManager inicializado")

    def set_websocket_manager(self, manager):
        """Injeta o WebSocket manager para broadcast"""
        self.websocket_manager = manager
        logger.info("WebSocket manager registado no AlertManager")

    def _generate_alert_id(self) -> str:
        """Gera ID único para alerta"""
        self.alert_counter += 1
        return f"alert_{int(time.time())}_{self.alert_counter}"

    def _should_send_alert(self, alert_type: AlertType) -> bool:
        """
        Verifica se deve enviar alerta (cooldown logic)

        Args:
            alert_type: Tipo de alerta

        Returns:
            True se pode enviar
        """
        key = alert_type.value
        last_time = self.last_alerts.get(key, 0)
        current_time = time.time()

        if current_time - last_time > self.cooldown_seconds:
            self.last_alerts[key] = current_time
            return True

        return False

    async def _broadcast_alert(self, alert: Alert):
        """Envia alerta via WebSocket"""
        if self.websocket_manager:
            try:
                await self.websocket_manager.broadcast({
                    "type": "alert",
                    "data": alert.to_dict()
                })
                logger.debug(f"Alerta broadcasted: {alert.type}")
            except Exception as e:
                logger.error(f"Erro ao broadcast alerta: {e}")

    async def create_alert(
        self,
        alert_type: AlertType,
        level: AlertLevel,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Alert]:
        """
        Cria e envia um novo alerta

        Args:
            alert_type: Tipo de alerta
            level: Nível de severidade
            message: Mensagem descritiva
            metadata: Dados adicionais
            force: Se True, ignora cooldown

        Returns:
            Alert criado ou None se em cooldown
        """
        # Verificar cooldown
        if not force and not self._should_send_alert(alert_type):
            logger.debug(f"Alerta {alert_type} em cooldown, ignorado")
            return None

        # Criar alerta
        alert = Alert(
            id=self._generate_alert_id(),
            type=alert_type,
            level=level,
            message=message,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )

        # Adicionar ao histórico
        self.alerts.append(alert)

        # Limitar histórico
        if len(self.alerts) > self.max_history:
            self.alerts = self.alerts[-self.max_history:]

        # Broadcast
        await self._broadcast_alert(alert)

        # Log
        logger.warning(f"[{level.value.upper()}] {alert_type.value}: {message}")

        return alert

    def check_memory(self) -> Optional[Dict[str, Any]]:
        """
        Verifica uso de memória

        Returns:
            Dict com info ou None se OK
        """
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            if memory_percent > self.memory_threshold:
                return {
                    "memory_percent": memory_percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "threshold": self.memory_threshold
                }
        except Exception as e:
            logger.error(f"Erro ao verificar memória: {e}")

        return None

    def check_disk(self) -> Optional[Dict[str, Any]]:
        """
        Verifica espaço em disco

        Returns:
            Dict com info ou None se OK
        """
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            if disk_percent > self.disk_threshold:
                return {
                    "disk_percent": disk_percent,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_total_gb": disk.total / (1024**3),
                    "disk_free_gb": disk.free / (1024**3),
                    "threshold": self.disk_threshold
                }
        except Exception as e:
            logger.error(f"Erro ao verificar disco: {e}")

        return None

    def track_inference_time(self, inference_time_ms: float):
        """
        Regista tempo de inferência

        Args:
            inference_time_ms: Tempo em milissegundos
        """
        self.inference_times.append(inference_time_ms)

        # Limitar amostras
        if len(self.inference_times) > self.max_inference_samples:
            self.inference_times = self.inference_times[-self.max_inference_samples:]

    def check_inference_performance(self) -> Optional[Dict[str, Any]]:
        """
        Verifica performance de inferência

        Returns:
            Dict com info ou None se OK
        """
        if len(self.inference_times) < 10:
            return None  # Amostras insuficientes

        try:
            avg_time = sum(self.inference_times) / len(self.inference_times)

            if avg_time > self.inference_time_threshold:
                return {
                    "avg_inference_ms": avg_time,
                    "threshold_ms": self.inference_time_threshold,
                    "samples": len(self.inference_times)
                }
        except Exception as e:
            logger.error(f"Erro ao verificar performance: {e}")

        return None

    async def run_checks(self):
        """Executa todas as verificações e gera alertas se necessário"""

        # 1. Verificar memória
        memory_info = self.check_memory()
        if memory_info:
            await self.create_alert(
                alert_type=AlertType.HIGH_MEMORY,
                level=AlertLevel.WARNING,
                message=f"Uso de memória elevado: {memory_info['memory_percent']:.1f}%",
                metadata=memory_info
            )

        # 2. Verificar disco
        disk_info = self.check_disk()
        if disk_info:
            await self.create_alert(
                alert_type=AlertType.DISK_FULL,
                level=AlertLevel.WARNING,
                message=f"Disco quase cheio: {disk_info['disk_percent']:.1f}%",
                metadata=disk_info
            )

        # 3. Verificar performance de inferência
        inference_info = self.check_inference_performance()
        if inference_info:
            await self.create_alert(
                alert_type=AlertType.SLOW_INFERENCE,
                level=AlertLevel.WARNING,
                message=f"Inferência lenta: {inference_info['avg_inference_ms']:.0f}ms (avg)",
                metadata=inference_info
            )

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Marca alerta como acknowledged

        Args:
            alert_id: ID do alerta

        Returns:
            True se sucesso
        """
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now().isoformat()
                logger.info(f"Alerta {alert_id} acknowledged")
                return True

        logger.warning(f"Alerta {alert_id} não encontrado")
        return False

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        Retorna alertas não acknowledged

        Returns:
            Lista de alertas ativos
        """
        return [
            alert.to_dict()
            for alert in self.alerts
            if not alert.acknowledged
        ]

    def get_all_alerts(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retorna todos os alertas

        Args:
            limit: Número máximo de alertas (mais recentes)

        Returns:
            Lista de alertas
        """
        alerts = self.alerts[::-1]  # Mais recentes primeiro

        if limit:
            alerts = alerts[:limit]

        return [alert.to_dict() for alert in alerts]

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de alertas

        Returns:
            Dict com estatísticas
        """
        total = len(self.alerts)
        active = len([a for a in self.alerts if not a.acknowledged])

        by_type = {}
        by_level = {}

        for alert in self.alerts:
            # Por tipo
            type_key = alert.type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            # Por nível
            level_key = alert.level.value
            by_level[level_key] = by_level.get(level_key, 0) + 1

        return {
            "total_alerts": total,
            "active_alerts": active,
            "acknowledged_alerts": total - active,
            "by_type": by_type,
            "by_level": by_level,
            "current_memory_percent": psutil.virtual_memory().percent,
            "current_disk_percent": psutil.disk_usage('/').percent,
            "avg_inference_ms": sum(self.inference_times) / len(self.inference_times) if self.inference_times else 0
        }

    def clear_old_alerts(self, days: int = 7):
        """
        Remove alertas antigos

        Args:
            days: Idade máxima em dias
        """
        cutoff = datetime.now() - timedelta(days=days)

        original_count = len(self.alerts)
        self.alerts = [
            alert for alert in self.alerts
            if datetime.fromisoformat(alert.timestamp) > cutoff
        ]

        removed = original_count - len(self.alerts)
        if removed > 0:
            logger.info(f"Removidos {removed} alertas antigos (>{days} dias)")


# Instância global
_alert_manager = None


def get_alert_manager() -> AlertManager:
    """Retorna instância global do AlertManager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Background task para monitorização contínua
async def alert_monitoring_task(interval_seconds: int = 60):
    """
    Task assíncrona para monitorização contínua

    Args:
        interval_seconds: Intervalo entre verificações
    """
    manager = get_alert_manager()
    logger.info(f"Alert monitoring task iniciada (intervalo: {interval_seconds}s)")

    while True:
        try:
            await manager.run_checks()
        except Exception as e:
            logger.error(f"Erro no monitoring task: {e}")

        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    # Teste do AlertManager
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("ALERT MANAGER - Teste")
    print("=" * 60)

    async def test():
        manager = AlertManager()

        # Teste 1: Alerta de memória
        print("\n1. Teste de alerta de memória...")
        await manager.create_alert(
            AlertType.HIGH_MEMORY,
            AlertLevel.WARNING,
            "Teste de memória alta",
            metadata={"memory_percent": 87.5}
        )

        # Teste 2: Verificações automáticas
        print("\n2. Executando verificações automáticas...")
        await manager.run_checks()

        # Teste 3: Estatísticas
        print("\n3. Estatísticas:")
        stats = manager.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

        # Teste 4: Alertas ativos
        print("\n4. Alertas ativos:")
        active = manager.get_active_alerts()
        print(f"   Total: {len(active)}")

        # Teste 5: Acknowledge
        if active:
            print("\n5. Acknowledging primeiro alerta...")
            manager.acknowledge_alert(active[0]['id'])
            print(f"   Alertas ativos restantes: {len(manager.get_active_alerts())}")

    asyncio.run(test())
