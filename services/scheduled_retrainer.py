"""
Scheduled Retraining System
Sistema de re-treino agendado automático

Features:
- Verifica periodicamente se há feedback suficiente
- Executa re-treino automaticamente quando necessário
- Mantém histórico de re-treinos
- Notificações via log e WebSocket
- Backup automático de modelos antigos
- Pode rodar como daemon ou via cron

Uso:
    # Como daemon (roda continuamente)
    python -m services.scheduled_retrainer --daemon --interval 24

    # Como cron job (executa uma vez)
    python -m services.scheduled_retrainer --check-and-retrain

    # Crontab example (diariamente às 3h)
    0 3 * * * cd /path/to/project && python -m services.scheduled_retrainer --check-and-retrain

Data: 21 Novembro 2025
"""

import logging
import time
import argparse
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import asyncio

logger = logging.getLogger(__name__)


class ScheduledRetrainer:
    """
    Sistema de re-treino agendado

    Verifica periodicamente se há feedback suficiente e executa re-treino
    """

    def __init__(
        self,
        min_samples: int = 50,
        check_interval_hours: int = 24,
        backup_models: bool = True,
        notify_alerts: bool = True
    ):
        """
        Args:
            min_samples: Número mínimo de feedbacks para triggerar re-treino
            check_interval_hours: Intervalo entre verificações (horas)
            backup_models: Se True, faz backup de modelos antigos
            notify_alerts: Se True, envia alertas via WebSocket
        """
        self.min_samples = min_samples
        self.check_interval_hours = check_interval_hours
        self.backup_models = backup_models
        self.notify_alerts = notify_alerts

        # Paths
        self.project_root = Path(__file__).resolve().parent.parent
        self.models_dir = self.project_root / "models"
        self.backups_dir = self.models_dir / "backups"
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        # Histórico
        self.history_file = self.models_dir / "retraining_history.json"
        self.history = self._load_history()

        # Estado
        self.last_check = None
        self.is_running = False

        logger.info(f"ScheduledRetrainer inicializado: min_samples={min_samples}, interval={check_interval_hours}h")

    def _load_history(self) -> list:
        """Carrega histórico de re-treinos"""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return []

    def _save_history(self):
        """Salva histórico de re-treinos"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def check_feedback_availability(self) -> Dict[str, Any]:
        """
        Verifica se há feedback suficiente para re-treino

        Returns:
            Dict com informações sobre feedback disponível
        """
        try:
            from services.ai_core.feedback_collector import FeedbackCollector

            db_path = self.project_root / "data" / "feedback.db"
            if not db_path.exists():
                return {
                    "available": False,
                    "reason": "feedback database not found",
                    "samples": 0
                }

            collector = FeedbackCollector(feedback_db_path=db_path)
            stats = collector.get_stats()

            samples_with_feedback = stats.get("predictions_with_feedback", 0)

            return {
                "available": samples_with_feedback >= self.min_samples,
                "samples": samples_with_feedback,
                "min_required": self.min_samples,
                "ready_for_retraining": samples_with_feedback >= self.min_samples
            }

        except Exception as e:
            logger.error(f"Erro ao verificar feedback: {e}")
            return {
                "available": False,
                "reason": f"error: {e}",
                "samples": 0
            }

    def backup_current_models(self) -> Optional[Path]:
        """
        Faz backup dos modelos atuais

        Returns:
            Path do backup ou None se falhou
        """
        if not self.backup_models:
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.backups_dir / f"models_backup_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Arquivos a fazer backup
            model_files = [
                "best_preset_classifier.pth",
                "best_refinement_model.pth",
                "scaler_stat.pkl",
                "scaler_deep.pkl",
                "scaler_deltas.pkl",
                "preset_centers.json",
                "delta_columns.json"
            ]

            backed_up = []
            for model_file in model_files:
                src = self.models_dir / model_file
                if src.exists():
                    dst = backup_dir / model_file
                    shutil.copy2(src, dst)
                    backed_up.append(model_file)

            logger.info(f"✓ Backup criado: {len(backed_up)} arquivos em {backup_dir}")
            return backup_dir

        except Exception as e:
            logger.error(f"Erro ao fazer backup: {e}")
            return None

    def execute_retraining(self) -> Dict[str, Any]:
        """
        Executa processo de re-treino

        Returns:
            Dict com resultados do re-treino
        """
        logger.info("=" * 60)
        logger.info("EXECUTANDO RE-TREINO AUTOMÁTICO")
        logger.info("=" * 60)

        start_time = datetime.now()
        result = {
            "start_time": start_time.isoformat(),
            "status": "started"
        }

        try:
            # 1. Backup de modelos
            backup_path = self.backup_current_models()
            if backup_path:
                result["backup_path"] = str(backup_path)

            # 2. Executar auto_train pipeline
            logger.info("Executando pipeline de treino...")

            sys.path.insert(0, str(self.project_root / "scripts"))
            from scripts.auto_train import AutoTrainPipeline

            pipeline = AutoTrainPipeline(
                quick_mode=False,  # Re-treino completo
                skip_quality_check=False,
                force_retrain=True
            )

            pipeline_result = pipeline.run()

            # 3. Verificar sucesso
            if pipeline_result.get("success"):
                result["status"] = "success"
                result["message"] = "Re-treino completo com sucesso"
                logger.info("✓ Re-treino completo com sucesso!")
            else:
                result["status"] = "failed"
                result["error"] = pipeline_result.get("error", "Unknown error")
                logger.error(f"❌ Re-treino falhou: {result['error']}")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            logger.error(f"❌ Erro durante re-treino: {e}", exc_info=True)

        # Tempo total
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()

        # Adicionar ao histórico
        self.history.append(result)
        self._save_history()

        # Notificar via alertas
        if self.notify_alerts:
            asyncio.run(self._send_retraining_alert(result))

        return result

    async def _send_retraining_alert(self, result: Dict[str, Any]):
        """
        Envia alerta sobre re-treino via AlertManager

        Args:
            result: Resultados do re-treino
        """
        try:
            from services.alert_manager import get_alert_manager, AlertType, AlertLevel

            manager = get_alert_manager()

            if result["status"] == "success":
                await manager.create_alert(
                    alert_type=AlertType.SYSTEM,
                    level=AlertLevel.INFO,
                    message=f"Re-treino automático completo com sucesso ({result['duration_seconds']:.0f}s)",
                    metadata=result,
                    force=True
                )
            else:
                await manager.create_alert(
                    alert_type=AlertType.TRAINING_FAILED,
                    level=AlertLevel.ERROR,
                    message=f"Re-treino automático falhou: {result.get('error', 'Unknown')}",
                    metadata=result,
                    force=True
                )

        except Exception as e:
            logger.warning(f"Erro ao enviar alerta: {e}")

    def check_and_retrain(self) -> Dict[str, Any]:
        """
        Verifica feedback e executa re-treino se necessário

        Returns:
            Dict com resultado da verificação/re-treino
        """
        self.last_check = datetime.now()

        logger.info("\n" + "=" * 60)
        logger.info("VERIFICAÇÃO AGENDADA DE RE-TREINO")
        logger.info("=" * 60)
        logger.info(f"Timestamp: {self.last_check.isoformat()}")

        # Verificar feedback
        feedback_check = self.check_feedback_availability()

        logger.info(f"Feedback disponível: {feedback_check['samples']}/{feedback_check['min_required']}")

        if not feedback_check["ready_for_retraining"]:
            logger.info("✓ Feedback insuficiente, não é necessário re-treino ainda")
            return {
                "checked": True,
                "retrained": False,
                "reason": "insufficient_feedback",
                "feedback_check": feedback_check
            }

        # Executar re-treino
        logger.info("⚡ Feedback suficiente! Iniciando re-treino...")
        retrain_result = self.execute_retraining()

        return {
            "checked": True,
            "retrained": True,
            "feedback_check": feedback_check,
            "retrain_result": retrain_result
        }

    def run_daemon(self):
        """
        Executa como daemon (loop contínuo)

        Verifica periodicamente e re-treina quando necessário
        """
        logger.info("=" * 60)
        logger.info("SCHEDULED RETRAINER DAEMON - INICIADO")
        logger.info("=" * 60)
        logger.info(f"Intervalo de verificação: {self.check_interval_hours}h")
        logger.info(f"Min samples: {self.min_samples}")

        self.is_running = True

        try:
            while self.is_running:
                try:
                    # Verificar e re-treinar se necessário
                    result = self.check_and_retrain()

                    # Aguardar próximo intervalo
                    sleep_seconds = self.check_interval_hours * 3600
                    logger.info(f"\nPróxima verificação em {self.check_interval_hours}h...")
                    time.sleep(sleep_seconds)

                except KeyboardInterrupt:
                    logger.info("\n⚠️  Daemon interrompido pelo utilizador")
                    break
                except Exception as e:
                    logger.error(f"❌ Erro no loop do daemon: {e}", exc_info=True)
                    # Aguardar 1h antes de tentar novamente
                    logger.info("Aguardando 1h antes de retry...")
                    time.sleep(3600)

        finally:
            self.is_running = False
            logger.info("Daemon parado")

    def get_history(self, limit: Optional[int] = None) -> list:
        """
        Retorna histórico de re-treinos

        Args:
            limit: Número máximo de entradas (None=todas)

        Returns:
            Lista de re-treinos (mais recentes primeiro)
        """
        history = sorted(self.history, key=lambda x: x.get("start_time", ""), reverse=True)

        if limit:
            history = history[:limit]

        return history

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de re-treinos

        Returns:
            Dict com estatísticas
        """
        total = len(self.history)
        successful = len([r for r in self.history if r.get("status") == "success"])
        failed = len([r for r in self.history if r.get("status") == "failed"])

        last_retrain = self.history[-1] if self.history else None

        return {
            "total_retrains": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "last_retrain": last_retrain,
            "last_check": self.last_check.isoformat() if self.last_check else None
        }


