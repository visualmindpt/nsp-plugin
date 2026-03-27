-- MarkBestPhotos.lua
-- Marca automaticamente as melhores fotos com pick flag baseado em análise AI
-- Permite ao utilizador escolher percentagem ou número absoluto

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrProgressScope = import 'LrProgressScope'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NSPPlugin.MarkBestPhotos')
logger:enable("logfile")

-- Importar Common_V2 para funções auxiliares
local CommonV2 = require 'Common_V2'

-- ============================================================================
-- FUNÇÕES AUXILIARES
-- ============================================================================

local function get_selected_photos()
    -- Obtém as fotos atualmente selecionadas
    local catalog = LrApplication.activeCatalog()
    local selectedPhotos = catalog:getTargetPhotos()

    if not selectedPhotos or #selectedPhotos == 0 then
        CommonV2.show_warning("Nenhuma foto selecionada. Por favor, seleciona pelo menos uma foto.")
        return nil
    end

    return selectedPhotos
end

local function collect_photo_data(photos)
    -- Recolhe dados de todas as fotos selecionadas
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
            CommonV2.log_warn("MarkBestPhotos", "Foto sem caminho válido, ignorada")
        end
    end

    return photo_data
end

local function show_selection_dialog(num_photos)
    -- Mostra diálogo para escolher critério de seleção
    -- Retorna {mode: "percentage"|"absolute", value: number} ou nil se cancelado

    return LrFunctionContext.callWithContext("SelectionDialog", function(context)
        local f = LrView.osFactory()
        local props = LrBinding.makePropertyTable(context)

        props.mode = "percentage" -- "percentage" ou "absolute"
        props.percentage_value = 20 -- Top 20% por defeito
        props.absolute_value = math.min(10, num_photos) -- Top 10 fotos por defeito

        -- Cálculo dinâmico de quantas fotos serão marcadas
        local function calculate_count()
            if props.mode == "percentage" then
                return math.max(1, math.floor(num_photos * props.percentage_value / 100))
            else
                return math.min(props.absolute_value, num_photos)
            end
        end

        props.calculated_count = calculate_count()

        -- Observer para atualizar contagem
        props:addObserver('mode', function()
            props.calculated_count = calculate_count()
        end)

        props:addObserver('percentage_value', function()
            if props.mode == "percentage" then
                props.calculated_count = calculate_count()
            end
        end)

        props:addObserver('absolute_value', function()
            if props.mode == "absolute" then
                props.calculated_count = calculate_count()
            end
        end)

        local contents = f:column {
            spacing = f:control_spacing(),
            fill_horizontal = 1,

            f:static_text {
                title = "Marcar Melhores Fotos",
                font = "<system/bold>",
                size = "large",
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = string.format("Total de fotos selecionadas: %d", num_photos),
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = "Critério de seleção:",
                font = "<system/bold>",
            },

            f:radio_button {
                title = "Percentagem das melhores",
                value = LrView.bind('mode'),
                checked_value = "percentage",
            },

            f:row {
                spacing = f:label_spacing(),
                fill_horizontal = 1,

                f:static_text {
                    title = "Top:",
                    enabled = LrView.bind {
                        key = 'mode',
                        transform = function(value)
                            return value == "percentage"
                        end
                    },
                },

                f:slider {
                    value = LrView.bind('percentage_value'),
                    min = 5,
                    max = 100,
                    integral = true,
                    width = 200,
                    enabled = LrView.bind {
                        key = 'mode',
                        transform = function(value)
                            return value == "percentage"
                        end
                    },
                },

                f:static_text {
                    title = LrView.bind {
                        key = 'percentage_value',
                        transform = function(value)
                            return string.format("%d%%", value)
                        end
                    },
                    enabled = LrView.bind {
                        key = 'mode',
                        transform = function(value)
                            return value == "percentage"
                        end
                    },
                },
            },

            f:separator { fill_horizontal = 1 },

            f:radio_button {
                title = "Número absoluto de fotos",
                value = LrView.bind('mode'),
                checked_value = "absolute",
            },

            f:row {
                spacing = f:label_spacing(),
                fill_horizontal = 1,

                f:static_text {
                    title = "Marcar as melhores:",
                    enabled = LrView.bind {
                        key = 'mode',
                        transform = function(value)
                            return value == "absolute"
                        end
                    },
                },

                f:slider {
                    value = LrView.bind('absolute_value'),
                    min = 1,
                    max = num_photos,
                    integral = true,
                    width = 200,
                    enabled = LrView.bind {
                        key = 'mode',
                        transform = function(value)
                            return value == "absolute"
                        end
                    },
                },

                f:static_text {
                    title = LrView.bind {
                        key = 'absolute_value',
                        transform = function(value)
                            return string.format("%d fotos", value)
                        end
                    },
                    enabled = LrView.bind {
                        key = 'mode',
                        transform = function(value)
                            return value == "absolute"
                        end
                    },
                },
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = LrView.bind {
                    keys = {'calculated_count'},
                    operation = function(binder, values)
                        return string.format("Serão marcadas %d fotos com pick flag", values.calculated_count)
                    end
                },
                font = "<system/bold>",
            },
        }

        local result = LrDialogs.presentModalDialog {
            title = "NSP - Marcar Melhores Fotos",
            contents = contents,
            actionVerb = "Marcar",
            cancelVerb = "Cancelar",
        }

        if result == "ok" then
            return {
                mode = props.mode,
                value = props.mode == "percentage" and props.percentage_value or props.absolute_value,
                count = props.calculated_count
            }
        else
            return nil
        end
    end)
