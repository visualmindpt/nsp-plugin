-- PreviewBeforeAfter.lua
-- Preview com comparação lado-a-lado antes/depois da aplicação AI
-- Permite ao utilizador ver o resultado antes de aplicar permanentemente

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrProgressScope = import 'LrProgressScope'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NSPPlugin.PreviewBeforeAfter')
logger:enable("logfile")

-- Importar Common_V2 para funções auxiliares
local CommonV2 = require 'Common_V2'

-- ============================================================================
-- FUNÇÕES AUXILIARES
-- ============================================================================

local function get_selected_photo()
    -- Obtém a foto atualmente selecionada
    local catalog = LrApplication.activeCatalog()
    local targetPhoto = catalog:getTargetPhoto()

    if not targetPhoto then
        CommonV2.show_warning("Nenhuma foto selecionada. Por favor, seleciona uma foto.")
        return nil
    end

    return targetPhoto
end

local function validate_photo(photo)
    -- Valida que a foto tem os metadados necessários
    local is_valid, error_or_dims = CommonV2.validate_exif(photo)

    if not is_valid then
        CommonV2.show_error("Foto inválida: " .. tostring(error_or_dims))
        return false
    end

    return true
end

local function get_exif_data(photo)
    -- Extrai EXIF relevante da foto
    local raw_meta = photo:getRawMetadata()

    return {
        iso = raw_meta.isoSpeedRating or 0,
        aperture = raw_meta.aperture or 0,
        shutterspeed = raw_meta.shutterSpeed or 0,
        focallength = raw_meta.focalLength or 0,
        make = raw_meta.cameraMake or "",
        model = raw_meta.cameraModel or "",
    }
end

-- ============================================================================
-- LÓGICA PRINCIPAL
-- ============================================================================

