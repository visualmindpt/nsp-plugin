-- ============================================================================
-- Migration: 001_feedback_granular.sql
-- Descrição: Sistema de Feedback Granular para Re-treino Inteligente
-- Versão: 1.0
-- Data: 2025-11-12
-- ============================================================================
--
-- Este script implementa a infraestrutura completa para feedback granular,
-- incluindo:
-- - Tabela de feedback detalhado por slider
-- - Tabela de histórico de re-treinos
-- - Tabela de configurações de re-treino
-- - Tabela de métricas de qualidade de feedback
-- - Índices otimizados para performance
--
-- O script é idempotente - pode ser executado múltiplas vezes sem erros.
-- ============================================================================

-- ============================================================================
-- 1. TABELA: granular_feedback
-- ============================================================================
-- Armazena feedback granular a nível de slider individual
-- Cada linha representa um ajuste do utilizador num slider específico
-- ============================================================================

CREATE TABLE IF NOT EXISTS granular_feedback (
    -- Identificação única do feedback
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Referência ao record original
    original_record_id INTEGER NOT NULL,

    -- Metadados da sessão de feedback
    session_id TEXT NOT NULL,                    -- ID da sessão de edição
    feedback_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Informação do slider editado
    slider_name TEXT NOT NULL,                   -- Nome do slider (ex: 'exposure')
    slider_index INTEGER NOT NULL,               -- Índice do slider (0-37)

    -- Valores do slider
    predicted_value REAL NOT NULL,               -- Valor previsto pelo modelo
    user_value REAL NOT NULL,                    -- Valor corrigido pelo utilizador
    delta_value REAL NOT NULL,                   -- user_value - predicted_value

    -- Metadados de contexto
    was_edited INTEGER NOT NULL DEFAULT 1,       -- 1 se editado, 0 se aceite
    edit_order INTEGER,                          -- Ordem de edição (1º, 2º, 3º slider editado)
    time_to_edit_seconds REAL,                   -- Tempo até editar (feedback implícito)

    -- Scores de confiança e qualidade
    confidence_score REAL,                       -- Confiança no feedback (0-1)
    feedback_quality REAL,                       -- Qualidade do feedback (0-1)
    is_outlier INTEGER DEFAULT 0,                -- 1 se outlier, 0 se normal

    -- Flags de processamento
    used_in_training INTEGER DEFAULT 0,          -- 1 se já usado em re-treino
    validated INTEGER DEFAULT 0,                 -- 1 se validado manualmente

    -- Constraints
    FOREIGN KEY (original_record_id) REFERENCES records(id) ON DELETE CASCADE,
    CHECK (delta_value = user_value - predicted_value),
    CHECK (was_edited IN (0, 1)),
    CHECK (is_outlier IN (0, 1)),
    CHECK (used_in_training IN (0, 1)),
    CHECK (validated IN (0, 1)),
    CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    CHECK (feedback_quality IS NULL OR (feedback_quality >= 0 AND feedback_quality <= 1))
);

-- ============================================================================
-- 2. TABELA: retraining_history
-- ============================================================================
-- Histórico de todos os re-treinos executados
-- Permite tracking e análise de evolução do modelo
-- ============================================================================

CREATE TABLE IF NOT EXISTS retraining_history (
    -- Identificação única do re-treino
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Timing
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    duration_seconds REAL,

    -- Tipo de re-treino
    trigger_type TEXT NOT NULL,                  -- 'manual', 'threshold', 'scheduled'

    -- Dados utilizados
    feedback_count INTEGER NOT NULL,             -- Nº de feedbacks usados
    feedback_ids TEXT,                           -- JSON array de IDs usados
    training_samples INTEGER,                    -- Nº total de samples no treino

    -- Métricas de treino
    train_loss REAL,
    validation_loss REAL,
    train_mae REAL,
    validation_mae REAL,

    -- Métricas por slider (JSON)
    slider_metrics TEXT,                         -- JSON: {slider: {mae, mse, r2}}

    -- Configuração usada
    config_snapshot TEXT,                        -- JSON snapshot da config

    -- Resultados
    model_path TEXT,                             -- Caminho do novo modelo
    status TEXT NOT NULL,                        -- 'success', 'failed', 'running'
    error_message TEXT,                          -- Mensagem de erro se falhou

    -- Metadados
    triggered_by TEXT,                           -- 'user', 'system', 'scheduler'
    notes TEXT,                                  -- Notas adicionais

    -- Constraints
    CHECK (trigger_type IN ('manual', 'threshold', 'scheduled')),
    CHECK (status IN ('success', 'failed', 'running', 'cancelled'))
);

