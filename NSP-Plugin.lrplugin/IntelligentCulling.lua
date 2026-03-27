-- IntelligentCulling.lua
-- Culling único: analisa, mostra estatísticas e marca fotos (pick/reject + rating)

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrProgressScope = import 'LrProgressScope'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NSPPlugin.IntelligentCulling')
logger:enable("logfile")

-- Importar Common_V2 para funções auxiliares
local CommonV2 = require 'Common_V2'

-- ============================================================================
-- FUNÇÕES AUXILIARES
-- ============================================================================

local ACCEPT_THRESHOLD = 0.60 -- score >= 0.60 (60%) é aprovado

local function get_selected_photos()
    local catalog = LrApplication.activeCatalog()
    local selectedPhotos = catalog:getTargetPhotos()

    if not selectedPhotos or #selectedPhotos == 0 then
        CommonV2.show_warning("Nenhuma foto selecionada. Por favor, seleciona pelo menos uma foto.")
        return nil
    end

    return selectedPhotos
end

local function collect_photo_data(photos)
    local photo_data = {}

    for i, photo in ipairs(photos) do
        local image_path = photo:getRawMetadata("path")

        if image_path then
            local raw_meta = photo:getRawMetadata()

            local exif_data = {
                iso = raw_meta.isoSpeedRating or 0,
                aperture = raw_meta.aperture or 0,
                shutterspeed = raw_meta.shutterSpeed or 0,
                focallength = raw_meta.focalLength or 0,
            }

            table.insert(photo_data, {
                photo = photo,
                path = image_path,
                exif = exif_data,
                filename = photo:getFormattedMetadata('fileName') or "unknown"
            })
        else
            CommonV2.log_warn("IntelligentCulling", "Foto sem caminho válido, ignorada")
        end
    end

    return photo_data
end

local function format_pct(score)
    if not score or type(score) ~= "number" then
        return "N/A"
    end

    return string.format("%.1f", score * 100)
end

-- ============================================================================
-- LÓGICA PRINCIPAL
-- ============================================================================

