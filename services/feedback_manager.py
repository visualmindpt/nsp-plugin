"""
services/feedback_manager.py

Gestor central do sistema de feedback granular para re-treino inteligente.
Responsável por processar, validar, calcular métricas e armazenar feedback.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from services.db_utils import get_db_connection
from services.feedback_schemas import (
    ExplicitFeedbackRequest,
    FeedbackProcessingResult,
    GranularFeedbackRequest,
    ImplicitFeedbackRequest,
)
from slider_config import ALL_SLIDER_NAMES, SLIDER_NAME_TO_INDEX, SLIDER_RANGES

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeedbackManager:
    """
    Gestor de feedback granular para o sistema de re-treino.

    Responsabilidades:
    - Processar feedback granular (slider a slider)
    - Calcular deltas, confidence scores e feedback quality
    - Detetar outliers usando métodos estatísticos
    - Armazenar feedback na base de dados
    - Fornecer feedback validado para re-treino

    Atributos:
        db_path: Caminho para a base de dados SQLite
        confidence_threshold: Threshold mínimo de confiança (default da config)
        outlier_std_multiplier: Multiplicador de desvio padrão para outliers
    """

    def __init__(
        self,
        db_path: Path,
        confidence_threshold: Optional[float] = None,
        outlier_std_multiplier: Optional[float] = None
    ):
        """
        Inicializa o FeedbackManager.

        Args:
            db_path: Caminho para o ficheiro da base de dados
            confidence_threshold: Threshold de confiança (se None, usa da config)
            outlier_std_multiplier: Multiplicador de std para outliers (se None, usa da config)
        """
        self.db_path = db_path

        # Carregar configuração da base de dados
        self._load_config()

        # Override com parâmetros se fornecidos
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
        if outlier_std_multiplier is not None:
            self.outlier_std_multiplier = outlier_std_multiplier

        logger.info(
            f"FeedbackManager inicializado | "
            f"confidence_threshold={self.confidence_threshold:.2f} | "
            f"outlier_std_multiplier={self.outlier_std_multiplier:.1f}"
        )

    def _load_config(self) -> None:
        """Carrega configuração de re-treino da base de dados."""
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT confidence_threshold, outlier_std_multiplier, "
                    "min_delta_threshold FROM retraining_config WHERE id = 1"
                )
                row = cursor.fetchone()

                if row:
                    self.confidence_threshold = row['confidence_threshold']
                    self.outlier_std_multiplier = row['outlier_std_multiplier']
                    self.min_delta_threshold = row['min_delta_threshold']
                else:
                    # Defaults se não existir configuração
                    self.confidence_threshold = 0.6
                    self.outlier_std_multiplier = 3.0
                    self.min_delta_threshold = 1.0
                    logger.warning("Configuração não encontrada, usando defaults")

        except sqlite3.Error as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            # Usar defaults em caso de erro
            self.confidence_threshold = 0.6
            self.outlier_std_multiplier = 3.0
            self.min_delta_threshold = 1.0

    # ========================================================================
    # PROCESSAMENTO DE FEEDBACK
    # ========================================================================

    def process_feedback(
        self,
        feedback: GranularFeedbackRequest
    ) -> FeedbackProcessingResult:
        """
        Processa feedback granular do utilizador.

        Fluxo:
        1. Calcular deltas (user_value - predicted_value)
        2. Identificar sliders editados vs aceites
        3. Calcular confidence scores
        4. Calcular feedback quality
        5. Detetar outliers
        6. Guardar na base de dados

        Args:
            feedback: Request de feedback granular

        Returns:
            FeedbackProcessingResult com IDs e estatísticas

        Raises:
            ValueError: Se dados inválidos
            sqlite3.Error: Se erro na base de dados
        """
        logger.info(
            f"Processando feedback | record_id={feedback.original_record_id} | "
            f"session_id={feedback.session_id} | sliders_editados={len(feedback.edited_sliders)}"
        )

        try:
            # 1. Calcular deltas
            deltas = self._calculate_deltas(feedback.edited_sliders)

            # 2. Identificar sliders editados
            edited_slider_indices = self._identify_edited_sliders(feedback.edited_sliders)

            # 3. Calcular confidence scores
            confidence_scores = self._calculate_confidence_scores(
                feedback.edited_sliders,
                deltas
            )

            # 4. Calcular feedback quality global
            feedback_quality = self._calculate_feedback_quality(
                deltas,
                confidence_scores
            )

            # 5. Detetar outliers
            outlier_flags = self._check_outliers(
                feedback.edited_sliders,
                deltas
            )

            # 6. Guardar na base de dados
            feedback_ids = self._save_to_database(
                feedback=feedback,
                deltas=deltas,
                confidence_scores=confidence_scores,
                feedback_quality=feedback_quality,
                outlier_flags=outlier_flags
            )

            # Estatísticas
            validated_count = sum(
                1 for i, outlier in enumerate(outlier_flags)
                if not outlier and confidence_scores[i] >= self.confidence_threshold
            )
            outlier_count = sum(outlier_flags)

            logger.info(
                f"Feedback processado | "
                f"ids={len(feedback_ids)} | "
                f"validated={validated_count} | "
                f"outliers={outlier_count} | "
                f"quality={feedback_quality:.3f}"
            )

            return FeedbackProcessingResult(
                success=True,
                feedback_ids=feedback_ids,
                total_feedbacks=len(feedback_ids),
                validated_count=validated_count,
                outlier_count=outlier_count,
                message=f"Feedback processado com sucesso. Quality score: {feedback_quality:.3f}"
            )

        except Exception as e:
            logger.error(f"Erro ao processar feedback: {e}", exc_info=True)
            return FeedbackProcessingResult(
                success=False,
                feedback_ids=[],
                total_feedbacks=0,
                validated_count=0,
                outlier_count=0,
                message=f"Erro ao processar feedback: {str(e)}"
            )

    def process_explicit_feedback(
        self,
        feedback: ExplicitFeedbackRequest
    ) -> FeedbackProcessingResult:
        """
        Processa feedback explícito (vetor completo de 38 valores).

        Converte feedback explícito em formato granular e processa.

        Args:
            feedback: Request de feedback explícito

        Returns:
            FeedbackProcessingResult
        """
        logger.info(
            f"Processando feedback explícito | record_id={feedback.original_record_id}"
        )

        # Converter para formato granular
        from services.feedback_schemas import SliderFeedbackItem

        edited_sliders = []
        for i in range(38):
            if abs(feedback.corrected_values[i] - feedback.predicted_values[i]) > 0.001:
                # Slider foi editado
                edited_sliders.append(SliderFeedbackItem(
                    slider_name=ALL_SLIDER_NAMES[i],
                    predicted_value=feedback.predicted_values[i],
                    user_value=feedback.corrected_values[i],
                    time_to_edit_seconds=None
                ))

        # Se nenhum slider foi editado, feedback implícito de aceitação
        if not edited_sliders:
            logger.info("Nenhum slider editado - feedback implícito de aceitação")
            return FeedbackProcessingResult(
                success=True,
                feedback_ids=[],
                total_feedbacks=0,
                validated_count=0,
                outlier_count=0,
                message="Feedback implícito: todos os valores aceites"
            )

        # Criar request granular
        granular_request = GranularFeedbackRequest(
            original_record_id=feedback.original_record_id,
            session_id=feedback.session_id,
            edited_sliders=edited_sliders,
            all_predicted_values=feedback.predicted_values
        )

        return self.process_feedback(granular_request)

    def process_implicit_feedback(
        self,
        feedback: ImplicitFeedbackRequest
    ) -> FeedbackProcessingResult:
        """
        Processa feedback implícito (aceitação sem edição).

        Feedback implícito pode ser valioso para indicar que o modelo
        está a prever bem esses sliders.

        Args:
            feedback: Request de feedback implícito

        Returns:
            FeedbackProcessingResult
        """
        logger.info(
            f"Processando feedback implícito | record_id={feedback.original_record_id} | "
            f"time_to_accept={feedback.time_to_accept_seconds}s"
        )

        # Para feedback implícito, não guardamos individualmente
        # Mas podemos atualizar estatísticas ou usar para métricas
        # Por agora, apenas logamos e retornamos sucesso

        return FeedbackProcessingResult(
            success=True,
            feedback_ids=[],
            total_feedbacks=0,
            validated_count=0,
            outlier_count=0,
            message=f"Feedback implícito registado (aceitação em {feedback.time_to_accept_seconds}s)"
        )

    # ========================================================================
    # CÁLCULOS DE MÉTRICAS
    # ========================================================================

    def _calculate_deltas(
        self,
        edited_sliders: List
    ) -> List[float]:
        """
        Calcula deltas entre valores previstos e corrigidos.

        Args:
            edited_sliders: Lista de SliderFeedbackItem

        Returns:
            Lista de deltas (user_value - predicted_value)
        """
        deltas = []
        for slider in edited_sliders:
            delta = slider.user_value - slider.predicted_value
            deltas.append(delta)

        return deltas

    def _identify_edited_sliders(
        self,
        edited_sliders: List
    ) -> List[int]:
        """
        Identifica índices dos sliders editados.

        Args:
            edited_sliders: Lista de SliderFeedbackItem

        Returns:
            Lista de índices dos sliders editados
        """
        indices = []
        for slider in edited_sliders:
            idx = SLIDER_NAME_TO_INDEX.get(slider.slider_name)
            if idx is not None:
                indices.append(idx)

        return indices

    def _calculate_confidence_scores(
        self,
        edited_sliders: List,
        deltas: List[float]
    ) -> List[float]:
        """
        Calcula scores de confiança para cada feedback.

        Confidence score baseia-se em:
        1. Magnitude do delta (deltas grandes = mais confiança na correção)
        2. Tempo até editar (edições rápidas = maior certeza)
        3. Consistência com histórico de feedbacks similares

        Args:
            edited_sliders: Lista de SliderFeedbackItem
            deltas: Lista de deltas calculados

        Returns:
            Lista de confidence scores (0-1)
        """
        confidence_scores = []

        for i, (slider, delta) in enumerate(zip(edited_sliders, deltas)):
            # Componente 1: Magnitude do delta (normalizada)
            abs_delta = abs(delta)
            slider_range = SLIDER_RANGES[slider.slider_name]
            range_size = slider_range['max'] - slider_range['min']
            delta_ratio = min(abs_delta / range_size, 1.0)  # Normalizar

            # Deltas maiores indicam maior confiança na correção
            # Usar função sigmoide para mapear [0, 1] -> [0.3, 1.0]
            magnitude_score = 0.3 + 0.7 * (1 / (1 + np.exp(-10 * (delta_ratio - 0.1))))

            # Componente 2: Tempo até editar (se disponível)
            time_score = 1.0  # Default
            if slider.time_to_edit_seconds is not None:
                # Edições rápidas (< 2s) = alta confiança
                # Edições lentas (> 10s) = menor confiança
                time_seconds = slider.time_to_edit_seconds
                if time_seconds < 2.0:
                    time_score = 1.0
                elif time_seconds > 10.0:
                    time_score = 0.7
                else:
                    # Interpolação linear entre 2s e 10s
                    time_score = 1.0 - 0.3 * (time_seconds - 2.0) / 8.0

            # Componente 3: Consistência (por agora, peso neutro)
            # TODO: Implementar análise de histórico
            consistency_score = 1.0

            # Score final (média ponderada)
            confidence = (
                0.5 * magnitude_score +
                0.3 * time_score +
                0.2 * consistency_score
            )

            confidence_scores.append(float(confidence))

        return confidence_scores

    def _calculate_feedback_quality(
        self,
        deltas: List[float],
        confidence_scores: List[float]
    ) -> float:
        """
        Calcula qualidade global do feedback.

        Feedback quality é uma métrica agregada que considera:
        - Número de sliders editados
        - Magnitude média dos deltas
        - Confidence scores médios
        - Consistência dos deltas

        Args:
            deltas: Lista de deltas
            confidence_scores: Lista de confidence scores

        Returns:
            Feedback quality score (0-1)
        """
        if not deltas:
            return 0.0

        # Componente 1: Número de edições (mais edições = mais informativo)
        # Normalizar: 1 edição = 0.3, 5+ edições = 1.0
        num_edits = len(deltas)
        edit_count_score = min(0.3 + 0.7 * (num_edits / 5.0), 1.0)

        # Componente 2: Magnitude média dos deltas
        abs_deltas = [abs(d) for d in deltas]
        avg_abs_delta = np.mean(abs_deltas)

        # Normalizar pela magnitude típica (assumindo deltas significativos > 5)
        magnitude_score = min(avg_abs_delta / 10.0, 1.0)

        # Componente 3: Confidence médio
        avg_confidence = np.mean(confidence_scores)

        # Componente 4: Consistência (baixo desvio padrão = maior consistência)
        if len(deltas) > 1:
            delta_std = np.std(abs_deltas)
            # Normalizar: std baixo (<5) = alta consistência
            consistency_score = max(0.5, 1.0 - (delta_std / 20.0))
        else:
            consistency_score = 1.0

        # Score final (média ponderada)
        quality = (
            0.2 * edit_count_score +
            0.3 * magnitude_score +
            0.3 * avg_confidence +
            0.2 * consistency_score
        )

        return float(quality)

    def _check_outliers(
        self,
        edited_sliders: List,
        deltas: List[float]
    ) -> List[bool]:
        """
        Deteta outliers usando métodos estatísticos.

        Métodos aplicados:
        1. Z-score: delta > mean ± (std_multiplier * std)
        2. IQR (Interquartile Range): delta fora de [Q1-1.5*IQR, Q3+1.5*IQR]
        3. Range check: delta excede limites físicos do slider

        Args:
            edited_sliders: Lista de SliderFeedbackItem
            deltas: Lista de deltas

        Returns:
            Lista de flags boolean (True = outlier)
        """
        outlier_flags = []

        # Obter histórico de deltas para cada slider da base de dados
        slider_deltas_history = self._get_slider_deltas_history()

        for slider, delta in zip(edited_sliders, deltas):
            is_outlier = False

            slider_name = slider.slider_name
            historical_deltas = slider_deltas_history.get(slider_name, [])

            # Método 1: Z-score (se temos histórico suficiente)
            if len(historical_deltas) >= 10:
                historical_deltas_with_current = historical_deltas + [delta]
                mean = np.mean(historical_deltas_with_current)
                std = np.std(historical_deltas_with_current)

                if std > 0:
                    z_score = abs((delta - mean) / std)
                    if z_score > self.outlier_std_multiplier:
                        logger.warning(
                            f"Outlier detectado (Z-score) | "
                            f"slider={slider_name} | delta={delta:.2f} | "
                            f"z_score={z_score:.2f}"
                        )
                        is_outlier = True

            # Método 2: IQR (se temos histórico suficiente)
            if not is_outlier and len(historical_deltas) >= 20:
                q1 = np.percentile(historical_deltas, 25)
                q3 = np.percentile(historical_deltas, 75)
                iqr = q3 - q1

                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                if delta < lower_bound or delta > upper_bound:
                    logger.warning(
                        f"Outlier detectado (IQR) | "
                        f"slider={slider_name} | delta={delta:.2f} | "
                        f"bounds=[{lower_bound:.2f}, {upper_bound:.2f}]"
                    )
                    is_outlier = True

            # Método 3: Range check (sempre aplicado)
            slider_range = SLIDER_RANGES[slider_name]
            range_size = slider_range['max'] - slider_range['min']
            abs_delta = abs(delta)

            # Se delta excede 80% do range, muito suspeito
            if abs_delta > 0.8 * range_size:
                logger.warning(
                    f"Outlier detectado (range) | "
                    f"slider={slider_name} | delta={delta:.2f} | "
                    f"range_size={range_size:.2f}"
                )
                is_outlier = True

            outlier_flags.append(is_outlier)

        return outlier_flags

    def _get_slider_deltas_history(self) -> Dict[str, List[float]]:
        """
        Obtém histórico de deltas por slider da base de dados.

        Returns:
            Dicionário {slider_name: [delta1, delta2, ...]}
        """
        history = {}

        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                # Obter últimos 100 deltas por slider (não outliers)
                cursor.execute("""
                    SELECT slider_name, delta_value
                    FROM granular_feedback
                    WHERE is_outlier = 0
                    ORDER BY feedback_timestamp DESC
                    LIMIT 1000
                """)

                rows = cursor.fetchall()

                for row in rows:
                    slider_name = row['slider_name']
                    delta = row['delta_value']

                    if slider_name not in history:
                        history[slider_name] = []

                    # Limitar a 100 por slider
                    if len(history[slider_name]) < 100:
                        history[slider_name].append(delta)

        except sqlite3.Error as e:
            logger.error(f"Erro ao obter histórico de deltas: {e}")

        return history

    # ========================================================================
    # PERSISTÊNCIA
    # ========================================================================

    def _save_to_database(
        self,
        feedback: GranularFeedbackRequest,
        deltas: List[float],
        confidence_scores: List[float],
        feedback_quality: float,
        outlier_flags: List[bool]
    ) -> List[int]:
        """
        Guarda feedback na base de dados.

        Args:
            feedback: Request original
            deltas: Deltas calculados
            confidence_scores: Confidence scores calculados
            feedback_quality: Qualidade global
            outlier_flags: Flags de outliers

        Returns:
            Lista de IDs dos feedbacks inseridos

        Raises:
            sqlite3.Error: Se erro na base de dados
        """
        feedback_ids = []

        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                # Verificar se record original existe
                cursor.execute(
                    "SELECT id FROM records WHERE id = ?",
                    (feedback.original_record_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(
                        f"Record original {feedback.original_record_id} não encontrado"
                    )

                # Inserir cada slider editado
                for i, slider in enumerate(feedback.edited_sliders):
                    slider_idx = SLIDER_NAME_TO_INDEX[slider.slider_name]

                    # Determinar se é validado automaticamente
                    validated = (
                        not outlier_flags[i] and
                        confidence_scores[i] >= self.confidence_threshold
                    )

                    cursor.execute("""
                        INSERT INTO granular_feedback (
                            original_record_id,
                            session_id,
                            slider_name,
                            slider_index,
                            predicted_value,
                            user_value,
                            delta_value,
                            was_edited,
                            edit_order,
                            time_to_edit_seconds,
                            confidence_score,
                            feedback_quality,
                            is_outlier,
                            validated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        feedback.original_record_id,
                        feedback.session_id,
                        slider.slider_name,
                        slider_idx,
                        slider.predicted_value,
                        slider.user_value,
                        deltas[i],
                        1,  # was_edited = True
                        i + 1,  # edit_order (1-based)
                        slider.time_to_edit_seconds,
                        confidence_scores[i],
                        feedback_quality,
                        1 if outlier_flags[i] else 0,
                        1 if validated else 0
                    ))

                    feedback_ids.append(cursor.lastrowid)

                logger.info(
                    f"Feedback guardado | "
                    f"record_id={feedback.original_record_id} | "
                    f"session_id={feedback.session_id} | "
                    f"count={len(feedback_ids)}"
                )

        except sqlite3.Error as e:
            logger.error(f"Erro ao guardar feedback: {e}", exc_info=True)
            raise

        return feedback_ids

    # ========================================================================
    # QUERIES PARA RE-TREINO
    # ========================================================================

    def get_validated_feedback_for_training(
        self,
        min_quality: Optional[float] = None,
        max_count: Optional[int] = None,
        exclude_outliers: bool = True
    ) -> List[Dict]:
        """
        Obtém feedback validado pronto para re-treino.

        Args:
            min_quality: Qualidade mínima de feedback (default: da config)
            max_count: Máximo de feedbacks a retornar
            exclude_outliers: Se True, exclui outliers

        Returns:
            Lista de dicionários com feedback validado
        """
        if min_quality is None:
            # Carregar da config
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT min_feedback_quality FROM retraining_config WHERE id = 1"
                )
                row = cursor.fetchone()
                min_quality = row['min_feedback_quality'] if row else 0.7

        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        gf.*,
                        r.image_path,
                        r.exif,
                        r.develop_vector
                    FROM granular_feedback gf
                    JOIN records r ON gf.original_record_id = r.id
                    WHERE
                        gf.used_in_training = 0
                        AND gf.validated = 1
                        AND gf.feedback_quality >= ?
                """

                params = [min_quality]

                if exclude_outliers:
                    query += " AND gf.is_outlier = 0"

                query += " ORDER BY gf.feedback_timestamp DESC"

                if max_count:
                    query += " LIMIT ?"
                    params.append(max_count)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                feedbacks = []
                for row in rows:
                    feedbacks.append({
                        'id': row['id'],
                        'original_record_id': row['original_record_id'],
                        'session_id': row['session_id'],
                        'slider_name': row['slider_name'],
                        'slider_index': row['slider_index'],
                        'predicted_value': row['predicted_value'],
                        'user_value': row['user_value'],
                        'delta_value': row['delta_value'],
                        'confidence_score': row['confidence_score'],
                        'feedback_quality': row['feedback_quality'],
                        'image_path': row['image_path'],
                        'exif': row['exif'],
                        'develop_vector': row['develop_vector'],
                        'feedback_timestamp': row['feedback_timestamp']
                    })

                logger.info(
                    f"Feedback para treino obtido | "
                    f"count={len(feedbacks)} | "
                    f"min_quality={min_quality:.2f}"
                )

                return feedbacks

        except sqlite3.Error as e:
            logger.error(f"Erro ao obter feedback para treino: {e}")
            return []

    def mark_feedback_as_used(self, feedback_ids: List[int]) -> bool:
        """
        Marca feedbacks como usados em treino.

        Args:
            feedback_ids: Lista de IDs de feedback

        Returns:
            True se sucesso, False caso contrário
        """
        if not feedback_ids:
            return True

        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                placeholders = ','.join('?' * len(feedback_ids))
                cursor.execute(
                    f"UPDATE granular_feedback SET used_in_training = 1 "
                    f"WHERE id IN ({placeholders})",
                    feedback_ids
                )

                logger.info(f"Feedback marcado como usado | count={len(feedback_ids)}")
                return True

        except sqlite3.Error as e:
            logger.error(f"Erro ao marcar feedback como usado: {e}")
            return False


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['FeedbackManager']
