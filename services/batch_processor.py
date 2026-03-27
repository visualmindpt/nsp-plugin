# -*- coding: utf-8 -*-
"""
Batch Processor Assincrono - Sistema de job queue para processamento em background
Permite submeter batches grandes sem bloquear o cliente
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging
import json

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Estados possíveis de um job"""
    PENDING = "pending"        # Aguardando processamento
    RUNNING = "running"        # Em processamento
    COMPLETED = "completed"    # Concluído com sucesso
    FAILED = "failed"          # Falhou
    CANCELLED = "cancelled"    # Cancelado pelo utilizador


@dataclass
class BatchJob:
    """Representa um job de batch processing"""
    job_id: str
    images: List[Dict[str, Any]]  # Lista de {image_path, exif}
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_images: int = 0
    processed_images: int = 0
    successful_images: int = 0
    failed_images: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    progress_pct: float = 0.0
    eta_seconds: Optional[int] = None

    def __post_init__(self):
        self.total_images = len(self.images)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa job para dict"""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_images": self.total_images,
            "processed_images": self.processed_images,
            "successful_images": self.successful_images,
            "failed_images": self.failed_images,
            "progress_pct": self.progress_pct,
            "eta_seconds": self.eta_seconds,
            "errors": self.errors[:10]  # Limitar a 10 erros
        }


class BatchProcessor:
    """Processa batches de predições em background"""

    def __init__(self, predictor=None, max_concurrent_jobs: int = 3):
        self.predictor = predictor
        self.max_concurrent_jobs = max_concurrent_jobs
        self.jobs: Dict[str, BatchJob] = {}
        self.active_jobs: int = 0
        self._lock = asyncio.Lock()

    def create_job(self, images: List[Dict[str, Any]]) -> str:
        """
        Cria um novo job de batch

        Args:
            images: Lista de dicts com image_path e exif

        Returns:
            job_id: UUID do job criado
        """
        job_id = str(uuid.uuid4())
        job = BatchJob(
            job_id=job_id,
            images=images
        )
        self.jobs[job_id] = job
        logger.info(f"Batch job criado: {job_id} ({len(images)} imagens)")
        return job_id

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Obtém job por ID"""
        return self.jobs.get(job_id)

    async def process_job(self, job_id: str):
        """
        Processa um job em background

        Esta função corre em asyncio task separada
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job não encontrado: {job_id}")
            return

        if not self.predictor:
            logger.error(f"Predictor não disponível para job {job_id}")
            job.status = JobStatus.FAILED
            job.errors.append("Predictor AI não está inicializado")
            return

        async with self._lock:
            if self.active_jobs >= self.max_concurrent_jobs:
                logger.warning(f"Max concurrent jobs atingido. Job {job_id} aguarda...")
                return
            self.active_jobs += 1

        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            logger.info(f"Iniciando processamento do job {job_id}")

            start_time = datetime.now()

            for idx, image_data in enumerate(job.images):
                try:
                    image_path = image_data.get('image_path')
                    exif = image_data.get('exif', {})

                    if not image_path:
                        job.errors.append(f"Imagem {idx+1}: path ausente")
                        job.failed_images += 1
                        continue

                    # Fazer predição (síncron - o predictor não é async)
                    # Executar em thread pool para não bloquear event loop
                    loop = asyncio.get_event_loop()
                    prediction = await loop.run_in_executor(
                        None,
                        self.predictor.predict,
                        image_path
                    )

                    # Guardar resultado
                    result = {
                        "image_path": image_path,
                        "preset_id": prediction.get('preset_id'),
                        "preset_confidence": prediction.get('preset_confidence'),
                        "sliders": prediction.get('sliders'),
                        "prediction_id": prediction.get('prediction_id')
                    }
                    job.results.append(result)
                    job.successful_images += 1

                except Exception as e:
                    error_msg = f"Imagem {idx+1} ({Path(image_path).name if image_path else '?'}): {str(e)}"
                    logger.error(f"Job {job_id} - {error_msg}")
                    job.errors.append(error_msg)
                    job.failed_images += 1

                finally:
                    job.processed_images += 1
                    job.progress_pct = (job.processed_images / job.total_images) * 100

                    # Calcular ETA
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if job.processed_images > 0:
                        avg_time_per_image = elapsed / job.processed_images
                        remaining_images = job.total_images - job.processed_images
                        job.eta_seconds = int(avg_time_per_image * remaining_images)

                # Yield para event loop (permite outros tasks correrem)
                await asyncio.sleep(0)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            total_time = (job.completed_at - job.started_at).total_seconds()

            logger.info(
                f"Job {job_id} concluído: {job.successful_images} sucesso, "
                f"{job.failed_images} falhas em {total_time:.1f}s"
            )

        except Exception as e:
            logger.error(f"Erro ao processar job {job_id}: {e}", exc_info=True)
            job.status = JobStatus.FAILED
            job.errors.append(f"Erro crítico: {str(e)}")

        finally:
            async with self._lock:
                self.active_jobs -= 1

    async def start_job(self, job_id: str):
        """Inicia processamento de um job (non-blocking)"""
        asyncio.create_task(self.process_job(job_id))

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancela um job (apenas se ainda não iniciou)

        Returns:
            True se cancelado, False se já em execução
        """
        job = self.get_job(job_id)
        if not job:
            return False

        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            logger.info(f"Job {job_id} cancelado")
            return True

        return False

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs antigos para libertar memória"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        old_jobs = [
            job_id for job_id, job in self.jobs.items()
            if job.completed_at and job.completed_at < cutoff
        ]

        for job_id in old_jobs:
            del self.jobs[job_id]

        if old_jobs:
            logger.info(f"Removidos {len(old_jobs)} jobs antigos")

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Retorna lista de todos os jobs"""
        return [job.to_dict() for job in self.jobs.values()]

    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Retorna apenas jobs ativos (running ou pending)"""
        return [
            job.to_dict() for job in self.jobs.values()
            if job.status in [JobStatus.PENDING, JobStatus.RUNNING]
        ]