local function intelligent_culling()
    LrTasks.startAsyncTask(function()
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor AI não está disponível. Inicia o servidor primeiro através do menu 'Iniciar Servidor AI'.")
            return
        end

        local photos = get_selected_photos()
        if not photos then
            return
        end

        local num_photos = #photos
        CommonV2.log_info("IntelligentCulling", "A analisar " .. num_photos .. " fotos")

        local progress = LrProgressScope({
            title = "NSP - Culling Inteligente",
            functionContext = nil,
        })

        progress:setCaption("A preparar fotos para análise...")

        local photo_data = collect_photo_data(photos)

        if not photo_data or #photo_data == 0 then
            progress:done()
            CommonV2.show_error("Nenhuma foto válida para análise.")
            return
        end

        CommonV2.log_info("IntelligentCulling", #photo_data .. " fotos preparadas para análise")

        local image_paths = {}
        local exif_data_list = {}

        for _, data in ipairs(photo_data) do
            table.insert(image_paths, data.path)
            table.insert(exif_data_list, data.exif)
        end

        progress:setCaption("A analisar qualidade das fotos...")

        local scores, err = CommonV2.call_culling_api(image_paths, exif_data_list)

        if err then
            progress:done()
            CommonV2.show_error("Erro ao analisar fotos: " .. (err.message or "desconhecido"))
            return
        end

        if not scores or #scores ~= #photo_data then
            progress:done()
            CommonV2.show_error("Resposta inválida da API de culling.")
            return
        end

        CommonV2.log_info("IntelligentCulling", "Análise concluída: " .. #scores .. " scores recebidos")

        for i, data in ipairs(photo_data) do
            -- Servidor pode devolver 0-1 ou 0-100; normalizar para 0-1
            local raw_score = tonumber(scores[i]) or 0
            if raw_score > 1 then
                raw_score = raw_score / 100.0
            end
            data.score_raw = raw_score
            data.score_pct = raw_score * 100
        end

        table.sort(photo_data, function(a, b)
            return (a.score_raw or 0) > (b.score_raw or 0)
        end)

        -- Estatísticas
        local total_score = 0
        local max_score = -1
        local min_score = 2

        local accepted = {}
        local rejected = {}

        for _, data in ipairs(photo_data) do
            local score = data.score_raw or 0
            total_score = total_score + score
            if score > max_score then max_score = score end
            if score < min_score then min_score = score end

            if score >= ACCEPT_THRESHOLD then
                table.insert(accepted, data)
            else
                table.insert(rejected, data)
            end
        end

        local avg_score = total_score / #photo_data
        local threshold_pct = ACCEPT_THRESHOLD * 100

        -- Aplicar flags/ratings
        local catalog = LrApplication.activeCatalog()
        catalog:withWriteAccessDo("NSP - Culling Inteligente", function()
            for _, data in ipairs(accepted) do
                if data.photo then
                    data.photo:setRawMetadata("pickStatus", 1) -- pick
                    data.photo:setRawMetadata("rating", 5)
                    -- Forçar cor: alguns catálogos usam nome local; gravamos ambos
                    pcall(function() data.photo:setRawMetadata("label", "Green") end)
                    pcall(function() data.photo:setRawMetadata("colorNameForLabel", "Green") end)
                end
            end

            for _, data in ipairs(rejected) do
                if data.photo then
                    data.photo:setRawMetadata("pickStatus", -1) -- reject
                    data.photo:setRawMetadata("rating", 1)
                    pcall(function() data.photo:setRawMetadata("label", "Red") end)
                    pcall(function() data.photo:setRawMetadata("colorNameForLabel", "Red") end)
                end
            end
        end)

        progress:done()

        -- Construir listas top/bottom
        local function build_list(items, limit)
            local text = ""
            for i = 1, math.min(limit, #items) do
                local data = items[i]
                text = text .. string.format(
                    "%d. %s — %s%%\n",
                    i,
                    data.filename,
                    format_pct(data.score_raw)
                )
            end
            return text == "" and "(sem entradas)" or text
        end

        local best_list = build_list(photo_data, math.min(3, #photo_data))
        local reversed = {}
        for i = #photo_data, 1, -1 do
            table.insert(reversed, photo_data[i])
        end
        local worst_list = build_list(reversed, math.min(3, #reversed))

        -- Mostrar resultados numa UI legível
        LrFunctionContext.callWithContext("CullingResults", function(context)
            local f = LrView.osFactory()
            local contents = f:column {
                spacing = f:control_spacing(),
                fill_horizontal = 1,

                f:static_text {
                    title = "Resultados do Culling",
                    font = "<system/bold>",
                    size = "large",
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = string.format(
                        "Analisadas %d fotos. Threshold usado: %.0f%%. Aceites: %d  |  Rejeitadas: %d",
                        #photo_data, threshold_pct, #accepted, #rejected
                    ),
                    font = "<system/bold>",
                },

                f:static_text {
                    title = string.format(
                        "Média: %s%%   •   Melhor: %s%%   •   Pior: %s%%",
                        format_pct(avg_score), format_pct(max_score), format_pct(min_score)
                    ),
                },

                f:separator { fill_horizontal = 1 },

                f:static_text { title = "Top 3 melhores:", font = "<system/bold>" },
                f:scrolled_view {
                    width = 500,
                    height = 80,
                    horizontal_scrolling_resistance = 1,
                    vertical_scrolling_resistance = 1,
                    content = f:static_text { title = best_list },
                },

                f:static_text { title = "Top 3 piores:", font = "<system/bold>" },
                f:scrolled_view {
                    width = 500,
                    height = 80,
                    horizontal_scrolling_resistance = 1,
                    vertical_scrolling_resistance = 1,
                    content = f:static_text { title = worst_list },
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = "O que foi aplicado: fotos >= " .. string.format("%.0f%%", threshold_pct) .. " receberam pick + rating 5 (verde). As restantes foram rejeitadas (flag reject) com rating 1 (vermelho).",
                    font = "<system/small/bold>",
                },
            }

            LrDialogs.presentModalDialog {
                title = "NSP - Culling Inteligente",
                contents = contents,
                actionVerb = "OK",
            }
        end)

        CommonV2.log_info("IntelligentCulling", "Análise concluída com sucesso")
    end)
end

-- ============================================================================
-- PONTO DE ENTRADA
-- ============================================================================

-- Executar a função principal
intelligent_culling()
