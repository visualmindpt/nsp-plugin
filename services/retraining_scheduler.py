"""
services/retraining_scheduler.py

Scheduler inteligente para retreino automático do modelo.
Monitoriza feedback acumulado e decide quando trigger retreino baseado em:
- Volume de feedback validado
- Qualidade do feedback
- Tempo desde último retreino
- Drift detection (deltas recentes)
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from services.db_utils import get_db_connection

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetrainingScheduler:
    """
    Scheduler para monitorização e trigger de retreino automático.

    Responsabilidades:
    - Verificar se há feedback suficiente para retreino
    - Calcular drift score baseado em deltas recentes
    - Validar cooldown periods para evitar retreinos excessivos
    - Fornecer estatísticas para dashboard de retreino

    Atributos:
        db_path: Caminho para a base de dados SQLite
        config: Configuração de retreino carregada da BD
    """

    def __init__(self, db_path: Path):
        """
        Inicializa o RetrainingScheduler.

        Args:
            db_path: Caminho para o ficheiro da base de dados
        """
        self.db_path = db_path
        self.config = self._load_config()

        logger.info(
            f"RetrainingScheduler inicializado | "
            f"min_feedback={self.config['min_feedback_count']} | "
            f"min_quality={self.config['min_feedback_quality']:.2f}"
        )

    def _load_config(self) -> Dict:
        """
        Carrega configuração de retreino da base de dados.

        Returns:
            Dicionário com configuração atual
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM retraining_config WHERE id = 1")
                row = cursor.fetchone()

                if not row:
                    raise ValueError("Configuração de retreino não encontrada na BD")

                return {
                    'min_feedback_count': row['min_feedback_count'],
                    'min_feedback_quality': row['min_feedback_quality'],
                    'max_outlier_percentage': row['max_outlier_percentage'],
                    'confidence_threshold': row['confidence_threshold'],
                    'min_delta_threshold': row['min_delta_threshold'],
                    'outlier_std_multiplier': row['outlier_std_multiplier'],
                    'auto_retrain_enabled': bool(row['auto_retrain_enabled']),
                    'check_interval_hours': row['check_interval_hours'],
                    'last_check_at': row['last_check_at'],
                    'last_retrain_at': row['last_retrain_at']
                }

        except sqlite3.Error as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            raise

    def refresh_config(self) -> None:
        """Recarrega configuração da base de dados."""
        self.config = self._load_config()
        logger.info("Configuração de retreino recarregada")

    # ========================================================================
    # VERIFICAÇÃO DE READINESS
    # ========================================================================

    def check_readiness(self) -> Dict:
        """
        Verifica se o sistema está pronto para retreino.

        Analisa múltiplos critérios:
        1. Volume de feedback validado suficiente
        2. Qualidade média do feedback acima do threshold
        3. Percentagem de outliers aceitável
        4. Cooldown period respeitado
        5. Drift score (opcional, indica urgência)

        Returns:
            Dicionário com estado de readiness e métricas:
            {
                'ready': bool,
                'reason': str,
                'metrics': {
                    'feedback_count': int,
                    'validated_count': int,
                    'avg_quality': float,
                    'outlier_percentage': float,
                    'drift_score': float,
                    'days_since_last_retrain': float,
                    'cooldown_remaining_hours': float
                }
            }
        """
        logger.info("Verificando readiness para retreino...")

        try:
            metrics = self._gather_metrics()

            # Critério 1: Volume de feedback
            if metrics['validated_count'] < self.config['min_feedback_count']:
                return {
                    'ready': False,
                    'reason': f"Feedback insuficiente: {metrics['validated_count']}/{self.config['min_feedback_count']}",
                    'metrics': metrics
                }

            # Critério 2: Qualidade média
            if metrics['avg_quality'] < self.config['min_feedback_quality']:
                return {
                    'ready': False,
                    'reason': f"Qualidade baixa: {metrics['avg_quality']:.3f} < {self.config['min_feedback_quality']:.3f}",
                    'metrics': metrics
                }

            # Critério 3: Percentagem de outliers
            if metrics['outlier_percentage'] > self.config['max_outlier_percentage']:
                return {
                    'ready': False,
                    'reason': f"Muitos outliers: {metrics['outlier_percentage']:.1%} > {self.config['max_outlier_percentage']:.1%}",
                    'metrics': metrics
                }

            # Critério 4: Cooldown
            if not self._check_cooldown():
                return {
                    'ready': False,
                    'reason': f"Cooldown ativo: aguardar {metrics['cooldown_remaining_hours']:.1f}h",
                    'metrics': metrics
                }

            # Todos os critérios satisfeitos
            logger.info(
                f"Sistema pronto para retreino | "
                f"feedback={metrics['validated_count']} | "
                f"quality={metrics['avg_quality']:.3f} | "
                f"drift={metrics['drift_score']:.3f}"
            )

            return {
                'ready': True,
                'reason': "Todos os critérios satisfeitos",
                'metrics': metrics
            }

        except Exception as e:
            logger.error(f"Erro ao verificar readiness: {e}", exc_info=True)
            return {
                'ready': False,
                'reason': f"Erro: {str(e)}",
                'metrics': {}
            }

    def should_trigger_retraining(self, force: bool = False) -> Tuple[bool, str]:
        """
        Decisão booleana: deve disparar retreino agora?

        Args:
            force: Se True, ignora todos os thresholds (trigger manual)

        Returns:
            Tupla (should_trigger, reason)
        """
        if force:
            logger.info("Retreino forçado (manual trigger)")
            return True, "Trigger manual forçado"

        # Verificar se auto-retrain está enabled
        if not self.config['auto_retrain_enabled']:
            return False, "Auto-retreino desativado na configuração"

        # Verificar readiness
        readiness = self.check_readiness()

        if readiness['ready']:
            # Atualizar last_check_at
            self._update_last_check()
            return True, readiness['reason']
        else:
            self._update_last_check()
            return False, readiness['reason']

    # ========================================================================
    # ESTATÍSTICAS E MÉTRICAS
    # ========================================================================

    def get_retraining_stats(self) -> Dict:
        """
        Retorna estatísticas detalhadas para dashboard de retreino.

        Returns:
            Dicionário com estatísticas completas:
            {
                'feedback': {...},
                'last_retrain': {...},
                'readiness': {...},
                'config': {...}
            }
        """
        try:
            metrics = self._gather_metrics()
            readiness = self.check_readiness()
            last_retrain = self._get_last_retrain_info()

            return {
                'feedback': {
                    'total': metrics['total_count'],
                    'validated': metrics['validated_count'],
                    'outliers': metrics['outlier_count'],
                    'avg_quality': metrics['avg_quality'],
                    'avg_confidence': metrics['avg_confidence'],
                    'ready_for_training': metrics['validated_count']
                },
                'last_retrain': last_retrain,
                'readiness': {
                    'ready': readiness['ready'],
                    'reason': readiness['reason'],
                    'drift_score': metrics['drift_score'],
                    'days_since_last': metrics['days_since_last_retrain'],
                    'cooldown_remaining_hours': metrics['cooldown_remaining_hours']
                },
                'config': {
                    'min_feedback_count': self.config['min_feedback_count'],
                    'min_feedback_quality': self.config['min_feedback_quality'],
                    'max_outlier_percentage': self.config['max_outlier_percentage'],
                    'auto_retrain_enabled': self.config['auto_retrain_enabled']
                }
            }

        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}", exc_info=True)
            return {}

    def _gather_metrics(self) -> Dict:
        """
        Reúne métricas atuais do sistema de feedback.

        Returns:
            Dicionário com métricas calculadas
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # Total de feedback não usado
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM granular_feedback
                WHERE used_in_training = 0
            """)
            total_count = cursor.fetchone()['total']

            # Feedback validado (pronto para treino)
            cursor.execute("""
                SELECT COUNT(*) as validated
                FROM granular_feedback
                WHERE used_in_training = 0
                  AND validated = 1
                  AND is_outlier = 0
                  AND confidence_score >= ?
            """, (self.config['confidence_threshold'],))
            validated_count = cursor.fetchone()['validated']

            # Outliers
            cursor.execute("""
                SELECT COUNT(*) as outliers
                FROM granular_feedback
                WHERE used_in_training = 0
                  AND is_outlier = 1
            """)
            outlier_count = cursor.fetchone()['outliers']

            # Qualidade média
            cursor.execute("""
                SELECT AVG(feedback_quality) as avg_quality,
                       AVG(confidence_score) as avg_confidence
                FROM granular_feedback
                WHERE used_in_training = 0
                  AND validated = 1
                  AND is_outlier = 0
            """)
            row = cursor.fetchone()
            avg_quality = row['avg_quality'] if row['avg_quality'] else 0.0
            avg_confidence = row['avg_confidence'] if row['avg_confidence'] else 0.0

            # Calcular percentagem de outliers
            outlier_percentage = (outlier_count / total_count) if total_count > 0 else 0.0

            # Drift score
            drift_score = self._calculate_drift_score()

            # Dias desde último retreino
            days_since_last_retrain = self._days_since_last_retrain()

            # Cooldown remaining
            cooldown_remaining_hours = self._cooldown_remaining_hours()

            return {
                'total_count': total_count,
                'validated_count': validated_count,
                'outlier_count': outlier_count,
                'avg_quality': avg_quality,
                'avg_confidence': avg_confidence,
                'outlier_percentage': outlier_percentage,
                'drift_score': drift_score,
                'days_since_last_retrain': days_since_last_retrain,
                'cooldown_remaining_hours': cooldown_remaining_hours
            }

    def _calculate_drift_score(self) -> float:
        """
        Calcula drift score baseado em deltas recentes.

        Drift score indica o quão diferentes são as correções recentes
        vs. o comportamento histórico do modelo. Score alto = modelo
        está a prever mal sistematicamente.

        Método:
        1. Obter últimos 100 feedbacks validados
        2. Calcular magnitude média dos deltas por slider
        3. Comparar com baseline (primeiros feedbacks)
        4. Score = ratio de mudança (0-1, onde 1 = muito drift)

        Returns:
            Drift score (0-1)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                # Obter deltas recentes (últimos 100)
                cursor.execute("""
                    SELECT slider_name, ABS(delta_value) as abs_delta
                    FROM granular_feedback
                    WHERE validated = 1
                      AND is_outlier = 0
                      AND used_in_training = 0
                    ORDER BY feedback_timestamp DESC
                    LIMIT 100
                """)
                recent_deltas = cursor.fetchall()

                if len(recent_deltas) < 10:
                    # Não há dados suficientes para calcular drift
                    return 0.0

                # Calcular magnitude média recente
                recent_magnitudes = [row['abs_delta'] for row in recent_deltas]
                recent_avg = np.mean(recent_magnitudes)

                # Obter baseline (primeiros 100 feedbacks após último retreino)
                last_retrain_date = self.config.get('last_retrain_at')
                if last_retrain_date:
                    cursor.execute("""
                        SELECT ABS(delta_value) as abs_delta
                        FROM granular_feedback
                        WHERE validated = 1
                          AND is_outlier = 0
                          AND feedback_timestamp > ?
                        ORDER BY feedback_timestamp ASC
                        LIMIT 100
                    """, (last_retrain_date,))
                else:
                    # Se nunca retreinou, usar primeiros 100 globalmente
                    cursor.execute("""
                        SELECT ABS(delta_value) as abs_delta
                        FROM granular_feedback
                        WHERE validated = 1
                          AND is_outlier = 0
                        ORDER BY feedback_timestamp ASC
                        LIMIT 100
                    """)

                baseline_deltas = cursor.fetchall()

                if len(baseline_deltas) < 10:
                    # Sem baseline suficiente
                    return 0.0

                baseline_magnitudes = [row['abs_delta'] for row in baseline_deltas]
                baseline_avg = np.mean(baseline_magnitudes)

                # Calcular drift score
                # Se deltas recentes são maiores que baseline, há drift
                if baseline_avg < 0.01:  # Evitar divisão por zero
                    baseline_avg = 0.01

                drift_ratio = recent_avg / baseline_avg

                # Normalizar para [0, 1]
                # drift_ratio = 1.0 → sem drift (score 0)
                # drift_ratio = 2.0 → drift alto (score ~0.5)
                # drift_ratio = 3.0 → drift muito alto (score ~0.67)
                drift_score = max(0.0, min(1.0, (drift_ratio - 1.0) / 2.0))

                logger.debug(
                    f"Drift score calculado | "
                    f"recent_avg={recent_avg:.2f} | "
                    f"baseline_avg={baseline_avg:.2f} | "
                    f"drift_score={drift_score:.3f}"
                )

                return drift_score

        except Exception as e:
            logger.error(f"Erro ao calcular drift score: {e}")
            return 0.0

    # ========================================================================
    # COOLDOWN E TIMING
    # ========================================================================

    def _check_cooldown(self) -> bool:
        """
        Verifica se o cooldown period passou.

        Cooldown previne retreinos muito frequentes, dando tempo ao modelo
        para acumular feedback suficiente.

        Returns:
            True se pode retreinar, False se ainda em cooldown
        """
        last_retrain = self.config.get('last_retrain_at')
        if not last_retrain:
            # Nunca retreinou, pode retreinar
            return True

        try:
            last_retrain_dt = datetime.fromisoformat(last_retrain)
            cooldown_hours = 12  # Fixo: 12 horas de cooldown
            cooldown_delta = timedelta(hours=cooldown_hours)

            time_since_last = datetime.now() - last_retrain_dt

            return time_since_last >= cooldown_delta

        except Exception as e:
            logger.error(f"Erro ao verificar cooldown: {e}")
            # Em caso de erro, permitir retreino
            return True

    def _cooldown_remaining_hours(self) -> float:
        """
        Calcula horas restantes de cooldown.

        Returns:
            Horas restantes (0.0 se cooldown passou)
        """
        last_retrain = self.config.get('last_retrain_at')
        if not last_retrain:
            return 0.0

        try:
            last_retrain_dt = datetime.fromisoformat(last_retrain)
            cooldown_hours = 12
            cooldown_delta = timedelta(hours=cooldown_hours)

            time_since_last = datetime.now() - last_retrain_dt
            remaining = cooldown_delta - time_since_last

            if remaining.total_seconds() <= 0:
                return 0.0

            return remaining.total_seconds() / 3600.0

        except Exception:
            return 0.0

    def _days_since_last_retrain(self) -> float:
        """
        Calcula dias desde último retreino.

        Returns:
            Dias desde último retreino (None se nunca retreinou)
        """
        last_retrain = self.config.get('last_retrain_at')
        if not last_retrain:
            return None

        try:
            last_retrain_dt = datetime.fromisoformat(last_retrain)
            delta = datetime.now() - last_retrain_dt
            return delta.total_seconds() / 86400.0  # Converter para dias

        except Exception:
            return None

    def _get_last_retrain_info(self) -> Optional[Dict]:
        """
        Obtém informação sobre o último retreino.

        Returns:
            Dicionário com info do último retreino, ou None
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT *
                    FROM retraining_history
                    WHERE status = 'success'
                    ORDER BY started_at DESC
                    LIMIT 1
                """)

                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    'id': row['id'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at'],
                    'duration_seconds': row['duration_seconds'],
                    'feedback_count': row['feedback_count'],
                    'validation_mae': row['validation_mae'],
                    'trigger_type': row['trigger_type']
                }

        except Exception as e:
            logger.error(f"Erro ao obter info de último retreino: {e}")
            return None

    # ========================================================================
    # UTILITIES
    # ========================================================================

    def _update_last_check(self) -> None:
        """Atualiza timestamp de última verificação."""
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE retraining_config
                    SET last_check_at = ?
                    WHERE id = 1
                """, (datetime.now().isoformat(),))

        except Exception as e:
            logger.error(f"Erro ao atualizar last_check_at: {e}")

    def update_last_retrain(self) -> None:
        """
        Atualiza timestamp de último retreino.

        Deve ser chamado após retreino bem-sucedido.
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE retraining_config
                    SET last_retrain_at = ?
                    WHERE id = 1
                """, (datetime.now().isoformat(),))

            logger.info("Timestamp de último retreino atualizado")

        except Exception as e:
            logger.error(f"Erro ao atualizar last_retrain_at: {e}")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['RetrainingScheduler']
