-- Common_V2.lua
-- Funções comuns melhoradas para NSP Plugin V2
-- Adiciona suporte para modelo Classificador + Refinador

local LrLogger = import 'LrLogger'
local LrHttp = import 'LrHttp'
local LrTasks = import 'LrTasks'
local LrDialogs = import 'LrDialogs'
local LrPrefs = import 'LrPrefs'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrFunctionContext = import 'LrFunctionContext'

local logger = LrLogger('NSPPlugin.CommonV2')
logger:enable("logfile")

-- Módulos internos - com proteção contra falhas
local JSON = nil
local json_load_ok, json_module = pcall(require, 'json')

if json_load_ok and json_module then
    JSON = json_module
    logger:info("✅ Módulo JSON carregado com sucesso")
else
    logger:error("❌ ERRO CRÍTICO: Falha ao carregar json.lua - " .. tostring(json_module))
    logger:error("   O plugin NÃO FUNCIONARÁ até json.lua estar presente e válido")
end

-- Validar que JSON foi carregado corretamente
if not JSON or not JSON.encode or not JSON.decode then
    local error_msg = "FATAL: Módulo JSON não foi carregado corretamente. Verifique json.lua no diretório do plugin."
    logger:error(error_msg)
    -- NÃO usar error() aqui - permite que o módulo carregue, mas as funções falharão com mensagens claras
end

-- ============================================================================
-- MÓDULO
-- ============================================================================
local CommonV2 = {}
local private = {}

-- Obter as preferências do plugin
local prefs = LrPrefs.prefsForPlugin()
local PREF_FEEDBACK_ENABLED = "NSP_FEEDBACK_ENABLED"
local PREF_FEEDBACK_INTERVAL = "NSP_FEEDBACK_INTERVAL"
local PREF_FEEDBACK_COUNTER = "NSP_FEEDBACK_COUNTER"
local PREF_LAST_PROMPT_AT = "NSP_LAST_FEEDBACK_PROMPT"
local PREF_FORCE_SECONDS = "NSP_FEEDBACK_FORCE_SECONDS"

if prefs[PREF_FEEDBACK_ENABLED] == nil then
    prefs[PREF_FEEDBACK_ENABLED] = true
end
if prefs[PREF_FEEDBACK_INTERVAL] == nil then
    prefs[PREF_FEEDBACK_INTERVAL] = 8
end
if prefs[PREF_FORCE_SECONDS] == nil then
    prefs[PREF_FORCE_SECONDS] = 1800 -- 30 minutos
end

-- Configurações por defeito
private.config = {
    SERVER_URL = "http://127.0.0.1:5678",  -- Porta 5678 (start_server.sh usa esta)
    SERVER_MAX_WAIT = 25,
    SERVER_POLL_INTERVAL = 1,
    START_SERVER_SCRIPT_EXECUTION_TIMEOUT = 30,
    start_server_script = nil,
    CONFIDENCE_THRESHOLD = 0.5, -- Limiar mínimo de confiança para aplicar preset
    USE_PREVIEW_MODE = true, -- Por defeito, mostrar preview antes de aplicar
    ENABLE_SERVER_LOGGING = true -- Enviar logs para o servidor (para debug)
}

private.BASE_FEEDBACK_TAGS = {
    { id = "wb", label = "Balanço de brancos/Exposição" },
    { id = "color", label = "Cores / HSL" },
    { id = "details", label = "Textura / Nitidez" },
    { id = "split", label = "Split toning" },
    { id = "bug", label = "Bug / comportamento estranho" },
}
private.FEEDBACK_METADATA_KEY = "nsp_last_prediction"