# Instância global (singleton)
_batch_processor: Optional[BatchProcessor] = None


def get_batch_processor(predictor=None, max_concurrent_jobs: int = 3) -> BatchProcessor:
    """
    Obtém instância global do batch processor

    Args:
        predictor: Instância do LightroomAIPredictor
        max_concurrent_jobs: Número máximo de jobs paralelos

    Returns:
        BatchProcessor instance
    """
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = BatchProcessor(
            predictor=predictor,
            max_concurrent_jobs=max_concurrent_jobs
        )
        logger.info("BatchProcessor inicializado")
    elif predictor is not None and _batch_processor.predictor is None:
        _batch_processor.predictor = predictor
        logger.info("Predictor associado ao BatchProcessor")

    return _batch_processor


# Exemplo de uso
if __name__ == "__main__":
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def test_batch_processor():
        # Mock predictor
        class MockPredictor:
            def predict(self, image_path):
                import time
                time.sleep(0.5)  # Simula processamento
                return {
                    'preset_id': 1,
                    'preset_confidence': 0.85,
                    'sliders': {'exposure': 0.5},
                    'prediction_id': 123
                }

        processor = get_batch_processor(predictor=MockPredictor())

        # Criar job
        images = [
            {'image_path': f'/fake/path/img_{i}.jpg', 'exif': {}}
            for i in range(10)
        ]
        job_id = processor.create_job(images)
        print(f"Job criado: {job_id}")

        # Iniciar processamento
        await processor.start_job(job_id)

        # Monitorar progresso
        while True:
            job = processor.get_job(job_id)
            print(f"Status: {job.status.value} | Progresso: {job.progress_pct:.1f}% | ETA: {job.eta_seconds}s")

            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                break

            await asyncio.sleep(1)

        # Resultado final
        print(f"\nJob concluído!")
        print(f"  Sucesso: {job.successful_images}")
        print(f"  Falhas: {job.failed_images}")
        print(f"  Erros: {job.errors}")

    asyncio.run(test_batch_processor())