-- ============================================================================
-- 3. TABELA: retraining_config
-- ============================================================================
-- Configuração do sistema de re-treino
-- Uma única linha com a configuração atual
-- ============================================================================

CREATE TABLE IF NOT EXISTS retraining_config (
    -- Apenas uma linha de configuração
    id INTEGER PRIMARY KEY CHECK (id = 1),

    -- Thresholds para trigger automático
    min_feedback_count INTEGER NOT NULL DEFAULT 50,
    min_feedback_quality REAL NOT NULL DEFAULT 0.7,
    max_outlier_percentage REAL NOT NULL DEFAULT 0.15,

    -- Configuração de qualidade
    confidence_threshold REAL NOT NULL DEFAULT 0.6,
    min_delta_threshold REAL NOT NULL DEFAULT 1.0,

    -- Configuração de outlier detection
    outlier_std_multiplier REAL NOT NULL DEFAULT 3.0,

    -- Scheduling
    auto_retrain_enabled INTEGER NOT NULL DEFAULT 0,
    check_interval_hours INTEGER NOT NULL DEFAULT 24,

    -- Última verificação
    last_check_at DATETIME,
    last_retrain_at DATETIME,

    -- Metadados
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,

    -- Constraints
    CHECK (min_feedback_count > 0),
    CHECK (min_feedback_quality >= 0 AND min_feedback_quality <= 1),
    CHECK (max_outlier_percentage >= 0 AND max_outlier_percentage <= 1),
    CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    CHECK (outlier_std_multiplier > 0),
    CHECK (auto_retrain_enabled IN (0, 1)),
    CHECK (check_interval_hours > 0)
);

-- ============================================================================
-- 4. TABELA: feedback_quality_metrics
-- ============================================================================
-- Métricas agregadas de qualidade de feedback por sessão/período
-- Útil para dashboards e análise de padrões de utilizador
-- ============================================================================

CREATE TABLE IF NOT EXISTS feedback_quality_metrics (
    -- Identificação
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Período de agregação
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,

    -- Métricas de volume
    total_feedbacks INTEGER NOT NULL DEFAULT 0,
    validated_feedbacks INTEGER NOT NULL DEFAULT 0,
    outlier_feedbacks INTEGER NOT NULL DEFAULT 0,

    -- Métricas de qualidade
    avg_confidence_score REAL,
    avg_feedback_quality REAL,
    avg_delta_magnitude REAL,

    -- Distribuição por slider (JSON)
    slider_distribution TEXT,                    -- JSON: {slider: count}

    -- Top sliders editados (JSON)
    most_edited_sliders TEXT,                    -- JSON: [{slider, count, avg_delta}]

    -- Metadados
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (period_end >= period_start),
    CHECK (total_feedbacks >= 0),
    CHECK (validated_feedbacks >= 0 AND validated_feedbacks <= total_feedbacks),
    CHECK (outlier_feedbacks >= 0 AND outlier_feedbacks <= total_feedbacks)
);

-- ============================================================================
-- 5. ÍNDICES OPTIMIZADOS
-- ============================================================================
-- Índices para garantir queries rápidas nas operações mais comuns
-- ============================================================================

-- Índice para queries por record_id (lookup de feedback de uma imagem)
CREATE INDEX IF NOT EXISTS idx_granular_feedback_record_id
    ON granular_feedback(original_record_id);

-- Índice para queries por session_id (feedback de uma sessão)
CREATE INDEX IF NOT EXISTS idx_granular_feedback_session
    ON granular_feedback(session_id);

-- Índice para queries temporais (feedback recente)
CREATE INDEX IF NOT EXISTS idx_granular_feedback_timestamp
    ON granular_feedback(feedback_timestamp DESC);

-- Índice para filtrar feedback validado e não usado
CREATE INDEX IF NOT EXISTS idx_granular_feedback_training
    ON granular_feedback(used_in_training, validated, is_outlier)
    WHERE used_in_training = 0;

-- Índice composto para análise por slider
CREATE INDEX IF NOT EXISTS idx_granular_feedback_slider_analysis
    ON granular_feedback(slider_name, was_edited, is_outlier);

-- Índice para histórico de re-treinos por status
CREATE INDEX IF NOT EXISTS idx_retraining_history_status
    ON retraining_history(status, started_at DESC);

