"""
Advanced Monitoring System
Monitorização avançada de GPU, modelo, e sistema

Features:
- GPU monitoring (uso, memória, temperatura) via NVIDIA-SMI ou PyTorch
- Métricas de modelo (latência, throughput, accuracy)
- Métricas de sistema (CPU, RAM, disco, threads, I/O)
- Histórico de métricas com janela temporal
- Agregações (média, percentis, min/max)

Data: 21 Novembro 2025
"""

import logging
import psutil
import time
import platform
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque
import threading
import subprocess

logger = logging.getLogger(__name__)


class GPUMonitor:
    """
    Monitor de GPU (suporta NVIDIA via nvidia-smi e PyTorch)
    """

    def __init__(self):
        self.gpu_available = False
        self.pytorch_available = False
        self.nvidia_smi_available = False

        # Verificar PyTorch
        try:
            import torch
            if torch.cuda.is_available():
                self.pytorch_available = True
                self.gpu_available = True
                logger.info(f"GPU PyTorch disponível: {torch.cuda.get_device_name(0)}")
        except ImportError:
            pass

        # Verificar nvidia-smi
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                self.nvidia_smi_available = True
                self.gpu_available = True
                logger.info(f"nvidia-smi disponível: {result.stdout.strip()}")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        if not self.gpu_available:
            logger.info("GPU não disponível ou não detetada")

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Obtém métricas de GPU

        Returns:
            Dict com métricas ou None se GPU não disponível
        """
        if not self.gpu_available:
            return None

        metrics = {
            "available": True,
            "timestamp": datetime.now().isoformat()
        }

        # Tentar PyTorch primeiro
        if self.pytorch_available:
            try:
                import torch
                device = torch.device('cuda:0')

                metrics.update({
                    "name": torch.cuda.get_device_name(0),
                    "memory_allocated_mb": torch.cuda.memory_allocated(0) / (1024**2),
                    "memory_reserved_mb": torch.cuda.memory_reserved(0) / (1024**2),
                    "memory_total_mb": torch.cuda.get_device_properties(0).total_memory / (1024**2),
                })

                # Calcular % de utilização de memória
                mem_used = metrics["memory_allocated_mb"]
                mem_total = metrics["memory_total_mb"]
                metrics["memory_percent"] = (mem_used / mem_total * 100) if mem_total > 0 else 0

            except Exception as e:
                logger.warning(f"Erro ao obter métricas PyTorch: {e}")

        # Complementar com nvidia-smi se disponível
        if self.nvidia_smi_available:
            try:
                # Query: utilização, temperatura, potência
                result = subprocess.run([
                    'nvidia-smi',
                    '--query-gpu=utilization.gpu,temperature.gpu,power.draw,power.limit',
                    '--format=csv,noheader,nounits'
                ], capture_output=True, text=True, timeout=2)

                if result.returncode == 0:
                    values = result.stdout.strip().split(', ')
                    if len(values) >= 4:
                        metrics.update({
                            "utilization_percent": float(values[0]),
                            "temperature_celsius": float(values[1]),
                            "power_draw_watts": float(values[2]),
                            "power_limit_watts": float(values[3])
                        })

            except (subprocess.TimeoutExpired, ValueError) as e:
                logger.warning(f"Erro ao obter métricas nvidia-smi: {e}")

        return metrics


class ModelMonitor:
    """
    Monitor de performance do modelo
    """

    def __init__(self, window_size: int = 1000):
        """
        Args:
            window_size: Tamanho da janela para métricas (número de amostras)
        """
        self.window_size = window_size

        # Métricas de latência
        self.inference_times = deque(maxlen=window_size)
        self.preprocessing_times = deque(maxlen=window_size)
        self.postprocessing_times = deque(maxlen=window_size)

        # Métricas de performance
        self.confidence_scores = deque(maxlen=window_size)
        self.preset_distribution = {}  # preset_id -> count

        # Contadores
        self.total_predictions = 0
        self.start_time = time.time()

        self._lock = threading.Lock()

    def record_inference(
        self,
        inference_time_ms: float,
        confidence: float,
        preset_id: int,
        preprocessing_time_ms: float = 0,
        postprocessing_time_ms: float = 0
    ):
        """
        Regista uma inferência

        Args:
            inference_time_ms: Tempo de inferência total
            confidence: Confiança da predição
            preset_id: ID do preset predito
            preprocessing_time_ms: Tempo de pré-processamento
            postprocessing_time_ms: Tempo de pós-processamento
        """
        with self._lock:
            self.inference_times.append(inference_time_ms)
            self.confidence_scores.append(confidence)
            self.preprocessing_times.append(preprocessing_time_ms)
            self.postprocessing_times.append(postprocessing_time_ms)

            # Distribuição de presets
            self.preset_distribution[preset_id] = self.preset_distribution.get(preset_id, 0) + 1

            self.total_predictions += 1

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtém métricas agregadas do modelo

        Returns:
            Dict com métricas
        """
        with self._lock:
            if not self.inference_times:
                return {
                    "total_predictions": 0,
                    "uptime_seconds": time.time() - self.start_time
                }

            # Latências
            inf_times = list(self.inference_times)
            conf_scores = list(self.confidence_scores)

            metrics = {
                # Contadores
                "total_predictions": self.total_predictions,
                "uptime_seconds": time.time() - self.start_time,
                "samples_in_window": len(inf_times),

                # Latência de inferência
                "inference_time_ms": {
                    "mean": sum(inf_times) / len(inf_times),
                    "min": min(inf_times),
                    "max": max(inf_times),
                    "p50": self._percentile(inf_times, 50),
                    "p95": self._percentile(inf_times, 95),
                    "p99": self._percentile(inf_times, 99)
                },

                # Confiança
                "confidence": {
                    "mean": sum(conf_scores) / len(conf_scores),
                    "min": min(conf_scores),
                    "max": max(conf_scores),
                    "p50": self._percentile(conf_scores, 50)
                },

                # Throughput
                "throughput": {
                    "predictions_per_second": self.total_predictions / (time.time() - self.start_time),
                    "avg_time_per_prediction_ms": sum(inf_times) / len(inf_times)
                },

                # Distribuição de presets
                "preset_distribution": dict(self.preset_distribution)
            }

            # Tempos de pré/pós-processamento se disponíveis
            if self.preprocessing_times and any(self.preprocessing_times):
                prep_times = [t for t in self.preprocessing_times if t > 0]
                if prep_times:
                    metrics["preprocessing_time_ms"] = {
                        "mean": sum(prep_times) / len(prep_times),
                        "min": min(prep_times),
                        "max": max(prep_times)
                    }

            if self.postprocessing_times and any(self.postprocessing_times):
                post_times = [t for t in self.postprocessing_times if t > 0]
                if post_times:
                    metrics["postprocessing_time_ms"] = {
                        "mean": sum(post_times) / len(post_times),
                        "min": min(post_times),
                        "max": max(post_times)
                    }

            return metrics

    def _percentile(self, data: List[float], p: int) -> float:
        """Calcula percentil"""
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p / 100)
        return sorted_data[min(idx, len(sorted_data) - 1)]

    def reset(self):
        """Reset das métricas"""
        with self._lock:
            self.inference_times.clear()
            self.preprocessing_times.clear()
            self.postprocessing_times.clear()
            self.confidence_scores.clear()
            self.preset_distribution.clear()
            self.total_predictions = 0
            self.start_time = time.time()


