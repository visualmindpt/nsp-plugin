-- ImplicitFeedback.lua
-- Sistema de feedback implícito automático para NSP Plugin
-- Detecta edições manuais após aplicação da AI e envia feedback automaticamente

local LrApplication = import 'LrApplication'
local LrLogger = import 'LrLogger'
local LrTasks = import 'LrTasks'
local LrPrefs = import 'LrPrefs'

local Common = require 'Common'
local JSON = require 'json'

local logger = LrLogger('NSPPlugin.ImplicitFeedback')
logger:enable("logfile")

-- ============================================================================
-- MÓDULO
-- ============================================================================
local ImplicitFeedback = {}
local private = {}

-- Armazenamento global de sessões ativas (photo_id → session_data)
-- NOTA: Estas sessões não persistem entre restarts do Lightroom
private.active_sessions = {}

-- Configuração de detecção de edições
private.DETECTION_CONFIG = {
    CHECK_DELAY_SECONDS = 30,      -- Tempo de espera antes de verificar edições
    DELTA_THRESHOLD = 5.0,         -- Diferença mínima em qualquer slider para considerar edição
    MAX_SESSION_AGE_SECONDS = 3600 -- Expirar sessões após 1 hora
}

-- ============================================================================
-- FUNÇÕES PRIVADAS
-- ============================================================================

-- Calcula a diferença absoluta máxima entre dois vectores
function private.calculate_max_delta(vector_ai, vector_final)
    local max_delta = 0.0

    for slider_name, ai_value in pairs(vector_ai) do
        local final_value = vector_final[slider_name] or 0
        local delta = math.abs(final_value - ai_value)

        if delta > max_delta then
            max_delta = delta
        end
    end

    return max_delta
end