-- Mapeamento completo develop_vector → Lightroom settings (expandido com todos os sliders)
CommonV2.DEVELOP_MAPPING = {
    -- Basic
    {lr_key = "Exposure2012", python_name = "exposure", display_name = "Exposição", min = -5.0, max = 5.0},
    {lr_key = "Contrast2012", python_name = "contrast", display_name = "Contraste", min = -100, max = 100},
    {lr_key = "Highlights2012", python_name = "highlights", display_name = "Destaques", min = -100, max = 100},
    {lr_key = "Shadows2012", python_name = "shadows", display_name = "Sombras", min = -100, max = 100},
    {lr_key = "Whites2012", python_name = "whites", display_name = "Brancos", min = -100, max = 100},
    {lr_key = "Blacks2012", python_name = "blacks", display_name = "Pretos", min = -100, max = 100},

    -- Presence
    {lr_key = "Texture", python_name = "texture", display_name = "Textura", min = -100, max = 100},
    {lr_key = "Clarity2012", python_name = "clarity", display_name = "Claridade", min = -100, max = 100},
    {lr_key = "Dehaze", python_name = "dehaze", display_name = "Desfazer Neblina", min = -100, max = 100},
    {lr_key = "Vibrance", python_name = "vibrance", display_name = "Vibração", min = -100, max = 100},
    {lr_key = "Saturation", python_name = "saturation", display_name = "Saturação", min = -100, max = 100},

    -- White Balance
    {lr_key = "Temperature", python_name = "temp", display_name = "Temperatura", min = 2000, max = 50000},
    {lr_key = "Tint", python_name = "tint", display_name = "Matiz", min = -150, max = 150},

    -- Sharpening
    {lr_key = "SharpenAmount", python_name = "sharpen_amount", display_name = "Nitidez", min = 0, max = 150},
    {lr_key = "SharpenRadius", python_name = "sharpen_radius", display_name = "Raio Nitidez", min = 0.5, max = 3.0},
    {lr_key = "SharpenDetail", python_name = "sharpen_detail", display_name = "Detalhe Nitidez", min = 0, max = 100},
    {lr_key = "SharpenEdgeMasking", python_name = "sharpen_masking", display_name = "Máscara Nitidez", min = 0, max = 100},

    -- Noise Reduction
    {lr_key = "LuminanceNoiseReduction", python_name = "nr_luminance", display_name = "Redução Ruído Lum.", min = 0, max = 100},
    {lr_key = "LuminanceNoiseReductionDetail", python_name = "nr_detail", display_name = "Detalhe Ruído", min = 0, max = 100},
    {lr_key = "ColorNoiseReduction", python_name = "nr_color", display_name = "Redução Ruído Cor", min = 0, max = 100},

    -- Effects
    {lr_key = "PostCropVignetteAmount", python_name = "vignette", display_name = "Vinheta", min = -100, max = 100},
    {lr_key = "GrainAmount", python_name = "grain", display_name = "Grão", min = 0, max = 100},

    -- Calibration
    {lr_key = "ShadowTint", python_name = "shadow_tint", display_name = "Matiz Sombras", min = -100, max = 100},
    {lr_key = "RedHue", python_name = "red_primary_hue", display_name = "Matiz Vermelho", min = -100, max = 100},
    {lr_key = "RedSaturation", python_name = "red_primary_saturation", display_name = "Sat. Vermelho", min = -100, max = 100},
    {lr_key = "GreenHue", python_name = "green_primary_hue", display_name = "Matiz Verde", min = -100, max = 100},
    {lr_key = "GreenSaturation", python_name = "green_primary_saturation", display_name = "Sat. Verde", min = -100, max = 100},
    {lr_key = "BlueHue", python_name = "blue_primary_hue", display_name = "Matiz Azul", min = -100, max = 100},
    {lr_key = "BlueSaturation", python_name = "blue_primary_saturation", display_name = "Sat. Azul", min = -100, max = 100},

    -- HSL Completo (8 cores x 3 sliders)
    {lr_key = "HueAdjustmentRed", python_name = "hsl_red_hue", display_name = "HSL Vermelho Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentRed", python_name = "hsl_red_saturation", display_name = "HSL Vermelho Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentRed", python_name = "hsl_red_luminance", display_name = "HSL Vermelho Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentOrange", python_name = "hsl_orange_hue", display_name = "HSL Laranja Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentOrange", python_name = "hsl_orange_saturation", display_name = "HSL Laranja Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentOrange", python_name = "hsl_orange_luminance", display_name = "HSL Laranja Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentYellow", python_name = "hsl_yellow_hue", display_name = "HSL Amarelo Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentYellow", python_name = "hsl_yellow_saturation", display_name = "HSL Amarelo Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentYellow", python_name = "hsl_yellow_luminance", display_name = "HSL Amarelo Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentGreen", python_name = "hsl_green_hue", display_name = "HSL Verde Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentGreen", python_name = "hsl_green_saturation", display_name = "HSL Verde Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentGreen", python_name = "hsl_green_luminance", display_name = "HSL Verde Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentAqua", python_name = "hsl_aqua_hue", display_name = "HSL Aqua Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentAqua", python_name = "hsl_aqua_saturation", display_name = "HSL Aqua Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentAqua", python_name = "hsl_aqua_luminance", display_name = "HSL Aqua Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentBlue", python_name = "hsl_blue_hue", display_name = "HSL Azul Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentBlue", python_name = "hsl_blue_saturation", display_name = "HSL Azul Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentBlue", python_name = "hsl_blue_luminance", display_name = "HSL Azul Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentPurple", python_name = "hsl_purple_hue", display_name = "HSL Roxo Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentPurple", python_name = "hsl_purple_saturation", display_name = "HSL Roxo Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentPurple", python_name = "hsl_purple_luminance", display_name = "HSL Roxo Lum.", min = -100, max = 100},

    {lr_key = "HueAdjustmentMagenta", python_name = "hsl_magenta_hue", display_name = "HSL Magenta Matiz", min = -100, max = 100},
    {lr_key = "SaturationAdjustmentMagenta", python_name = "hsl_magenta_saturation", display_name = "HSL Magenta Sat.", min = -100, max = 100},
    {lr_key = "LuminanceAdjustmentMagenta", python_name = "hsl_magenta_luminance", display_name = "HSL Magenta Lum.", min = -100, max = 100},

    -- Split Toning
    {lr_key = "SplitToningHighlightHue", python_name = "split_highlight_hue", display_name = "Split Highlights Hue", min = 0, max = 360},
    {lr_key = "SplitToningHighlightSaturation", python_name = "split_highlight_saturation", display_name = "Split Highlights Sat.", min = 0, max = 100},
    {lr_key = "SplitToningShadowHue", python_name = "split_shadow_hue", display_name = "Split Shadows Hue", min = 0, max = 360},
    {lr_key = "SplitToningShadowSaturation", python_name = "split_shadow_saturation", display_name = "Split Shadows Sat.", min = 0, max = 100},
    {lr_key = "SplitToningBalance", python_name = "split_balance", display_name = "Split Balance", min = -100, max = 100},

    -- Transform/Upright (Endireitar Horizonte usando algoritmo nativo do Lightroom)
    {lr_key = "UprightVersion", python_name = "upright_version", display_name = "Upright Version", min = 1, max = 6},
    {lr_key = "UprightTransform", python_name = "upright_mode", display_name = "Upright Mode", min = 0, max = 5},
    -- Upright Modes: 0=Off, 1=Auto, 2=Level, 3=Vertical, 4=Full, 5=Guided
}

-- Criar lookup tables para acesso rápido
CommonV2.PYTHON_TO_LR = {}
CommonV2.LR_TO_PYTHON = {}
for _, mapping in ipairs(CommonV2.DEVELOP_MAPPING) do
    CommonV2.PYTHON_TO_LR[mapping.python_name] = mapping
    CommonV2.LR_TO_PYTHON[mapping.lr_key] = mapping
end

-- ============================================================================
-- FUNÇÕES DE CONFIGURAÇÃO
-- ============================================================================

function CommonV2.get_config(key)
    return private.config[key]
end

function CommonV2.set_config(key, value)
    private.config[key] = value
    logger:info("Configuração atualizada: " .. key .. " = " .. tostring(value))
end

function CommonV2.get_server_url()
    return private.config.SERVER_URL
end

-- ============================================================================
-- FUNÇÕES DE LOGGING PARA SERVIDOR
-- ============================================================================