class SystemMonitor:
    """
    Monitor de métricas de sistema
    """

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtém métricas detalhadas de sistema

        Returns:
            Dict com métricas
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Memória
        memory = psutil.virtual_memory()

        # Disco
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()

        # Network
        net_io = psutil.net_io_counters()

        # Process info
        process = psutil.Process()
        process_info = {
            "pid": process.pid,
            "memory_mb": process.memory_info().rss / (1024**2),
            "cpu_percent": process.cpu_percent(),
            "num_threads": process.num_threads(),
            "num_fds": process.num_fds() if hasattr(process, 'num_fds') else None,
        }

        metrics = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.system(),
            "python_version": platform.python_version(),

            # CPU
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "frequency_mhz": cpu_freq.current if cpu_freq else None,
                "per_cpu_percent": psutil.cpu_percent(percpu=True)
            },

            # Memória
            "memory": {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "used_gb": memory.used / (1024**3),
                "percent": memory.percent,
                "swap_percent": psutil.swap_memory().percent
            },

            # Disco
            "disk": {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": disk.percent,
                "read_mb": disk_io.read_bytes / (1024**2) if disk_io else None,
                "write_mb": disk_io.write_bytes / (1024**2) if disk_io else None,
            },

            # Network
            "network": {
                "bytes_sent_mb": net_io.bytes_sent / (1024**2),
                "bytes_recv_mb": net_io.bytes_recv / (1024**2),
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            },

            # Processo
            "process": process_info
        }

        return metrics