-- Remove sessões expiradas (limpeza de memória)
function private.cleanup_expired_sessions()
    local current_time = os.time()
    local expired_ids = {}

    for photo_id, session in pairs(private.active_sessions) do
        local age = current_time - session.timestamp
        if age > private.DETECTION_CONFIG.MAX_SESSION_AGE_SECONDS then
            table.insert(expired_ids, photo_id)
        end
    end

    for _, photo_id in ipairs(expired_ids) do
        logger:trace("A remover sessão expirada para photo_id: " .. photo_id)
        private.active_sessions[photo_id] = nil
    end

    if #expired_ids > 0 then
        logger:info("Limpeza de sessões: " .. #expired_ids .. " sessões expiradas removidas")
    end
end

-- Verifica se a foto ainda existe no catálogo
function private.is_photo_valid(photo)
    if not photo then
        return false
    end

    -- Tenta aceder a uma propriedade básica para verificar se o objecto é válido
    local success = pcall(function()
        local _ = photo.path
    end)

    return success
end

-- Envia feedback implícito para o servidor
function private.send_feedback_to_server(session_data, vector_final)
    logger:trace("A enviar feedback implícito para session_uuid: " .. session_data.session_uuid)

    -- Converter vectores para arrays ordenados
    local vector_before_array = Common.vector_to_array(session_data.vector_before)
    local vector_ai_array = Common.vector_to_array(session_data.vector_ai)
    local vector_final_array = Common.vector_to_array(vector_final)

    -- Construir payload
    local payload = {
        session_uuid = session_data.session_uuid,
        photo_hash = session_data.photo_hash,
        vector_before = vector_before_array,
        vector_ai = vector_ai_array,
        vector_final = vector_final_array,
        model_version = session_data.model_version,
        exif_data = session_data.exif_data,
        photo_category = nil -- Pode ser adicionado futuramente
    }

    -- Enviar para o servidor (assíncrono, não bloquear UI)
    local response, err = Common.post_json("/feedback/implicit", payload)

    if err then
        logger:error("Falha ao enviar feedback implícito: " .. tostring(err.message or err))
        return false
    else
        logger:info("Feedback implícito enviado com sucesso - session_uuid: " .. session_data.session_uuid)
        return true
    end
end

-- ============================================================================
-- FUNÇÕES PÚBLICAS
-- ============================================================================

-- Inicia uma nova sessão de tracking de feedback
-- Parâmetros:
--   photo: objecto LrPhoto
--   vector_before: tabela com estado dos sliders ANTES da AI
--   vector_ai: tabela com estado dos sliders retornados pela AI
--   model_version: string identificador do modelo (ex: "nn")
function ImplicitFeedback.start_session(photo, vector_before, vector_ai, model_version)
    if not private.is_photo_valid(photo) then
        logger:error("start_session: photo inválida")
        return false
    end

    -- Gerar identificadores únicos
    local session_uuid = Common.generate_uuid()
    local photo_hash = Common.calculate_photo_hash(photo)
    local photo_id = tostring(photo.localIdentifier) -- ID único da foto no catálogo

    -- Recolher EXIF data
    local raw_meta = photo:getRawMetadata()
    local format_meta = photo:getFormattedMetadata()

    local width, height = 0, 0
    local dims_value = format_meta.dimensions

    if type(dims_value) == "string" then
        width, height = string.match(dims_value, "(%d+)%s*x%s*(%d+)")
        width = tonumber(width) or 0
        height = tonumber(height) or 0
    elseif type(dims_value) == "table" then
        width = dims_value.width or 0
        height = dims_value.height or 0
    end

    local exif_data = {
        iso = tonumber(raw_meta.isoSpeedRating) or 0,
        width = width,
        height = height
    }

    -- Criar dados da sessão
    local session_data = {
        session_uuid = session_uuid,
        photo_hash = photo_hash,
        photo_id = photo_id,
        vector_before = vector_before,
        vector_ai = vector_ai,
        model_version = model_version,
        exif_data = exif_data,
        timestamp = os.time(),
        photo = photo -- Guardar referência (pode tornar-se inválida)
    }

    -- Armazenar sessão
    private.active_sessions[photo_id] = session_data

    logger:info(string.format(
        "Sessão de feedback iniciada - session_uuid: %s, photo_id: %s, model: %s",
        session_uuid, photo_id, model_version
    ))

    -- Agendar verificação automática após delay
    ImplicitFeedback.schedule_check(photo_id)

    return true
end

-- Agenda verificação de edições após delay configurado
function ImplicitFeedback.schedule_check(photo_id)
    local delay = private.DETECTION_CONFIG.CHECK_DELAY_SECONDS

    logger:trace("A agendar verificação de edições para photo_id: " .. photo_id .. " em " .. delay .. " segundos")

    -- Executar verificação em background após delay
    LrTasks.startAsyncTask(function()
        LrTasks.sleep(delay)

        -- Executar verificação
        ImplicitFeedback.check_and_send(photo_id)
    end)
end

-- Verifica se houve edições manuais e envia feedback se detectado
function ImplicitFeedback.check_and_send(photo_id)
    -- Limpar sessões expiradas primeiro
    private.cleanup_expired_sessions()

    -- Verificar se existe sessão activa
    local session_data = private.active_sessions[photo_id]
    if not session_data then
        logger:trace("check_and_send: Nenhuma sessão activa para photo_id: " .. photo_id)
        return false
    end

    -- Verificar se a foto ainda é válida
    local photo = session_data.photo
    if not private.is_photo_valid(photo) then
        logger:warn("check_and_send: Foto já não é válida, a remover sessão - photo_id: " .. photo_id)
        private.active_sessions[photo_id] = nil
        return false
    end

    -- Recolher estado actual dos sliders
    local vector_final = Common.collect_develop_vector(photo)

    -- Detectar se houve edições significativas
    local max_delta = private.calculate_max_delta(session_data.vector_ai, vector_final)

    logger:trace(string.format(
        "Verificação de edições - photo_id: %s, max_delta: %.2f, threshold: %.2f",
        photo_id, max_delta, private.DETECTION_CONFIG.DELTA_THRESHOLD
    ))

    -- Se delta > threshold, enviar feedback
    if max_delta >= private.DETECTION_CONFIG.DELTA_THRESHOLD then
        logger:info(string.format(
            "Edições detectadas (delta: %.2f) - A enviar feedback implícito para photo_id: %s",
            max_delta, photo_id
        ))

        -- Enviar feedback de forma assíncrona
        LrTasks.startAsyncTask(function()
            local success = private.send_feedback_to_server(session_data, vector_final)

            if success then
                -- Remover sessão após envio bem-sucedido
                private.active_sessions[photo_id] = nil
                logger:trace("Sessão removida após envio bem-sucedido - photo_id: " .. photo_id)
            end
        end)

        return true
    else
        logger:trace("Nenhuma edição significativa detectada - photo_id: " .. photo_id)
        -- Manter sessão activa (pode haver edições futuras)
        return false
    end
end

-- Força o envio de feedback para uma foto específica (uso manual)
function ImplicitFeedback.force_send(photo)
    if not private.is_photo_valid(photo) then
        logger:error("force_send: photo inválida")
        return false
    end

    local photo_id = tostring(photo.localIdentifier)
    local session_data = private.active_sessions[photo_id]

    if not session_data then
        logger:warn("force_send: Nenhuma sessão activa para esta foto")
        return false
    end

    local vector_final = Common.collect_develop_vector(photo)

    logger:info("Envio forçado de feedback - photo_id: " .. photo_id)

    local success = private.send_feedback_to_server(session_data, vector_final)

    if success then
        private.active_sessions[photo_id] = nil
    end

    return success
end

-- Retorna informação de debug sobre sessões activas
function ImplicitFeedback.get_active_sessions_info()
    local count = 0
    for _ in pairs(private.active_sessions) do
        count = count + 1
    end

    return {
        active_count = count,
        sessions = private.active_sessions
    }
end

-- Limpa todas as sessões activas (uso em testes ou reset)
function ImplicitFeedback.clear_all_sessions()
    logger:info("A limpar todas as sessões activas de feedback")
    private.active_sessions = {}
end

-- ============================================================================
-- EXPORT
-- ============================================================================

return ImplicitFeedback
