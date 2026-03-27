-- ApplyAIPresetV2.lua
-- Aplica preset AI DIRETAMENTE (modelo V2 - Classificador + Refinador)
-- SIMPLIFICADO: Sem preview, aplicação imediata

local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'
local LrProgressScope = import 'LrProgressScope'
local LrDialogs = import 'LrDialogs'

-- Módulos internos
local CommonV2 = require 'Common_V2'

local logger = LrLogger('NSPPlugin.ApplyAIPresetV2')
logger:enable("logfile")

-- ============================================================================
-- APLICAR PRESET (modo sincronizado para single ou batch)
-- ============================================================================

local function apply_preset_sync(photo, suppress_toast, skip_feedback, progress_scope)
    local filename = photo:getFormattedMetadata('fileName')
    CommonV2.log_info("ApplyAIPresetV2", "Aplicando AI preset: " .. filename)

    -- Feedback: Iniciando
    if progress_scope then
        progress_scope:setCaption("📸 " .. filename .. " - Validando...")
    end

    -- Validar caminho
    local path = photo:getRawMetadata("path")
    if not path or path == "" then
        return false, "Caminho da foto inválido"
    end

    -- Validar EXIF
    local valid_exif, exif_data = CommonV2.validate_exif(photo)
    if not valid_exif then
        return false, "EXIF inválido: " .. (exif_data or "erro desconhecido")
    end

    -- Feedback: Preparando
    if progress_scope then
        progress_scope:setCaption("🔍 " .. filename .. " - Analisando features...")
    end

    -- Payload EXIF
    local raw_meta = photo:getRawMetadata()
    local exif_payload = {
        iso = tonumber(raw_meta.isoSpeedRating),
        width = tonumber(exif_data.width),
        height = tonumber(exif_data.height),
    }

    -- Feedback: Predição AI
    if progress_scope then
        progress_scope:setCaption("🤖 " .. filename .. " - Processando AI...")
    end

    -- Predição
    local prediction, err = CommonV2.predict_v2(path, exif_payload)
    if err then
        return false, "Erro na predição AI: " .. (err.message or "desconhecido")
    end
    if not prediction or not prediction.sliders then
        return false, "Predição inválida (sem sliders)"
    end

    local confidence_pct = math.floor((prediction.preset_confidence or 0) * 100)
    CommonV2.log_info("ApplyAIPresetV2", "Predição recebida: preset_id=" .. tostring(prediction.preset_id) .. ", confiança=" .. confidence_pct .. "%")

    -- Feedback: Aplicando
    if progress_scope then
        progress_scope:setCaption("✨ " .. filename .. " - Aplicando ajustes (" .. confidence_pct .. "% confiança)...")
    end

    -- Build settings
    local developSettings = CommonV2.build_develop_settings(prediction.sliders)
    if not developSettings or not next(developSettings) then
        return false, "Sem ajustes válidos do servidor"
    end

    -- Aplicar
    local catalog = LrApplication.activeCatalog()
    catalog:withWriteAccessDo("Aplicar NSP Preset V2", function()
        photo:applyDevelopSettings(developSettings)
    end, {timeout = 10, abortOnConflict = true})

    -- Bezel notification (rápido, não-blocking)
    if not suppress_toast then
        pcall(function()
            LrDialogs.showBezel("✅ Preset aplicado - " .. confidence_pct .. "% confiança", 2)
        end)
    end

    -- Guardar metadata/feedback
    if not skip_feedback then
        CommonV2.handle_post_apply_feedback(photo, prediction)
    end
    return true, nil
end

-- ============================================================================
-- ENTRY POINT
-- ============================================================================

local function main()
    -- Tudo dentro de uma task para evitar waits fora de contexto
    LrTasks.startAsyncTask(function()
        local catalog = LrApplication.activeCatalog()
        local photos = catalog:getTargetPhotos()

        if not photos or #photos == 0 then
            CommonV2.show_error("Selecione pelo menos uma foto para aplicar o preset AI.")
            return
        end

        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor NSP offline. Por favor inicie o NSP Control Center.")
            return
        end

        if #photos == 1 then
            -- Single photo com progress scope
            local progress = LrProgressScope({
                title = "NSP - AI Preset V2",
                caption = "Processando foto...",
                functionContext = nil,
            })

            local ok, err = apply_preset_sync(photos[1], false, false, progress)
            progress:done()

            if not ok then
                CommonV2.show_error(err or "Falha ao aplicar preset.")
            end
            return
        end

        -- Batch processing melhorado
        local total = #photos
        local start_time = os.time()
        local progress = LrProgressScope({
            title = "NSP - AI Preset V2 (Batch)",
            caption = string.format("🚀 Preparando processamento de %d fotos...", total),
            functionContext = nil,
        })
        progress:setCancelable(true)

        local success = 0
        local failed = 0
        local errors = {}

        for idx, photo in ipairs(photos) do
            if progress:isCanceled() then
                CommonV2.log_info("ApplyAIPresetV2", "Batch cancelado pelo utilizador")
                break
            end

            -- Calcular progresso e tempo estimado
            progress:setPortionComplete(idx - 1, total)

            local elapsed = os.time() - start_time
            local avg_time_per_photo = elapsed / math.max(1, idx - 1)
            local remaining_photos = total - idx + 1
            local eta_seconds = math.floor(avg_time_per_photo * remaining_photos)
            local eta_str = ""

            if idx > 1 and eta_seconds > 0 then
                if eta_seconds < 60 then
                    eta_str = string.format(" | ETA: %ds", eta_seconds)
                else
                    local eta_mins = math.floor(eta_seconds / 60)
                    local eta_secs = eta_seconds % 60
                    eta_str = string.format(" | ETA: %dm %ds", eta_mins, eta_secs)
                end
            end

            local pct = math.floor((idx / total) * 100)
            progress:setCaption(string.format("📊 %d/%d (%d%%) | ✅ %d | ❌ %d%s",
                idx, total, pct, success, failed, eta_str))

            local ok, err = apply_preset_sync(photo, true, true, progress)
            if ok then
                success = success + 1
            else
                failed = failed + 1
                local photo_name = photo:getFormattedMetadata('fileName') or string.format("Foto %d", idx)
                table.insert(errors, string.format("%s: %s", photo_name, err or "erro"))
            end
            LrTasks.sleep(0)
        end

        progress:done()

        -- Resumo final com estatísticas
        local elapsed_total = os.time() - start_time
        local elapsed_str = ""
        if elapsed_total < 60 then
            elapsed_str = string.format("%d segundos", elapsed_total)
        else
            local mins = math.floor(elapsed_total / 60)
            local secs = elapsed_total % 60
            elapsed_str = string.format("%d minutos e %d segundos", mins, secs)
        end

        local avg_per_photo = elapsed_total / total

        local msg = string.format(
            "🎯 Processamento Concluído!\n\n" ..
            "✅ Sucesso: %d fotos\n" ..
            "❌ Falhas: %d fotos\n\n" ..
            "⏱️  Tempo total: %s\n" ..
            "⚡ Média: %.1f seg/foto",
            success, failed, elapsed_str, avg_per_photo
        )

        if #errors > 0 then
            msg = msg .. "\n\n⚠️  Erros encontrados:\n• " .. table.concat(errors, "\n• ")
        end

        LrDialogs.message("NSP AI Preset V2 - Batch", msg, (#errors > 0) and "warning" or "info")
    end)
end

-- EXECUTAR a função
main()