def main():
    """Main function para CLI"""
    parser = argparse.ArgumentParser(
        description="Scheduled Retraining System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Executar como daemon (loop contínuo)"
    )

    parser.add_argument(
        "--check-and-retrain",
        action="store_true",
        help="Verificar e re-treinar se necessário (para cron)"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=24,
        help="Intervalo entre verificações em horas (default: 24)"
    )

    parser.add_argument(
        "--min-samples",
        type=int,
        default=50,
        help="Número mínimo de feedbacks para re-treino (default: 50)"
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Não fazer backup de modelos antigos"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostrar estatísticas de re-treinos"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Criar retrainer
    retrainer = ScheduledRetrainer(
        min_samples=args.min_samples,
        check_interval_hours=args.interval,
        backup_models=not args.no_backup
    )

    # Executar ação
    if args.stats:
        # Mostrar estatísticas
        stats = retrainer.get_stats()
        print("\n" + "=" * 60)
        print("RETRAINING STATISTICS")
        print("=" * 60)
        for key, value in stats.items():
            print(f"{key}: {value}")
        print("=" * 60)

    elif args.daemon:
        # Executar como daemon
        retrainer.run_daemon()

    elif args.check_and_retrain:
        # Verificar e re-treinar (para cron)
        result = retrainer.check_and_retrain()

        # Exit code
        if result.get("retrained") and result["retrain_result"]["status"] == "failed":
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