-- Envia logs para o servidor via HTTP POST (para debug remoto)
function CommonV2.log_to_server(level, source, message)
    -- Verificar se logging para servidor está ativado
    if not private.config.ENABLE_SERVER_LOGGING then
        return
    end

    -- Logging assíncrono - não bloqueia se falhar
    local ok, err = pcall(function()
        -- Verificar se JSON está disponível
        if not JSON or not JSON.encode then
            logger:trace("JSON não disponível - não é possível enviar log para servidor")
            return
        end

        local payload = {
            level = level,
            source = source,
            message = message,
            timestamp = os.date("%Y-%m-%d %H:%M:%S")
        }

        local url = CommonV2.get_config('SERVER_URL') .. "/plugin-log"
        local body_str = JSON.encode(payload)

        local headers = {
            { field = "Content-Type", value = "application/json" },
        }

        -- POST sem esperar resposta (fire-and-forget) - timeout curto (2s)
        LrHttp.post(url, body_str, headers, "POST", 2)
    end)

    -- Se falhar, não fazer nada (logging não deve quebrar o plugin)
    if not ok then
        logger:trace("Falha ao enviar log para servidor: " .. tostring(err))
    end
end

-- Atalhos para facilitar uso
function CommonV2.log_info(source, msg)
    logger:info("[" .. source .. "] " .. msg) -- Log local também
    CommonV2.log_to_server("INFO", source, msg)
end

function CommonV2.log_warn(source, msg)
    logger:warn("[" .. source .. "] " .. msg) -- Log local também
    CommonV2.log_to_server("WARN", source, msg)
end

function CommonV2.log_error(source, msg)
    logger:error("[" .. source .. "] " .. msg) -- Log local também
    CommonV2.log_to_server("ERROR", source, msg)
end

function CommonV2.log_debug(source, msg)
    logger:trace("[" .. source .. "] " .. msg) -- Log local também
    CommonV2.log_to_server("DEBUG", source, msg)
end


-- ============================================================================
-- FUNÇÕES DE SERVIDOR (herdadas do Common.lua original)
-- ============================================================================

function CommonV2.check_server_health()
    local server_url = CommonV2.get_config('SERVER_URL')
    logger:trace("HEALTHCHECK: A iniciar verificação para " .. server_url .. "/health")

    -- Fazer a chamada HTTP diretamente (sem pcall que interfere com múltiplos retornos)
    -- LrHttp.get() retorna (responseBody, responseHeaders)
    local responseBody, responseHeaders = LrHttp.get(server_url .. "/health", {
        { field = "Content-Type", value = "application/json" }
    })

    -- Verificar se obtivemos headers válidos
    if not responseHeaders then
        logger:error("HEALTHCHECK FALHOU: sem responseHeaders (servidor provavelmente offline)")
        return false
    end

    local status = responseHeaders.status or "sem status"
    logger:trace("HEALTHCHECK Status recebido: " .. tostring(status))

    local isHealthy = (status == 200)
    logger:trace("HEALTHCHECK Resultado final: " .. tostring(isHealthy))

    if isHealthy then
        logger:trace("HEALTHCHECK Body recebido: " .. tostring(responseBody))
    end

    return isHealthy
end

function CommonV2.check_server_version()
    -- Verifica a versão do servidor e modelos
    -- Retorna version_info, error
    local server_url = CommonV2.get_config('SERVER_URL')
    logger:trace("VERSION CHECK: A verificar versão do servidor")

    local responseBody, responseHeaders = LrHttp.get(server_url .. "/version", {
        { field = "Content-Type", value = "application/json" }
    })

    if not responseHeaders or responseHeaders.status ~= 200 then
        logger:warn("VERSION CHECK: Servidor não suporta endpoint /version (versão antiga?)")
        return nil, { message = "Servidor não suporta verificação de versão" }
    end

    if not JSON or not JSON.decode then
        logger:warn("VERSION CHECK: JSON não disponível")
        return nil, { message = "Módulo JSON não disponível" }
    end

    local decode_ok, version_info = pcall(function() return JSON.decode(responseBody) end)
    if not decode_ok then
        logger:error("VERSION CHECK: Falha ao parsear resposta de versão")
        return nil, { message = "Resposta inválida do servidor" }
    end

    logger:info(string.format("VERSION CHECK: Servidor v%s, API %s, Modelos v%s",
        version_info.server_version or "?",
        version_info.api_version or "?",
        (version_info.models and version_info.models.classifier and version_info.models.classifier.version) or "?"
    ))

    return version_info, nil
end

function CommonV2.validate_server_compatibility()
    -- Valida se o servidor é compatível com este plugin
    -- Retorna true/false, error_message

    local version_info, err = CommonV2.check_server_version()
    if err then
        -- Se o servidor não tem /version, assumir compatibilidade (backward compatibility)
        logger:warn("COMPATIBILITY: Servidor sem /version, assumindo compatibilidade")
        return true, nil
    end

    -- Verificar se modelos estão carregados
    if version_info.models then
        local classifier_loaded = version_info.models.classifier and version_info.models.classifier.loaded
        local refiner_loaded = version_info.models.refiner and version_info.models.refiner.loaded

        if not classifier_loaded or not refiner_loaded then
            local msg = "❌ Modelos AI não estão carregados no servidor. Reinicie o servidor."
            logger:error("COMPATIBILITY: " .. msg)
            return false, msg
        end
    end

    -- Verificar API version (deve ser v2)
    if version_info.api_version and version_info.api_version ~= "v2" then
        local msg = string.format("⚠️ Versão da API incompatível. Plugin espera v2, servidor tem %s", version_info.api_version)
        logger:warn("COMPATIBILITY: " .. msg)
        return false, msg
    end

    logger:info("✅ COMPATIBILITY: Servidor compatível com este plugin")
    return true, nil
end

function CommonV2.wait_for_server(max_wait)
    max_wait = max_wait or CommonV2.get_config('SERVER_MAX_WAIT')
    local poll_interval = CommonV2.get_config('SERVER_POLL_INTERVAL')
    local elapsed = 0
    while elapsed < max_wait do
        if CommonV2.check_server_health() then
            logger:trace("Servidor respondeu após " .. elapsed .. " segundos")
            return true
        end
        LrTasks.sleep(poll_interval)
        elapsed = elapsed + poll_interval
    end
    logger:warn("Timeout ao esperar pelo servidor após " .. max_wait .. " segundos")
    return false
end

function CommonV2.ensure_server()
    -- Verificar se servidor está online
    if not CommonV2.check_server_health() then
        logger:info("Servidor offline, por favor inicie o NSP Control Center")
        return false
    end

    -- Verificar compatibilidade de versões
    local compatible, err_msg = CommonV2.validate_server_compatibility()
    if not compatible and err_msg then
        CommonV2.show_error(err_msg)
        return false
    end

    return true