end

-- ============================================================================
-- LÓGICA PRINCIPAL
-- ============================================================================

local function mark_best_photos()
    -- Função principal que marca as melhores fotos

    LrTasks.startAsyncTask(function()
        -- 1. Verificar que o servidor está disponível
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor AI não está disponível. Inicia o servidor primeiro através do menu 'Iniciar Servidor AI'.")
            return
        end

        -- 2. Obter fotos selecionadas
        local photos = get_selected_photos()
        if not photos then
            return
        end

        local num_photos = #photos
        CommonV2.log_info("MarkBestPhotos", "A processar " .. num_photos .. " fotos")

        -- 3. Mostrar diálogo de seleção
        local selection = show_selection_dialog(num_photos)
        if not selection then
            CommonV2.log_info("MarkBestPhotos", "Utilizador cancelou")
            return
        end

        CommonV2.log_info("MarkBestPhotos", string.format(
            "Critério: %s = %s, marcar %d fotos",
            selection.mode,
            tostring(selection.value),
            selection.count
        ))

        -- 4. Recolher dados das fotos
        local progress = LrProgressScope({
            title = "NSP - Marcar Melhores Fotos",
            functionContext = nil,
        })

        progress:setCaption("A preparar fotos para análise...")

        local photo_data = collect_photo_data(photos)

        if not photo_data or #photo_data == 0 then
            progress:done()
            CommonV2.show_error("Nenhuma foto válida para análise.")
            return
        end

        -- 5. Preparar dados para API
        local image_paths = {}
        local exif_data_list = {}

        for _, data in ipairs(photo_data) do
            table.insert(image_paths, data.path)
            table.insert(exif_data_list, data.exif)
        end

        -- 6. Chamar API de culling
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

        CommonV2.log_info("MarkBestPhotos", "Análise concluída: " .. #scores .. " scores recebidos")

        -- 7. Associar scores às fotos
        for i, data in ipairs(photo_data) do
            data.score = scores[i]
        end

        -- 8. Ordenar por score (melhor primeiro)
        table.sort(photo_data, function(a, b)
            return (a.score or 0) > (b.score or 0)
        end)

        -- 9. Marcar as melhores com pick flag
        progress:setCaption("A marcar fotos...")

        local catalog = LrApplication.activeCatalog()
        local marked_count = 0

        catalog:withWriteAccessDo("Mark Best Photos", function()
            for i = 1, selection.count do
                local data = photo_data[i]
                if data and data.photo then
                    data.photo:setRawMetadata("pickStatus", 1) -- 1 = picked
                    marked_count = marked_count + 1
                    CommonV2.log_debug("MarkBestPhotos", string.format(
                        "Marcada: %s (score: %.1f)",
                        data.filename,
                        data.score or 0
                    ))
                end
            end
        end)

        progress:done()

        -- 10. Mostrar resultado
        local message = string.format(
            "%d fotos marcadas com pick flag\n\n" ..
            "Critério usado: %s %s",
            marked_count,
            selection.mode == "percentage" and "Top" or "Melhores",
            selection.mode == "percentage" and (selection.value .. "%") or (selection.value .. " fotos")
        )

        CommonV2.show_info(message)
        CommonV2.log_info("MarkBestPhotos", "Operação concluída: " .. marked_count .. " fotos marcadas")
    end)
end

-- ============================================================================
-- PONTO DE ENTRADA
-- ============================================================================

-- Executar a função principal
mark_best_photos()