class MonitoringCollector:
    """
    Coletor central de todas as métricas de monitorização
    """

    def __init__(self):
        self.gpu_monitor = GPUMonitor()
        self.model_monitor = ModelMonitor(window_size=1000)
        self.system_monitor = SystemMonitor()

        logger.info("MonitoringCollector inicializado")

    def record_inference(
        self,
        inference_time_ms: float,
        confidence: float,
        preset_id: int,
        preprocessing_time_ms: float = 0,
        postprocessing_time_ms: float = 0
    ):
        """
        Regista inferência no model monitor

        Args:
            inference_time_ms: Tempo de inferência
            confidence: Confiança
            preset_id: ID do preset
            preprocessing_time_ms: Tempo de pré-processamento
            postprocessing_time_ms: Tempo de pós-processamento
        """
        self.model_monitor.record_inference(
            inference_time_ms=inference_time_ms,
            confidence=confidence,
            preset_id=preset_id,
            preprocessing_time_ms=preprocessing_time_ms,
            postprocessing_time_ms=postprocessing_time_ms
        )

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Obtém todas as métricas (GPU, modelo, sistema)

        Returns:
            Dict com todas as métricas organizadas
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "gpu": self.gpu_monitor.get_metrics(),
            "model": self.model_monitor.get_metrics(),
            "system": self.system_monitor.get_metrics()
        }

    def get_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo das métricas principais

        Returns:
            Dict com métricas resumidas
        """
        all_metrics = self.get_all_metrics()

        summary = {
            "timestamp": all_metrics["timestamp"],
            "status": "healthy",
            "warnings": []
        }

        # GPU summary
        if all_metrics["gpu"]:
            gpu = all_metrics["gpu"]
            summary["gpu"] = {
                "available": True,
                "memory_percent": gpu.get("memory_percent", 0),
                "utilization_percent": gpu.get("utilization_percent", 0),
                "temperature_celsius": gpu.get("temperature_celsius", 0)
            }

            # Warnings
            if gpu.get("memory_percent", 0) > 90:
                summary["warnings"].append("GPU memory > 90%")
            if gpu.get("temperature_celsius", 0) > 80:
                summary["warnings"].append("GPU temperature > 80°C")
        else:
            summary["gpu"] = {"available": False}

        # Model summary
        model = all_metrics["model"]
        if model.get("total_predictions", 0) > 0:
            summary["model"] = {
                "total_predictions": model["total_predictions"],
                "avg_inference_ms": model["inference_time_ms"]["mean"],
                "avg_confidence": model["confidence"]["mean"],
                "throughput_per_sec": model["throughput"]["predictions_per_second"]
            }

            # Warnings
            if model["inference_time_ms"]["mean"] > 500:
                summary["warnings"].append("Avg inference time > 500ms")
            if model["confidence"]["mean"] < 0.7:
                summary["warnings"].append("Low avg confidence < 0.7")
        else:
            summary["model"] = {"total_predictions": 0}

        # System summary
        system = all_metrics["system"]
        summary["system"] = {
            "cpu_percent": system["cpu"]["percent"],
            "memory_percent": system["memory"]["percent"],
            "disk_percent": system["disk"]["percent"],
            "process_memory_mb": system["process"]["memory_mb"]
        }

        # Warnings
        if system["memory"]["percent"] > 85:
            summary["warnings"].append("System memory > 85%")
        if system["disk"]["percent"] > 90:
            summary["warnings"].append("Disk usage > 90%")
        if system["cpu"]["percent"] > 90:
            summary["warnings"].append("CPU usage > 90%")

        # Status geral
        if summary["warnings"]:
            summary["status"] = "warning"

        return summary


# Instância global
_monitoring_collector = None


def get_monitoring_collector() -> MonitoringCollector:
    """Retorna instância global do MonitoringCollector"""
    global _monitoring_collector
    if _monitoring_collector is None:
        _monitoring_collector = MonitoringCollector()
    return _monitoring_collector


if __name__ == "__main__":
    # Teste do monitoring system
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("MONITORING SYSTEM - Teste")
    print("=" * 60)

    collector = MonitoringCollector()

    # Simular algumas inferências
    print("\n1. Simulando inferências...")
    for i in range(10):
        collector.record_inference(
            inference_time_ms=150 + (i * 10),
            confidence=0.85 + (i * 0.01),
            preset_id=i % 3,
            preprocessing_time_ms=20,
            postprocessing_time_ms=10
        )

    # Obter métricas
    print("\n2. Métricas completas:")
    import json
    metrics = collector.get_all_metrics()
    print(json.dumps(metrics, indent=2))

    print("\n3. Resumo:")
    summary = collector.get_summary()
    print(json.dumps(summary, indent=2))