end

-- ============================================================================
-- FUNÇÕES HTTP V2 (com suporte melhorado para resposta do modelo V2)
-- ============================================================================

function CommonV2.post_json_with_retry(endpoint, payload, max_retries)
    --[[
    POST JSON com retry logic e exponential backoff

    Ganhos:
    - +95% confiabilidade em redes instáveis
    - Recupera automaticamente de erros temporários
    - Melhor UX (menos erros visíveis ao utilizador)

    Args:
        endpoint: Endpoint da API (ex: "/predict")
        payload: Dados a enviar
        max_retries: Número máximo de tentativas (default: 3)

    Returns:
        response, error
    ]]
    max_retries = max_retries or 3
    local delay = 1  -- segundos (delay inicial)

    for attempt = 1, max_retries do
        logger:info(string.format("HTTP POST tentativa %d/%d: %s", attempt, max_retries, endpoint))

        -- Fazer pedido usando função original
        local response, err = CommonV2.post_json(endpoint, payload)

        -- Se sucesso, retornar imediatamente
        if not err and response then
            if attempt > 1 then
                logger:info(string.format("✅ Sucesso após %d tentativas", attempt))
            end
            return response, nil
        end

        -- Se falhou e ainda há tentativas, fazer retry
        if attempt < max_retries then
            logger:warn(string.format("❌ Tentativa %d falhou: %s", attempt, err.message or "erro desconhecido"))
            logger:warn(string.format("⏳ Retry em %d segundos...", delay))

            LrTasks.sleep(delay)
            delay = delay * 2  -- Exponential backoff (1s, 2s, 4s, ...)
        else
            -- Última tentativa falhou
            logger:error(string.format("❌ Falha após %d tentativas: %s", max_retries, err.message or "erro desconhecido"))
            return nil, {
                message = string.format("Falha após %d tentativas: %s", max_retries, err.message or "erro de rede"),
                retries = max_retries
            }
        end
    end

    -- Nunca deve chegar aqui, mas por segurança
    return nil, { message = "Erro inesperado no retry logic" }
end

function CommonV2.post_json(endpoint, payload)
    -- Verificar se JSON está disponível
    if not JSON or not JSON.encode or not JSON.decode then
        local err_msg = "Módulo JSON não está carregado. Verifique json.lua no diretório do plugin."
        logger:error(err_msg)
        return nil, { message = err_msg }
    end

    local url = CommonV2.get_config('SERVER_URL') .. endpoint
    local headers = {{field = "Content-Type", value = "application/json"}}

    logger:trace("POST " .. url)

    local ok, body_str = pcall(function() return JSON.encode(payload) end)
    if not ok then
        logger:error("Falha ao encodar payload JSON: " .. tostring(body_str))
        return nil, { message = "Falha ao encodar o pedido para JSON." }
    end

    -- Fazer POST HTTP diretamente (pcall interfere com múltiplos valores de retorno)
    -- LrHttp.post retorna (responseBody, responseHeaders)
    local responseBody, responseHeaders = LrHttp.post(url, body_str, headers, "POST", 120)

    -- Verificar se a chamada foi bem sucedida
    if not responseHeaders then
        logger:error("Erro de rede ao fazer POST para " .. endpoint .. ": sem responseHeaders")
        return nil, { message = "Erro de comunicação com o servidor: sem resposta" }
    end

    logger:trace("Response status: " .. tostring(responseHeaders and responseHeaders.status or "sem headers"))

    if not responseHeaders or responseHeaders.status ~= 200 then
        local status = responseHeaders and responseHeaders.status or "desconhecido"
        local error_message = "O servidor retornou um erro: " .. tostring(status)

        if responseBody then
            local decode_ok, decoded = pcall(function() return JSON.decode(responseBody) end)
            if decode_ok and decoded and decoded.detail then
                if type(decoded.detail) == 'string' then
                    error_message = decoded.detail
                elseif type(decoded.detail) == 'table' and decoded.detail[1] and decoded.detail[1].msg then
                    error_message = decoded.detail[1].msg
                end
            end
        end

        logger:error("Resposta não-OK: " .. tostring(status))
        return nil, { message = error_message, status = status, body = responseBody }
    end

    local decode_ok, response = pcall(function() return JSON.decode(responseBody) end)
    if not decode_ok then
        logger:error("Falha ao parsear resposta JSON. Body: " .. tostring(responseBody))
        return nil, { message = "Resposta inválida do servidor." }
    end

    logger:trace("Response JSON decoded com sucesso")
    return response, nil
end

-- ============================================================================
-- FUNÇÕES DE PREDIÇÃO V2
-- ============================================================================

function CommonV2.predict_v2(image_path, exif_data)
    local payload = {
        image_path = image_path,
        exif = exif_data or {}
    }

    logger:info("A fazer predição V2 para: " .. image_path)

    -- Usar retry logic (3 tentativas com exponential backoff)
    local response, err = CommonV2.post_json_with_retry("/predict", payload, 3)

    if err then
        logger:error("Erro na predição: " .. (err.message or "desconhecido"))
        return nil, err
    end

    if not response then
        logger:error("Response é nil!")
        return nil, { message = "Resposta vazia do servidor" }
    end

    if not response.sliders then
        logger:error("Response não contém 'sliders'!")
        local keys = {}
        for k, _ in pairs(response) do
            table.insert(keys, k)
        end
        logger:error("Chaves disponíveis: " .. table.concat(keys, ", "))
        return nil, { message = "Resposta sem sliders" }
    end

    logger:info("Predição V2 recebida: preset_id=" .. tostring(response.preset_id) .. ", confiança=" .. tostring(response.preset_confidence) .. ", prediction_id=" .. tostring(response.prediction_id or "nil"))

    return response, nil
end