local function preview_before_after()
    -- Função principal que executa o preview antes/depois

    LrTasks.startAsyncTask(function()
        -- 1. Verificar que o servidor está disponível
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor AI não está disponível. Inicia o servidor primeiro através do menu 'Iniciar Servidor AI'.")
            return
        end

        -- 2. Obter foto selecionada
        local photo = get_selected_photo()
        if not photo then
            return
        end

        -- 3. Validar foto
        if not validate_photo(photo) then
            return
        end

        -- 4. Capturar settings originais ANTES de qualquer operação
        local original_settings = CommonV2.capture_current_settings(photo)
        if not original_settings then
            CommonV2.show_error("Não foi possível capturar os settings atuais da foto.")
            return
        end

        CommonV2.log_info("PreviewBeforeAfter", "Settings originais capturados com sucesso")

        -- 5. Obter caminho da imagem e EXIF
        local image_path = photo:getRawMetadata("path")
        if not image_path then
            CommonV2.show_error("Não foi possível obter o caminho da imagem.")
            return
        end

        local exif_data = get_exif_data(photo)

        -- 6. Fazer predição AI
        local progress = LrProgressScope({
            title = "NSP - Preview AI",
            functionContext = nil,
        })

        progress:setCaption("A obter sugestões AI...")

        local prediction, err = CommonV2.predict_v2(image_path, exif_data)

        if err then
            progress:done()
            CommonV2.show_error("Erro ao obter predição AI: " .. (err.message or "desconhecido"))
            return
        end

        if not prediction or not prediction.sliders then
            progress:done()
            CommonV2.show_error("Predição AI inválida ou vazia.")
            return
        end

        CommonV2.log_info("PreviewBeforeAfter", "Predição obtida: preset_id=" .. tostring(prediction.preset_id))

        -- 7. Construir develop settings AI
        local ai_settings = CommonV2.build_develop_settings(prediction.sliders)
        if not ai_settings or next(ai_settings) == nil then
            progress:done()
            CommonV2.show_error("Não foi possível construir settings AI.")
            return
        end

        CommonV2.log_info("PreviewBeforeAfter", "Settings AI construídos com sucesso")

        progress:done()

        -- 8. Mostrar diálogo de preview interativo
        LrFunctionContext.callWithContext("PreviewDialog", function(context)
            local f = LrView.osFactory()
            local props = LrBinding.makePropertyTable(context)

            -- Começamos a mostrar o DEPOIS (AI aplicado)
            props.current_view = "after" -- "before" ou "after"
            props.view_label = "A mostrar: DEPOIS (AI)"

            -- Aplicar já o preset AI para a vista inicial
            local catalog = LrApplication.activeCatalog()
            catalog:withWriteAccessDo("Apply AI Preview (initial after)", function()
                photo:applyDevelopSettings(ai_settings)
            end, { timeout = 5 })

            -- Formatar informação do preset
            local preset_info = CommonV2.format_preset_info(
                prediction.preset_id,
                prediction.preset_confidence
            )

            -- Contador de alterações significativas
            local significant_changes = 0
            local change_list = {}

            for slider_name, value in pairs(prediction.sliders) do
                local abs_value = math.abs(tonumber(value) or 0)
                if abs_value > 5 then -- Mudanças > 5 são significativas
                    significant_changes = significant_changes + 1
                    local mapping = CommonV2.PYTHON_TO_LR[slider_name]
                    local display_name = mapping and mapping.display_name or slider_name
                    local formatted = CommonV2.format_slider_value(slider_name, value)
                    table.insert(change_list, display_name .. ": " .. formatted)
                end
            end

            -- Limitar lista a top 8 mudanças
            local changes_text = ""
            if #change_list > 0 then
                for i = 1, math.min(8, #change_list) do
                    changes_text = changes_text .. change_list[i] .. "\n"
                end
                if #change_list > 8 then
                    changes_text = changes_text .. "... e mais " .. (#change_list - 8) .. " ajustes"
                end
            else
                changes_text = "Ajustes subtis aplicados"
            end

            -- Função para alternar entre antes/depois
            local function toggle_view()
                LrTasks.startAsyncTask(function()
                    if props.current_view == "before" then
                        -- Aplicar settings AI
                        props.current_view = "after"
                        props.view_label = "A mostrar: DEPOIS (AI)"

                        local catalog = LrApplication.activeCatalog()
                        catalog:withWriteAccessDo("Apply AI Preview", function()
                            photo:applyDevelopSettings(ai_settings)
                        end, { timeout = 5 })

                        CommonV2.log_debug("PreviewBeforeAfter", "A mostrar DEPOIS (AI aplicado)")
                    else
                        -- Reverter para settings originais
                        props.current_view = "before"
                        props.view_label = "A mostrar: ANTES"

                        local catalog = LrApplication.activeCatalog()
                        catalog:withWriteAccessDo("Revert to Original", function()
                            photo:applyDevelopSettings(original_settings)
                        end, { timeout = 5 })

                        CommonV2.log_debug("PreviewBeforeAfter", "A mostrar ANTES (revertido)")
                    end
                end)
            end

            local contents = f:column {
                spacing = f:control_spacing(),
                fill_horizontal = 1,

                f:static_text {
                    title = "Preview Antes/Depois - AI Preset",
                    font = "<system/bold>",
                    size = "large",
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = preset_info,
                    font = "<system>",
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = "Principais ajustes sugeridos:",
                    font = "<system/bold>",
                },

                f:edit_field {
                    value = changes_text,
                    height_in_lines = 8,
                    width_in_chars = 40,
                    enabled = false,
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = LrView.bind('view_label'),
                    font = "<system/bold>",
                },

                f:row {
                    spacing = f:control_spacing(),
                    fill_horizontal = 1,

                    f:push_button {
                        title = "⇄ Alternar Antes/Depois",
                        action = function()
                            toggle_view()
                        end,
                        width = 180,
                    },
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = "Escolhe uma ação:",
                    font = "<system/bold>",
                },
            }

            local result = LrDialogs.presentModalDialog {
                title = "NSP - Preview AI",
                contents = contents,
                actionVerb = "✓ Aplicar Definitivamente",
                otherVerb = "✎ Ajustar Manualmente",
                cancelVerb = "✗ Cancelar",
                -- Dica: Mantemos modal mais estreito para não tapar tanto a foto
                preferredWidth = 420,
            }

            -- Processar resultado (aguardar um pouco para garantir que toggle anterior terminou)
            LrTasks.sleep(0.5)

            if result == "ok" then
                -- Aplicar definitivamente
                CommonV2.log_info("PreviewBeforeAfter", "Utilizador escolheu aplicar definitivamente")

                local catalog = LrApplication.activeCatalog()
                catalog:withWriteAccessDo("Apply AI Preset", function()
                    photo:applyDevelopSettings(ai_settings)

                    -- Guardar metadata da predição dentro do mesmo write access
                    CommonV2.save_prediction_metadata(photo, prediction)
                end, { timeout = 10 })

                -- Solicitar feedback se apropriado (fora do write access)
                CommonV2.handle_post_apply_feedback(photo, prediction)

                CommonV2.show_info("Preset AI aplicado com sucesso!")

            elseif result == "other" then
                -- Aplicar e deixar utilizador ajustar
                CommonV2.log_info("PreviewBeforeAfter", "Utilizador escolheu ajustar manualmente")

                local catalog = LrApplication.activeCatalog()
                catalog:withWriteAccessDo("Apply AI Preset for Manual Adjustment", function()
                    photo:applyDevelopSettings(ai_settings)

                    -- Guardar metadata da predição dentro do mesmo write access
                    CommonV2.save_prediction_metadata(photo, prediction)
                end, { timeout = 10 })

                CommonV2.show_info("Preset AI aplicado como ponto de partida. Podes ajustar manualmente agora.")

            else
                -- Cancelar - reverter para original
                CommonV2.log_info("PreviewBeforeAfter", "Utilizador cancelou")

                local catalog = LrApplication.activeCatalog()
                catalog:withWriteAccessDo("Cleanup Preview", function()
                    photo:applyDevelopSettings(original_settings)
                end, { timeout = 5 })

                CommonV2.show_info("Operação cancelada. Foto não foi alterada.")
            end
        end)
    end)
end

-- ============================================================================
-- PONTO DE ENTRADA
-- ============================================================================

-- Executar a função principal
preview_before_after()
