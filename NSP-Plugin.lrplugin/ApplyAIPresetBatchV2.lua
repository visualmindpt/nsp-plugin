-- ApplyAIPresetBatchV2.lua
-- Processa múltiplas fotos com AI em lote com tracking detalhado

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'
local LrProgressScope = import 'LrProgressScope'
local LrLogger = import 'LrLogger'
local okDev, LrDevelopController = pcall(import, 'LrDevelopController')

-- Módulos internos
local CommonV2 = require 'Common_V2'

local logger = LrLogger('NSPPlugin.ApplyAIPresetBatchV2')
logger:enable("logfile")

-- ============================================================================
-- ESTATÍSTICAS
-- ============================================================================

local function initStats()
    return {
        total = 0,
        processed = 0,
        success = 0,
        failed = 0,
        skipped = 0,
        preset_distribution = {}, -- {[preset_id] = count}
        average_confidence = 0,
        total_time = 0,
        errors = {},
    }
end

local function updatePresetDistribution(stats, preset_id)
    if not stats.preset_distribution[preset_id] then
        stats.preset_distribution[preset_id] = 0
    end
    stats.preset_distribution[preset_id] = stats.preset_distribution[preset_id] + 1
end

local function formatStats(stats)
    local lines = {}

    table.insert(lines, string.format("📊 Estatísticas de Processamento"))
    table.insert(lines, string.format("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"))
    table.insert(lines, string.format("✅ Sucesso: %d/%d fotos", stats.success, stats.total))
    table.insert(lines, string.format("❌ Falhas: %d", stats.failed))

    if stats.success > 0 then
        local avg_time = stats.total_time / stats.success
        table.insert(lines, string.format("⏱  Tempo médio: %.1fs/foto", avg_time))
        table.insert(lines, string.format("📈 Confiança média: %.0f%%", stats.average_confidence * 100))
    end

    if next(stats.preset_distribution) then
        table.insert(lines, "")
        table.insert(lines, "🎨 Distribuição de Presets:")
        for preset_id, count in pairs(stats.preset_distribution) do
            local preset_names = {[0] = "Natural", [1] = "Vibrante", [2] = "Moody", [3] = "Suave"}
            local name = preset_names[preset_id] or ("Preset " .. (preset_id + 1))
            local percentage = (count / stats.success) * 100
            table.insert(lines, string.format("  %s: %d (%.0f%%)", name, count, percentage))
        end
    end

    if #stats.errors > 0 then
        table.insert(lines, "")
        table.insert(lines, "❌ Erros encontrados:")
        for i = 1, math.min(5, #stats.errors) do
            table.insert(lines, "  " .. stats.errors[i])
        end
        if #stats.errors > 5 then
            table.insert(lines, string.format("  ... e mais %d erros", #stats.errors - 5))
        end
    end

    return table.concat(lines, "\n")
end

-- ============================================================================
-- PROCESSAMENTO BATCH
-- ============================================================================

local function processBatch(photos, context)
    local stats = initStats()
    stats.total = #photos

    local progress = LrProgressScope {
        title = "NSP Plugin V2 - Processamento em Lote",
        caption = string.format("A preparar %d fotos...", stats.total),
        functionContext = context,
    }
    progress:setCancelable(true)

    local batch_write = {}
    local BATCH_SIZE = 20
    local catalog = LrApplication.activeCatalog()
    local startTime = os.time()

    logger:info(string.format("Iniciando processamento batch de %d fotos", stats.total))

    for index, photo in ipairs(photos) do
        if progress:isCanceled() then
            logger:info("Processamento cancelado pelo utilizador")
            table.insert(stats.errors, "Processamento cancelado pelo utilizador")
            break
        end

        -- Atualizar UI de progresso
        local elapsed = os.time() - startTime
        local rate = elapsed > 0 and index / elapsed or 0
        local remaining = stats.total - index
        local eta = rate > 0 and math.ceil(remaining / rate) or 0

        progress:setPortionComplete(index - 1, stats.total)
        progress:setCaption(string.format(
            "NSP V2 (%d/%d) | ✅ %d | ❌ %d | ⏱ ~%ds restantes",
            index, stats.total, stats.success, stats.failed, eta
        ))

        -- Processar foto
        local photo_start = os.time()
        local success_photo = false

        repeat  -- usar repeat-until como alternativa a goto
            local path = photo:getRawMetadata("path")
            if not path or path == "" then
                logger:warn(string.format("Foto %d: caminho inválido", index))
                table.insert(stats.errors, string.format("Foto %d: caminho inválido", index))
                stats.failed = stats.failed + 1
                break
            end

            -- Validar EXIF
            local valid_exif, exif_data = CommonV2.validate_exif(photo)
            if not valid_exif then
                logger:warn(string.format("Foto %d: EXIF inválido - %s", index, exif_data or ""))
                table.insert(stats.errors, string.format("Foto %d: EXIF inválido", index))
                stats.failed = stats.failed + 1
                break
            end

            -- Preparar EXIF payload
            local raw_meta = photo:getRawMetadata()
            local exif_payload = {
                iso = tonumber(raw_meta.isoSpeedRating),
                width = tonumber(exif_data.width),
                height = tonumber(exif_data.height),
            }

            -- Fazer predição
            local prediction, err = CommonV2.predict_v2(path, exif_payload)

            if err then
                logger:warn(string.format("Foto %d: erro na predição - %s", index, err.message or ""))
                table.insert(stats.errors, string.format("Foto %d: %s", index, err.message or "erro desconhecido"))
                stats.failed = stats.failed + 1
                break
            end

            if not prediction or not prediction.sliders then
                logger:warn(string.format("Foto %d: resposta inválida do servidor", index))
                table.insert(stats.errors, string.format("Foto %d: resposta inválida do servidor", index))
                stats.failed = stats.failed + 1
                break
            end

            -- Construir develop settings
            local developSettings = CommonV2.build_develop_settings(prediction.sliders)

            if not developSettings or not next(developSettings) then
                logger:warn(string.format("Foto %d: nenhum ajuste válido recebido", index))
                table.insert(stats.errors, string.format("Foto %d: nenhum ajuste válido", index))
                stats.failed = stats.failed + 1
                break
            end

            -- Sucesso! Adicionar ao batch para aplicar
            table.insert(batch_write, {
                photo = photo,
                settings = developSettings,
            })

            stats.success = stats.success + 1
            success_photo = true
            local photo_time = os.time() - photo_start
            stats.total_time = stats.total_time + photo_time

            -- Atualizar estatísticas
            if prediction.preset_id ~= nil then
                updatePresetDistribution(stats, prediction.preset_id)
            end

            if prediction.preset_confidence then
                -- Calcular média móvel da confiança
                local old_avg = stats.average_confidence
                stats.average_confidence = ((old_avg * (stats.success - 1)) + prediction.preset_confidence) / stats.success
            end

            -- Aplicar batch se atingiu o tamanho limite
            if #batch_write >= BATCH_SIZE then
                logger:info(string.format("💾 A aplicar batch de %d fotos...", #batch_write))
                catalog:withWriteAccessDo("NSP Batch V2", function()
                    for _, item in ipairs(batch_write) do
                        item.photo:applyDevelopSettings(item.settings)
                    end
                end)
                batch_write = {} -- Limpar batch
                logger:info("✅ Batch aplicado com sucesso")
            end
        until true  -- sempre executa uma vez e sai com break

        stats.processed = stats.processed + 1
    end

    if #batch_write > 0 then
        logger:info(string.format("A aplicar batch final de %d fotos", #batch_write))
        catalog:withWriteAccessDo("NSP Batch V2 Final", function()
            for _, item in ipairs(batch_write) do
                item.photo:applyDevelopSettings(item.settings)
            end
        end)
        logger:info("Batch final aplicado com sucesso")
    end

    progress:done()

    return stats
end

-- ============================================================================
-- ENTRY POINT
-- ============================================================================

local function main()
    LrTasks.startAsyncTask(function()
        -- 1. Validar seleção de fotos
        local catalog = LrApplication.activeCatalog()
        local photos = catalog:getTargetPhotos()

        if not photos or #photos == 0 then
            CommonV2.show_error("Selecione pelo menos uma foto para processar em lote.")
            return
        end

        if #photos == 1 then
            CommonV2.show_warning("Apenas uma foto selecionada. Use 'AI Preset V2 - Foto Individual' para melhor experiência com preview.")
            -- Continuar mesmo assim
        end

        -- 2. Garantir que o servidor está online
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor NSP offline. Por favor inicie o NSP Control Center antes de processar.")
            return
        end

        -- 3. Confirmar ação com o utilizador
        local confirm_result = LrDialogs.confirm(
            string.format("Processar %d fotos com AI?", #photos),
            "Esta operação irá aplicar presets AI a todas as fotos selecionadas.\n\n" ..
            "💡 Dica: Pode cancelar a qualquer momento durante o processamento.",
            "Processar",
            "Cancelar"
        )

        if confirm_result == "cancel" then
            return
        end

        -- 4. Processar fotos
        LrFunctionContext.callWithContext("batch_process_v2", function(context)
            local stats = processBatch(photos, context)

            if stats.success > 0 then
                local report = formatStats(stats)
                logger:info("Relatório final:\n" .. report)
                CommonV2.show_info(report)
            else
                CommonV2.show_error("Nenhuma foto foi processada com sucesso.\n\n" .. formatStats(stats))
            end
        end)
    end)
end

-- EXECUTAR a função
main()