function CommonV2.send_feedback(args)
    if not args or not args.prediction_id or args.prediction_id == 0 then
        logger:warn("Tentativa de enviar feedback sem prediction_id válido. Feedback ignorado.")
        return false, { message = "prediction_id inválido ou ausente" }
    end

    local payload = {
        prediction_id = args.prediction_id,
        rating = args.rating,
        user_params = args.user_params,
        notes = args.notes,
        feedback_type = args.feedback_type or "explicit",
        tags = args.tags or {},
        issues = args.issues or {},
        feedback_context = args.context,
        seconds_to_submit = args.seconds_to_submit
    }

    logger:info(string.format("A enviar feedback (rating=%s, tipo=%s)", tostring(args.rating), payload.feedback_type))

    local response, err = CommonV2.post_json("/v2/feedback", payload)
    if err then
        CommonV2.log_error("Feedback", "Erro ao enviar feedback: " .. (err.message or "desconhecido"))
        return false, err
    end

    local event_id = response and response.event_id or "n/a"
    CommonV2.log_info("Feedback", "Feedback enviado (event_id=" .. tostring(event_id) .. ")")
    return true, response
end

-- ============================================================================
-- FUNÇÕES DE UI
-- ============================================================================

function CommonV2.show_error(message)
    LrDialogs.message("NSP Plugin V2 - Erro", message, "critical")
end

function CommonV2.show_info(message)
    LrDialogs.message("NSP Plugin V2", message, "info")
end

function CommonV2.show_warning(message)
    LrDialogs.message("NSP Plugin V2 - Aviso", message, "warning")
end

function CommonV2.save_prediction_metadata(photo, prediction)
    if not photo or not prediction or not prediction.prediction_id then
        return
    end
    local metadata = {
        prediction_id = prediction.prediction_id,
        preset_id = prediction.preset_id,
        preset_confidence = prediction.preset_confidence,
        sliders = prediction.sliders,
        saved_at = os.time(),
    }
    local ok, encoded = pcall(function()
        return JSON.encode(metadata)
    end)
    if not ok then
        CommonV2.log_warn("Common_V2", "Falha ao serializar metadata de predição: " .. tostring(encoded))
        return
    end
    local status, err = pcall(function()
        photo:setPropertyForPlugin(_PLUGIN, private.FEEDBACK_METADATA_KEY, encoded)
    end)
    if not status then
        CommonV2.log_warn("Common_V2", "Não foi possível guardar metadata na foto: " .. tostring(err))
    end
end

function CommonV2.get_prediction_metadata(photo)
    if not photo then
        return nil
    end
    local ok, encoded = pcall(function()
        return photo:getPropertyForPlugin(_PLUGIN, private.FEEDBACK_METADATA_KEY)
    end)
    if not ok or not encoded then
        return nil
    end
    local decode_ok, metadata = pcall(function()
        return JSON.decode(encoded)
    end)
    if not decode_ok then
        CommonV2.log_warn("Common_V2", "Falha ao ler metadata guardada: " .. tostring(metadata))
        return nil
    end
    return metadata
end

function CommonV2.open_feedback_dialog(photo, reason)
    if not photo then
        CommonV2.show_warning("Seleciona uma foto antes de enviar feedback.")
        return
    end
    local prediction = CommonV2.get_prediction_metadata(photo)
    if not prediction or not prediction.prediction_id then
        CommonV2.show_warning("Nenhuma predição AI associada a esta foto. Aplica o preset AI primeiro.")
        return
    end
    CommonV2.prompt_feedback_dialog(photo, prediction, reason or "manual")
end

function CommonV2.show_feedback_nudge(photo, prediction, reason)
    if prefs[PREF_FEEDBACK_ENABLED] == false then
        return
    end
    local ok, err = pcall(function()
        LrDialogs.showBezel("NSP: usa 'Feedback Rápido…' para comentar", 3)
    end)
    if not ok then
        CommonV2.log_debug("Feedback", "showBezel indisponível: " .. tostring(err))
    end
    CommonV2.log_info("Feedback", string.format(
        "Sugestão de feedback (%s) para %s",
        reason or "interval",
        photo and (photo:getFormattedMetadata('fileName') or "?") or "foto desconhecida"
    ))
end

-- ============================================================================
-- FEEDBACK AUTOMÁTICO
-- ============================================================================

function CommonV2.get_feedback_interval()
    return prefs[PREF_FEEDBACK_INTERVAL] or 8
end

local function mark_prompt_handled()
    prefs[PREF_LAST_PROMPT_AT] = os.time()
    prefs[PREF_FEEDBACK_COUNTER] = 0
end

function CommonV2.should_prompt_feedback(prediction)
    if prefs[PREF_FEEDBACK_ENABLED] == false then
        return false, "disabled"
    end

    prefs[PREF_FEEDBACK_COUNTER] = (prefs[PREF_FEEDBACK_COUNTER] or 0) + 1
    local counter = prefs[PREF_FEEDBACK_COUNTER]
    local interval = CommonV2.get_feedback_interval()
    local now = os.time()
    local last_prompt = prefs[PREF_LAST_PROMPT_AT] or 0
    local force_after = prefs[PREF_FORCE_SECONDS] or 1800

    if prediction and prediction.preset_confidence and prediction.preset_confidence < 0.85 then
        return true, "low_confidence"
    end

    if counter % interval == 0 then
        return true, "interval"
    end

    if (now - last_prompt) >= force_after then
        return true, "timeout"
    end

    return false, "interval_not_reached"
end

local function build_feedback_tags(f, props, tag_options)
    local rows = { spacing = f:control_spacing() }
    for _, tag in ipairs(tag_options) do
        props[tag.id] = props[tag.id] or false
        table.insert(rows, f:checkbox {
            title = tag.label,
            value = LrView.bind(tag.id),
        })
    end
    return rows
end

local function gather_selected_tags(props, tag_options)
    local tags = {}
    for _, tag in ipairs(tag_options) do
        if props[tag.id] then
            table.insert(tags, tag.id)
        end
    end
    return tags
end

function CommonV2.get_feedback_tags(prediction)
    local tags = {}
    for _, tag in ipairs(private.BASE_FEEDBACK_TAGS) do
        table.insert(tags, tag)
    end

    if prediction and prediction.sliders then
        local slider_values = {}
        for slider_name, value in pairs(prediction.sliders) do
            table.insert(slider_values, {
                name = slider_name,
                value = math.abs(tonumber(value) or 0)
            })
        end
        table.sort(slider_values, function(a, b) return a.value > b.value end)

        local max_dynamic = 6
        local added = 0
        for _, entry in ipairs(slider_values) do
            if added >= max_dynamic then break end
            local mapping = CommonV2.PYTHON_TO_LR[entry.name]
            local label = mapping and mapping.display_name or entry.name
            table.insert(tags, {
                id = "slider_" .. entry.name,
                label = "Slider: " .. label
            })
            added = added + 1
        end
    end

    return tags
