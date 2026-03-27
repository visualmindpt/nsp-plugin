-- AutoStraighten.lua
-- Auto-Straighten - Detecção automática de horizonte e correção de rotação

local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'
local LrProgressScope = import 'LrProgressScope'
local LrDialogs = import 'LrDialogs'
local LrHttp = import 'LrHttp'

-- Módulos internos
local CommonV2 = require 'Common_V2'

local logger = LrLogger('NSPPlugin.AutoStraighten')
logger:enable("logfile")

-- ============================================================================
-- AUTO-STRAIGHTEN PARA FOTO INDIVIDUAL
-- ============================================================================

local function auto_straighten_photo(photo, suppress_toast)
    CommonV2.log_info("AutoStraighten", "Analisando horizonte: " .. photo:getFormattedMetadata('fileName'))

    -- Validar caminho
    local path = photo:getRawMetadata("path")
    if not path or path == "" then
        return false, "Caminho da foto inválido"
    end

    -- Chamar endpoint /auto-straighten
    local url = CommonV2.get_server_url() .. "/auto-straighten"
    local payload = {
        image_path = path,
        min_line_length = 200,
        angle_threshold = 45.0
    }

    -- Fazer POST
    local JSON = require 'json'
    local body_str = JSON.encode(payload)
    if not body_str then
        return false, "Erro ao codificar pedido JSON"
    end

    local headers = {
        { field = "Content-Type", value = "application/json" },
    }

    CommonV2.log_info("AutoStraighten", "Enviando pedido para " .. url)

    local responseBody, responseHeaders = LrHttp.post(url, body_str, headers, "POST", 30)

    -- Verificar resposta
    if not responseHeaders then
        return false, "Erro de comunicação com o servidor"
    end

    if responseHeaders.status ~= 200 then
        return false, "Servidor retornou erro: " .. tostring(responseHeaders.status)
    end

    -- Parse resposta
    local result = JSON.decode(responseBody)
    if not result then
        return false, "Resposta inválida do servidor"
    end

    CommonV2.log_info("AutoStraighten",
        string.format("Resultado: ângulo=%.2f°, confiança=%.2f, recomendação=%s",
            result.angle, result.confidence, result.recommendation))

    -- Verificar se precisa correção
    if not result.requires_correction then
        if not suppress_toast then
            CommonV2.show_info("Horizonte já está nivelado!\n\nÂngulo detectado: " ..
                string.format("%.2f°", result.angle) .. "\nConfiança: " ..
                string.format("%.0f%%", result.confidence * 100))
        end
        return true, "Sem correção necessária"
    end

    -- Verificar confiança
    if result.recommendation ~= 'rotate' then
        local msg = string.format(
            "Baixa confiança na detecção!\n\nÂngulo detectado: %.2f°\nConfiança: %.0f%%\n\nRecomendação: verificar manualmente",
            result.angle, result.confidence * 100
        )

        if not suppress_toast then
            CommonV2.show_warning(msg)
        end
        return false, "Baixa confiança"
    end

    -- Aplicar rotação no Lightroom
    local catalog = LrApplication.activeCatalog()
    catalog:withWriteAccessDo("Auto-Straighten Horizonte", function()
        -- Obter ângulo atual
        local current_angle = photo:getDevelopSettings().StraightenAngle or 0

        -- Calcular novo ângulo (negativo porque Lightroom usa sistema invertido)
        local new_angle = current_angle - result.angle

        -- Limitar entre -45 e 45 graus (limites do Lightroom)
        new_angle = math.max(-45, math.min(45, new_angle))

        -- Aplicar
        photo:applyDevelopSettings({ StraightenAngle = new_angle })

        CommonV2.log_info("AutoStraighten",
            string.format("Rotação aplicada: %.2f° (anterior: %.2f°, novo: %.2f°)",
                -result.angle, current_angle, new_angle))
    end, {timeout = 10, abortOnConflict = true})

    if not suppress_toast then
        CommonV2.show_info(string.format(
            "Horizonte corrigido!\n\nRotação aplicada: %.2f°\nConfiança: %.0f%%\n\n%s",
            result.angle, result.confidence * 100, photo:getFormattedMetadata('fileName')
        ))
    end

    return true, nil
end

-- ============================================================================
-- ENTRY POINT
-- ============================================================================

local function main()
    LrTasks.startAsyncTask(function()
        local catalog = LrApplication.activeCatalog()
        local photos = catalog:getTargetPhotos()

        if not photos or #photos == 0 then
            CommonV2.show_error("Selecione pelo menos uma foto para auto-straighten.")
            return
        end

        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor NSP offline. Por favor inicie o NSP Control Center.")
            return
        end

        -- Single photo
        if #photos == 1 then
            local ok, err = auto_straighten_photo(photos[1], false)
            if not ok and err ~= "Sem correção necessária" and err ~= "Baixa confiança" then
                CommonV2.show_error("Erro no Auto-Straighten:\n\n" .. tostring(err))
            end
            return
        end

        -- Batch processing
        local progressScope = LrDialogs.showModalProgressDialog({
            title = "Auto-Straighten - Processamento em Lote",
            caption = "Analisando horizontes...",
            cannotCancel = false,
            functionContext = nil
        })

        local success_count = 0
        local skip_count = 0
        local error_count = 0

        for i, photo in ipairs(photos) do
            if progressScope:isCanceled() then
                CommonV2.log_info("AutoStraighten", "Processo cancelado pelo utilizador")
                break
            end

            progressScope:setCaption(string.format(
                "A processar %d de %d...\n%s",
                i, #photos, photo:getFormattedMetadata('fileName')
            ))
            progressScope:setPortionComplete(i - 1, #photos)

            local ok, err = auto_straighten_photo(photo, true)

            if ok then
                if err == "Sem correção necessária" or err == "Baixa confiança" then
                    skip_count = skip_count + 1
                else
                    success_count = success_count + 1
                end
            else
                error_count = error_count + 1
                CommonV2.log_error("AutoStraighten",
                    "Erro em " .. photo:getFormattedMetadata('fileName') .. ": " .. tostring(err))
            end
        end

        progressScope:done()

        -- Mostrar resumo
        local summary = string.format(
            "Auto-Straighten Completo!\n\n✅ Corrigidas: %d\n⏭️ Ignoradas: %d\n❌ Erros: %d\n\nTotal: %d fotos",
            success_count, skip_count, error_count, #photos
        )
        CommonV2.show_info(summary)
    end)
end

-- Execute
main()
