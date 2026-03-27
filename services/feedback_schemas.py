"""
services/feedback_schemas.py

Pydantic models para validação de requests e responses do sistema de feedback granular.
Garante validação robusta de dados com type safety e validadores customizados.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from slider_config import ALL_SLIDER_NAMES, SLIDER_RANGES, SLIDER_NAME_TO_INDEX


# ============================================================================
# SCHEMAS DE REQUEST - Feedback
# ============================================================================


class SliderFeedbackItem(BaseModel):
    """
    Representa feedback para um slider individual.

    Atributos:
        slider_name: Nome do slider (deve estar em ALL_SLIDER_NAMES)
        predicted_value: Valor previsto pelo modelo
        user_value: Valor corrigido pelo utilizador
        time_to_edit_seconds: Tempo até o utilizador editar (opcional)
    """
    slider_name: str = Field(..., description="Nome do slider editado")
    predicted_value: float = Field(..., description="Valor previsto pelo modelo")
    user_value: float = Field(..., description="Valor corrigido pelo utilizador")
    time_to_edit_seconds: Optional[float] = Field(None, ge=0, description="Tempo até editar em segundos")

    @field_validator('slider_name')
    @classmethod
    def validate_slider_name(cls, v: str) -> str:
        """Valida se o slider_name existe."""
        if v not in ALL_SLIDER_NAMES:
            raise ValueError(
                f"slider_name '{v}' inválido. "
                f"Deve ser um de: {', '.join(ALL_SLIDER_NAMES[:5])}..."
            )
        return v

    @model_validator(mode='after')
    def validate_slider_ranges(self) -> 'SliderFeedbackItem':
        """Valida se os valores estão dentro dos ranges permitidos."""
        slider_range = SLIDER_RANGES.get(self.slider_name)
        if not slider_range:
            # Já foi validado no field_validator, mas por segurança
            return self

        min_val = slider_range['min']
        max_val = slider_range['max']

        # Validar predicted_value
        if not (min_val <= self.predicted_value <= max_val):
            raise ValueError(
                f"predicted_value {self.predicted_value} fora do range "
                f"[{min_val}, {max_val}] para slider '{self.slider_name}'"
            )

        # Validar user_value
        if not (min_val <= self.user_value <= max_val):
            raise ValueError(
                f"user_value {self.user_value} fora do range "
                f"[{min_val}, {max_val}] para slider '{self.slider_name}'"
            )

        return self


class GranularFeedbackRequest(BaseModel):
    """
    Request para submeter feedback granular (slider a slider).

    Usado quando o utilizador edita manualmente sliders individuais.

    Atributos:
        original_record_id: ID do record original da previsão
        session_id: ID único da sessão de edição
        edited_sliders: Lista de sliders editados com valores
        all_predicted_values: Todos os 38 valores previstos (opcional, para contexto)
    """
    original_record_id: int = Field(..., gt=0, description="ID do record original")
    session_id: str = Field(..., min_length=1, description="ID da sessão de edição")
    edited_sliders: List[SliderFeedbackItem] = Field(
        ...,
        min_length=1,
        description="Lista de sliders editados pelo utilizador"
    )
    all_predicted_values: Optional[List[float]] = Field(
        None,
        description="Todos os 38 valores previstos (para contexto)"
    )

    @field_validator('all_predicted_values')
    @classmethod
    def validate_predicted_values_length(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        """Valida que all_predicted_values tem exatamente 38 valores se fornecido."""
        if v is not None and len(v) != 38:
            raise ValueError(f"all_predicted_values deve ter exatamente 38 valores, recebeu {len(v)}")
        return v

    @field_validator('edited_sliders')
    @classmethod
    def validate_no_duplicate_sliders(cls, v: List[SliderFeedbackItem]) -> List[SliderFeedbackItem]:
        """Valida que não há sliders duplicados."""
        slider_names = [item.slider_name for item in v]
        if len(slider_names) != len(set(slider_names)):
            duplicates = [name for name in slider_names if slider_names.count(name) > 1]
            raise ValueError(f"Sliders duplicados encontrados: {', '.join(set(duplicates))}")
        return v


class ImplicitFeedbackRequest(BaseModel):
    """
    Request para feedback implícito (sliders aceites sem edição).

    Usado quando o utilizador aceita previsões sem modificar.

    Atributos:
        original_record_id: ID do record original da previsão
        session_id: ID único da sessão
        predicted_values: Todos os 38 valores previstos e aceites
        time_to_accept_seconds: Tempo até aceitar
    """
    original_record_id: int = Field(..., gt=0, description="ID do record original")
    session_id: str = Field(..., min_length=1, description="ID da sessão")
    predicted_values: List[float] = Field(
        ...,
        min_length=38,
        max_length=38,
        description="Todos os 38 valores previstos"
    )
    time_to_accept_seconds: Optional[float] = Field(None, ge=0, description="Tempo até aceitar")

    @field_validator('predicted_values')
    @classmethod
    def validate_predicted_values(cls, v: List[float]) -> List[float]:
        """Valida ranges dos valores previstos."""
        if len(v) != 38:
            raise ValueError(f"predicted_values deve ter exatamente 38 valores, recebeu {len(v)}")

        # Validar cada valor contra seu range
        for i, value in enumerate(v):
            slider_name = ALL_SLIDER_NAMES[i]
            slider_range = SLIDER_RANGES[slider_name]
            min_val = slider_range['min']
            max_val = slider_range['max']

            if not (min_val <= value <= max_val):
                raise ValueError(
                    f"Valor {value} no índice {i} (slider '{slider_name}') "
                    f"fora do range [{min_val}, {max_val}]"
                )

        return v


class ExplicitFeedbackRequest(BaseModel):
    """
    Request para feedback explícito (todos os 38 valores corrigidos).

    Usado quando o sistema recebe o vetor completo de valores corrigidos.

    Atributos:
        original_record_id: ID do record original
        session_id: ID da sessão
        predicted_values: Todos os 38 valores previstos
        corrected_values: Todos os 38 valores corrigidos
    """
    original_record_id: int = Field(..., gt=0, description="ID do record original")
    session_id: str = Field(..., min_length=1, description="ID da sessão")
    predicted_values: List[float] = Field(
        ...,
        min_length=38,
        max_length=38,
        description="Todos os 38 valores previstos"
    )
    corrected_values: List[float] = Field(
        ...,
        min_length=38,
        max_length=38,
        description="Todos os 38 valores corrigidos"
    )

    @model_validator(mode='after')
    def validate_values(self) -> 'ExplicitFeedbackRequest':
        """Valida que ambas as listas têm 38 valores e estão nos ranges."""
        if len(self.predicted_values) != 38:
            raise ValueError(
                f"predicted_values deve ter 38 valores, recebeu {len(self.predicted_values)}"
            )

        if len(self.corrected_values) != 38:
            raise ValueError(
                f"corrected_values deve ter 38 valores, recebeu {len(self.corrected_values)}"
            )

        # Validar ranges
        for i in range(38):
            slider_name = ALL_SLIDER_NAMES[i]
            slider_range = SLIDER_RANGES[slider_name]
            min_val = slider_range['min']
            max_val = slider_range['max']

            pred_val = self.predicted_values[i]
            corr_val = self.corrected_values[i]

            if not (min_val <= pred_val <= max_val):
                raise ValueError(
                    f"predicted_values[{i}] ({slider_name}) = {pred_val} "
                    f"fora do range [{min_val}, {max_val}]"
                )

            if not (min_val <= corr_val <= max_val):
                raise ValueError(
                    f"corrected_values[{i}] ({slider_name}) = {corr_val} "
                    f"fora do range [{min_val}, {max_val}]"
                )

        return self


# ============================================================================
# SCHEMAS DE REQUEST - Re-treino
# ============================================================================


class RetrainingTriggerRequest(BaseModel):
    """
    Request para trigger manual de re-treino.

    Atributos:
        trigger_type: Tipo de trigger ('manual', 'threshold', 'scheduled')
        min_feedback_quality: Qualidade mínima de feedback (opcional)
        max_feedbacks: Limite máximo de feedbacks a usar (opcional)
        notes: Notas adicionais sobre o re-treino
    """
    trigger_type: Literal['manual', 'threshold', 'scheduled'] = Field(
        'manual',
        description="Tipo de trigger do re-treino"
    )
    min_feedback_quality: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Qualidade mínima de feedback a considerar"
    )
    max_feedbacks: Optional[int] = Field(
        None,
        gt=0,
        description="Limite máximo de feedbacks a usar"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notas sobre o re-treino"
    )


class RetrainingConfigUpdate(BaseModel):
    """
    Request para atualizar configuração de re-treino.

    Todos os campos são opcionais - apenas os fornecidos são atualizados.
    """
    min_feedback_count: Optional[int] = Field(None, gt=0)
    min_feedback_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_outlier_percentage: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_delta_threshold: Optional[float] = Field(None, ge=0.0)
    outlier_std_multiplier: Optional[float] = Field(None, gt=0.0)
    auto_retrain_enabled: Optional[bool] = None
    check_interval_hours: Optional[int] = Field(None, gt=0)


# ============================================================================
# SCHEMAS DE RESPONSE
# ============================================================================


class FeedbackProcessingResult(BaseModel):
    """
    Response após processar feedback.

    Atributos:
        success: Se o processamento foi bem-sucedido
        feedback_ids: IDs dos feedbacks criados
        total_feedbacks: Total de feedbacks processados
        validated_count: Quantos foram validados
        outlier_count: Quantos foram marcados como outliers
        message: Mensagem descritiva
    """
    success: bool
    feedback_ids: List[int]
    total_feedbacks: int
    validated_count: int
    outlier_count: int
    message: str


class RetrainingStatus(BaseModel):
    """
    Response com status de re-treino.

    Atributos:
        status: Status atual ('idle', 'running', 'completed', 'failed')
        retraining_id: ID do re-treino (se existir)
        started_at: Quando começou
        completed_at: Quando terminou
        duration_seconds: Duração
        feedback_count: Nº de feedbacks usados
        validation_mae: MAE de validação
        message: Mensagem descritiva
    """
    status: Literal['idle', 'running', 'completed', 'failed']
    retraining_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    feedback_count: Optional[int] = None
    validation_mae: Optional[float] = None
    message: str


class FeedbackStatistics(BaseModel):
    """
    Response com estatísticas de feedback.

    Atributos:
        total_feedbacks: Total de feedbacks na base de dados
        validated_feedbacks: Quantos validados
        outlier_feedbacks: Quantos outliers
        ready_for_training: Quantos prontos para treino
        avg_confidence_score: Confiança média
        avg_feedback_quality: Qualidade média
        most_edited_sliders: Top 5 sliders mais editados
    """
    total_feedbacks: int
    validated_feedbacks: int
    outlier_feedbacks: int
    ready_for_training: int
    avg_confidence_score: Optional[float]
    avg_feedback_quality: Optional[float]
    most_edited_sliders: List[Dict[str, Any]]


class RetrainingConfigResponse(BaseModel):
    """Response com configuração atual de re-treino."""
    min_feedback_count: int
    min_feedback_quality: float
    max_outlier_percentage: float
    confidence_threshold: float
    min_delta_threshold: float
    outlier_std_multiplier: float
    auto_retrain_enabled: bool
    check_interval_hours: int
    last_check_at: Optional[datetime]
    last_retrain_at: Optional[datetime]
    updated_at: datetime


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Request schemas
    'SliderFeedbackItem',
    'GranularFeedbackRequest',
    'ImplicitFeedbackRequest',
    'ExplicitFeedbackRequest',
    'RetrainingTriggerRequest',
    'RetrainingConfigUpdate',

    # Response schemas
    'FeedbackProcessingResult',
    'RetrainingStatus',
    'FeedbackStatistics',
    'RetrainingConfigResponse',
]