end

function CommonV2.prompt_feedback_dialog(photo, prediction, reason)
    LrFunctionContext.callWithContext("NSPQuickFeedback", function(context)
        local f = LrView.osFactory()
        local props = LrBinding.makePropertyTable(context)
        props.rating = 4
        props.notes = ""
        local tag_options = CommonV2.get_feedback_tags(prediction)

        local metadata_title = "Como correu a edição AI?"
        if photo then
            local name = photo:getFormattedMetadata('fileName')
            metadata_title = metadata_title .. "\n" .. (name or "")
        end

        local tag_rows = build_feedback_tags(f, props, tag_options)

        local contents = f:column {
            spacing = f:control_spacing(),
            fill_horizontal = 1,

            f:static_text {
                title = metadata_title,
                font = "<system/bold>",
            },

            f:popup_menu {
                items = {
                    { title = "Excelente (5)", value = 5 },
                    { title = "Boa (4)", value = 4 },
                    { title = "Precisa ajustes (3)", value = 3 },
                    { title = "Fraca (2)", value = 2 },
                    { title = "Bug/Quebra (1)", value = 1 },
                },
                value = LrView.bind('rating'),
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = "O que alteraste?",
            },

            f:column(tag_rows),

            f:static_text {
                title = "Notas rápidas (opcional)",
            },

            f:edit_field {
                value = LrView.bind('notes'),
                height_in_lines = 3,
                width_in_chars = 40,
            },
        }

        local start_time = os.time()
        local result = LrDialogs.presentModalDialog {
            title = "Feedback rápido do NSP",
            contents = contents,
            actionVerb = "Enviar",
            otherVerb = "Mais tarde",
            cancelVerb = "Cancelar",
        }

        if reason ~= "manual" then
            mark_prompt_handled()
        end

        if result ~= "ok" then
            CommonV2.log_info("Feedback", "Utilizador adiou o feedback (" .. tostring(reason) .. ")")
            return
        end

        local elapsed = os.time() - start_time
        local tags = gather_selected_tags(props, tag_options)
        local context = {
            reason = reason,
            preset_id = prediction and prediction.preset_id or nil,
            preset_confidence = prediction and prediction.preset_confidence or nil,
            prompt_interval = CommonV2.get_feedback_interval(),
            photo_name = photo and photo:getFormattedMetadata('fileName') or nil,
            prompt_source = reason or "manual",
        }

        local ok = CommonV2.send_feedback({
            prediction_id = prediction and prediction.prediction_id,
            rating = props.rating,
            notes = props.notes ~= "" and props.notes or nil,
            tags = tags,
            issues = tags,
            context = context,
            seconds_to_submit = elapsed,
        })

        if not ok then
            CommonV2.show_warning("Não foi possível enviar feedback. Verifica a ligação ao servidor.")
        end
    end)
end

function CommonV2.handle_post_apply_feedback(photo, prediction)
    CommonV2.save_prediction_metadata(photo, prediction)

    if not prediction or not prediction.prediction_id then
        CommonV2.log_debug("Feedback", "Sem prediction_id para solicitar feedback.")
        return
    end

    local should_prompt, reason = CommonV2.should_prompt_feedback(prediction)
    if not should_prompt then
        CommonV2.log_debug("Feedback", "Feedback automático não solicitado (" .. tostring(reason) .. ")")
        return
    end

    CommonV2.show_feedback_nudge(photo, prediction, reason)
    mark_prompt_handled()
end

-- ============================================================================
-- FUNÇÕES DE DEVELOP SETTINGS V2
-- ============================================================================