-- Índice para histórico por tipo de trigger
CREATE INDEX IF NOT EXISTS idx_retraining_history_trigger
    ON retraining_history(trigger_type, started_at DESC);

-- Índice para métricas de qualidade por período
CREATE INDEX IF NOT EXISTS idx_feedback_quality_period
    ON feedback_quality_metrics(period_start, period_end);

-- ============================================================================
-- 6. INSERIR CONFIGURAÇÃO DEFAULT
-- ============================================================================
-- Insere configuração default apenas se não existir
-- ============================================================================

INSERT OR IGNORE INTO retraining_config (
    id,
    min_feedback_count,
    min_feedback_quality,
    max_outlier_percentage,
    confidence_threshold,
    min_delta_threshold,
    outlier_std_multiplier,
    auto_retrain_enabled,
    check_interval_hours,
    updated_by
) VALUES (
    1,                  -- id (única linha)
    50,                 -- min_feedback_count
    0.7,                -- min_feedback_quality
    0.15,               -- max_outlier_percentage (15%)
    0.6,                -- confidence_threshold
    1.0,                -- min_delta_threshold
    3.0,                -- outlier_std_multiplier (3 sigma)
    0,                  -- auto_retrain_enabled (desligado por default)
    24,                 -- check_interval_hours
    'system_init'       -- updated_by
);

-- ============================================================================
-- 7. VIEWS ÚTEIS
-- ============================================================================
-- Views para facilitar queries comuns
-- ============================================================================

-- View: Feedback pronto para treino
CREATE VIEW IF NOT EXISTS v_feedback_ready_for_training AS
SELECT
    gf.*,
    r.image_path,
    r.exif
FROM granular_feedback gf
JOIN records r ON gf.original_record_id = r.id
WHERE
    gf.used_in_training = 0
    AND gf.is_outlier = 0
    AND gf.confidence_score >= (SELECT confidence_threshold FROM retraining_config WHERE id = 1)
ORDER BY gf.feedback_timestamp DESC;

-- View: Estatísticas de feedback por slider
-- Nota: SQLite não tem STDEV nativo, removido da view
CREATE VIEW IF NOT EXISTS v_slider_feedback_stats AS
SELECT
    slider_name,
    slider_index,
    COUNT(*) as total_edits,
    SUM(CASE WHEN was_edited = 1 THEN 1 ELSE 0 END) as edit_count,
    AVG(ABS(delta_value)) as avg_abs_delta,
    MIN(delta_value) as min_delta,
    MAX(delta_value) as max_delta,
    AVG(confidence_score) as avg_confidence,
    SUM(CASE WHEN is_outlier = 1 THEN 1 ELSE 0 END) as outlier_count
FROM granular_feedback
WHERE was_edited = 1
GROUP BY slider_name, slider_index
ORDER BY slider_index;

-- View: Resumo de re-treinos recentes
CREATE VIEW IF NOT EXISTS v_recent_retrainings AS
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
WHERE status IN ('success', 'running')
ORDER BY started_at DESC
LIMIT 20;

-- ============================================================================
-- 8. TRIGGERS
-- ============================================================================
-- Triggers automáticos para manutenção de dados
-- ============================================================================

-- Trigger: Atualizar timestamp de updated_at em retraining_config
CREATE TRIGGER IF NOT EXISTS trg_retraining_config_updated
AFTER UPDATE ON retraining_config
BEGIN
    UPDATE retraining_config
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- Trigger: Validar consistency ao inserir feedback
CREATE TRIGGER IF NOT EXISTS trg_validate_feedback_insert
BEFORE INSERT ON granular_feedback
BEGIN
    -- Verificar se slider_index está no range válido (0-37)
    SELECT CASE
        WHEN NEW.slider_index < 0 OR NEW.slider_index > 37 THEN
            RAISE(ABORT, 'slider_index deve estar entre 0 e 37')
    END;

    -- Verificar se delta_value está correto
    SELECT CASE
        WHEN ABS((NEW.user_value - NEW.predicted_value) - NEW.delta_value) > 0.0001 THEN
            RAISE(ABORT, 'delta_value inconsistente com user_value - predicted_value')
    END;
END;

-- ============================================================================
-- FIM DA MIGRATION 001
-- ============================================================================

-- Verificação final: listar todas as tabelas criadas
SELECT 'Migration 001 completed successfully!' as status;
SELECT name, type FROM sqlite_master
WHERE type IN ('table', 'view', 'index', 'trigger')
  AND name LIKE '%feedback%' OR name LIKE '%retrain%'
ORDER BY type, name;