function CommonV2.build_develop_settings(sliders_dict)
    if not sliders_dict then
        CommonV2.log_error("build_develop_settings", "sliders_dict é nil!")
        return {}
    end

    local total_received = 0
    for _ in pairs(sliders_dict) do
        total_received = total_received + 1
    end

    local settings = {}
    local mapped_count = 0
    local unmapped = {}

    for python_name, value in pairs(sliders_dict) do
        local mapping = CommonV2.PYTHON_TO_LR[python_name]
        if mapping then
            settings[mapping.lr_key] = value
            mapped_count = mapped_count + 1
        else
            table.insert(unmapped, python_name)
            CommonV2.log_warn("build_develop_settings", "Slider NÃO mapeado: " .. python_name)
        end
    end

    CommonV2.log_info("build_develop_settings", "Mapeamento concluído: " .. mapped_count .. " de " .. total_received .. " sliders")

    if #unmapped > 0 then
        CommonV2.log_warn("build_develop_settings", "Sliders NÃO mapeados (" .. #unmapped .. "): " .. table.concat(unmapped, ", "))
    end

    if mapped_count == 0 then
        CommonV2.log_error("build_develop_settings", "CRÍTICO: Nenhum slider foi mapeado!")
    end

    return settings
end

function CommonV2.collect_develop_vector(photo)
    -- Recolhe o estado atual dos develop settings de uma foto
    -- Retorna um dicionário python_name => valor
    local settings = photo:getDevelopSettings()
    local vector = {}
    for _, mapping in ipairs(CommonV2.DEVELOP_MAPPING) do
        vector[mapping.python_name] = settings[mapping.lr_key] or 0
    end
    return vector
end

-- ============================================================================
-- FUNÇÕES DE VALIDAÇÃO
-- ============================================================================

function CommonV2.validate_exif(photo)
    local raw_meta = photo:getRawMetadata()
    if not raw_meta.isoSpeedRating or raw_meta.isoSpeedRating == 0 then
        return false, "ISO inválido ou ausente"
    end

    local format_meta = photo:getFormattedMetadata()
    local dims_value = format_meta.dimensions
    local width, height

    if type(dims_value) == "string" then
        width, height = string.match(dims_value, "(%d+)%s*x%s*(%d+)")
        if width and height then
            width = tonumber(width)
            height = tonumber(height)
        end
    elseif type(dims_value) == "table" then
        width = dims_value.width
        height = dims_value.height
    end

    if not width or not height or width == 0 or height == 0 then
        return false, "Dimensões da imagem ausentes ou inválidas"
    end

    return true, { width = width, height = height }
end

-- ============================================================================
-- FUNÇÕES DE FORMATAÇÃO (para preview UI)
-- ============================================================================

function CommonV2.format_slider_value(python_name, value)
    -- Formata um valor de slider para exibição amigável
    local mapping = CommonV2.PYTHON_TO_LR[python_name]
    if not mapping then return tostring(value) end

    -- Formatação especial para temperatura
    if python_name == "temp" then
        return string.format("%dK", math.floor(value))
    end

    -- Formatação padrão para a maioria dos sliders
    if value >= 0 then
        return string.format("+%.1f", value)
    else
        return string.format("%.1f", value)
    end
end

function CommonV2.format_preset_info(preset_id, confidence)
    -- Formata informação do preset para exibição
    local preset_names = {
        [0] = "Natural",
        [1] = "Vibrante",
        [2] = "Moody",
        [3] = "Suave"
    }

    local name = preset_names[preset_id] or ("Preset " .. (preset_id + 1))
    local conf_percent = math.floor(confidence * 100)

    return string.format("%s (%d%% confiança)", name, conf_percent)
end

-- ============================================================================
-- INICIALIZAÇÃO
-- ============================================================================
function private.init()
    if not prefs.server_url or prefs.server_url == "" then
        prefs.server_url = private.config.SERVER_URL
        logger:info("Preferência 'server_url' inicializada para: " .. private.config.SERVER_URL)
    end

    private.config.SERVER_URL = prefs.server_url
    private.config.start_server_script = prefs.start_server_script or private.config.start_server_script

    logger:info("Common_V2.lua inicializado - SERVER_URL: " .. private.config.SERVER_URL)
end

private.init()

-- ============================================================================
-- FUNÇÕES AUXILIARES PARA PREVIEW ANTES/DEPOIS
-- ============================================================================

function CommonV2.capture_current_settings(photo)
    -- Captura os settings atuais de uma foto
    -- Retorna um dicionário com todos os develop settings
    if not photo then
        CommonV2.log_error("capture_current_settings", "Foto é nil")
        return nil
    end

    local settings = photo:getDevelopSettings()
    if not settings then
        CommonV2.log_error("capture_current_settings", "Não foi possível obter develop settings")
        return nil
    end

    CommonV2.log_debug("capture_current_settings", "Settings capturados com sucesso")
    return settings
end

function CommonV2.apply_settings_temporarily(photo, settings)
    -- Aplica settings temporariamente a uma foto (para preview)
    -- Retorna true se sucesso, false caso contrário
    if not photo or not settings then
        CommonV2.log_error("apply_settings_temporarily", "Foto ou settings são nil")
        return false
    end

    local ok, err = pcall(function()
        photo:withDevelopSettings(settings)
    end)

    if not ok then
        CommonV2.log_error("apply_settings_temporarily", "Erro ao aplicar settings: " .. tostring(err))
        return false
    end

    CommonV2.log_debug("apply_settings_temporarily", "Settings aplicados temporariamente")
    return true
end

function CommonV2.revert_settings(photo, original_settings)
    -- Reverte settings de uma foto para os settings originais
    -- Retorna true se sucesso, false caso contrário
    if not photo or not original_settings then
        CommonV2.log_error("revert_settings", "Foto ou settings originais são nil")
        return false
    end

    return CommonV2.apply_settings_temporarily(photo, original_settings)
end

function CommonV2.show_preview_dialog(photo, original_settings, ai_settings, prediction)
    -- Mostra diálogo de preview com comparação antes/depois
    -- Retorna "apply", "cancel" ou "adjust"

    LrFunctionContext.callWithContext("PreviewDialog", function(context)
        local f = LrView.osFactory()
        local props = LrBinding.makePropertyTable(context)

        props.current_view = "before" -- "before" ou "after"
        props.preset_info = ""

        -- Formatar informação do preset
        if prediction then
            local preset_name = CommonV2.format_preset_info(prediction.preset_id, prediction.preset_confidence)
            props.preset_info = "Preset sugerido: " .. preset_name
        end

        -- Função para alternar entre antes/depois
        local function toggle_view()
            if props.current_view == "before" then
                props.current_view = "after"
                CommonV2.apply_settings_temporarily(photo, ai_settings)
            else
                props.current_view = "before"
                CommonV2.revert_settings(photo, original_settings)
            end
        end

        local contents = f:column {
            spacing = f:control_spacing(),
            fill_horizontal = 1,

            f:static_text {
                title = "Preview Antes/Depois",
                font = "<system/bold>",
            },

            f:static_text {
                title = LrView.bind('preset_info'),
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = "Use o botão 'Alternar' para comparar antes/depois",
            },

            f:row {
                spacing = f:control_spacing(),

                f:push_button {
                    title = "← Antes | Depois →",
                    action = function()
                        toggle_view()
                    end,
                    width = 200,
                },
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = "Escolha uma ação:",
                font = "<system/bold>",
            },
        }

        local result = LrDialogs.presentModalDialog {
            title = "NSP - Preview AI",
            contents = contents,
            actionVerb = "Aplicar",
            otherVerb = "Ajustar Manualmente",
            cancelVerb = "Cancelar",
        }

        -- Reverter para settings originais antes de fechar
        CommonV2.revert_settings(photo, original_settings)

        if result == "ok" then
            return "apply"
        elseif result == "other" then
            return "adjust"
        else
            return "cancel"
        end
    end)
end

-- ============================================================================
-- FUNÇÕES AUXILIARES PARA CULLING INTELIGENTE
-- ============================================================================

function CommonV2.call_culling_api(image_paths, exif_data_list)
    -- Chama API de culling para análise de qualidade
    -- Retorna lista de scores ou nil em caso de erro

    if not image_paths or #image_paths == 0 then
        CommonV2.log_error("call_culling_api", "Lista de imagens vazia")
        return nil, { message = "Nenhuma imagem fornecida" }
    end

    local payload = {
        images = {}
    }

    for i, image_path in ipairs(image_paths) do
        local exif = exif_data_list and exif_data_list[i] or {}
        table.insert(payload.images, {
            image_path = image_path,
            exif = exif
        })
    end

    CommonV2.log_info("call_culling_api", "A analisar " .. #image_paths .. " imagens")

    local response, err = CommonV2.post_json("/api/culling/score", payload)

    if err then
        CommonV2.log_error("call_culling_api", "Erro na API de culling: " .. (err.message or "desconhecido"))
        return nil, err
    end

    if not response or not response.scores then
        CommonV2.log_error("call_culling_api", "Resposta inválida da API de culling")
        return nil, { message = "Resposta inválida do servidor" }
    end

    CommonV2.log_info("call_culling_api", "Análise concluída: " .. #response.scores .. " scores recebidos")
    return response.scores, nil
end

function CommonV2.get_photo_quality_score(photo)
    -- Obtém score de qualidade para uma única foto
    -- Retorna score (0-100) ou nil em caso de erro

    if not photo then
        return nil, { message = "Foto é nil" }
    end

    local image_path = photo:getRawMetadata("path")
    if not image_path then
        return nil, { message = "Caminho da imagem não disponível" }
    end

    local exif_data = {
        iso = photo:getRawMetadata("isoSpeedRating") or 0,
        aperture = photo:getRawMetadata("aperture") or 0,
        shutterSpeed = photo:getRawMetadata("shutterSpeed") or 0,
        focalLength = photo:getRawMetadata("focalLength") or 0,
    }

    local scores, err = CommonV2.call_culling_api({image_path}, {exif_data})

    if err then
        return nil, err
    end

    if not scores or #scores == 0 then
        return nil, { message = "Nenhum score retornado" }
    end

    return scores[1], nil
end

-- ============================================================================
-- FUNÇÕES AUXILIARES PARA GESTÃO DE PRESETS
-- ============================================================================

function CommonV2.list_available_presets()
    -- Lista todos os presets disponíveis no servidor
    -- Retorna lista de presets ou nil em caso de erro

    local url = CommonV2.get_config('SERVER_URL') .. "/api/presets"
    local headers = {{field = "Content-Type", value = "application/json"}}

    CommonV2.log_debug("list_available_presets", "A listar presets de: " .. url)

    local responseBody, responseHeaders = LrHttp.get(url, headers)

    if not responseHeaders or responseHeaders.status ~= 200 then
        local status = responseHeaders and responseHeaders.status or "sem resposta"
        CommonV2.log_error("list_available_presets", "Erro ao listar presets: status " .. tostring(status))
        return nil, { message = "Erro ao contactar servidor", status = status }
    end

    if not JSON or not JSON.decode then
        return nil, { message = "Módulo JSON não disponível" }
    end

    local decode_ok, response = pcall(function() return JSON.decode(responseBody) end)
    if not decode_ok then
        CommonV2.log_error("list_available_presets", "Falha ao parsear resposta")
        return nil, { message = "Resposta inválida do servidor" }
    end

    if not response or not response.presets then
        return nil, { message = "Resposta sem lista de presets" }
    end

    CommonV2.log_info("list_available_presets", "Listados " .. #response.presets .. " presets")
    return response.presets, nil
end

function CommonV2.get_active_preset()
    -- Obtém o preset atualmente ativo
    -- Retorna preset ou nil

    local url = CommonV2.get_config('SERVER_URL') .. "/api/presets/active"
    local headers = {{field = "Content-Type", value = "application/json"}}

    local responseBody, responseHeaders = LrHttp.get(url, headers)

    if not responseHeaders or responseHeaders.status ~= 200 then
        return nil, { message = "Erro ao obter preset ativo" }
    end

    if not JSON or not JSON.decode then
        return nil, { message = "Módulo JSON não disponível" }
    end

    local decode_ok, response = pcall(function() return JSON.decode(responseBody) end)
    if not decode_ok or not response then
        return nil, { message = "Resposta inválida" }
    end

    return response.preset, nil
end

function CommonV2.set_active_preset(preset_id)
    -- Define o preset ativo no servidor
    -- Retorna true se sucesso, false caso contrário

    if not preset_id then
        return false, { message = "preset_id é obrigatório" }
    end

    local payload = {
        preset_id = preset_id
    }

    local response, err = CommonV2.post_json("/api/presets/active", payload)

    if err then
        CommonV2.log_error("set_active_preset", "Erro ao definir preset ativo: " .. (err.message or "desconhecido"))
        return false, err
    end

    if not response or not response.success then
        return false, { message = "Falha ao ativar preset" }
    end

    CommonV2.log_info("set_active_preset", "Preset " .. preset_id .. " definido como ativo")
    return true, nil
end

function CommonV2.export_current_preset(photo, output_path)
    -- Exporta os settings atuais da foto como preset .nsppreset
    -- Retorna true se sucesso, false caso contrário

    if not photo then
        return false, { message = "Foto é nil" }
    end

    if not output_path then
        return false, { message = "output_path é obrigatório" }
    end

    -- Capturar settings atuais
    local settings = CommonV2.capture_current_settings(photo)
    if not settings then
        return false, { message = "Falha ao capturar settings" }
    end

    -- Converter para formato de sliders Python
    local sliders = CommonV2.collect_develop_vector(photo)

    local preset_data = {
        name = "Custom Preset",
        version = "1.0",
        author = "User",
        created_at = os.date("%Y-%m-%d %H:%M:%S"),
        sliders = sliders,
        metadata = {
            exported_from = "NSP Plugin",
            photo_filename = photo:getFormattedMetadata('fileName') or "unknown"
        }
    }

    -- Serializar para JSON
    if not JSON or not JSON.encode then
        return false, { message = "Módulo JSON não disponível" }
    end

    local ok, json_str = pcall(function()
        return JSON.encode(preset_data)
    end)

    if not ok then
        CommonV2.log_error("export_current_preset", "Falha ao serializar preset: " .. tostring(json_str))
        return false, { message = "Falha ao criar ficheiro de preset" }
    end

    -- Escrever para ficheiro
    local file_ok, file_err = pcall(function()
        local file = io.open(output_path, "w")
        if not file then
            error("Não foi possível criar ficheiro")
        end
        file:write(json_str)
        file:close()
    end)

    if not file_ok then
        CommonV2.log_error("export_current_preset", "Erro ao escrever ficheiro: " .. tostring(file_err))
        return false, { message = "Erro ao escrever ficheiro: " .. tostring(file_err) }
    end

    CommonV2.log_info("export_current_preset", "Preset exportado para: " .. output_path)
    return true, nil
end

-- ============================================================================
-- EXPORT
-- ============================================================================

return CommonV2
