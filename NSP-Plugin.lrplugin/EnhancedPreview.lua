-- EnhancedPreview.lua
-- Enhanced Preview with Undo/Redo, Progress Bars, and Visual Comparison
-- Comprehensive UI/UX improvements for NSP Plugin

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrProgressScope = import 'LrProgressScope'
local LrLogger = import 'LrLogger'
local LrDevelopController = import 'LrDevelopController'

local logger = LrLogger('NSPPlugin.EnhancedPreview')
logger:enable("logfile")

local CommonV2 = require 'Common_V2'

local function get_dim_text_color()
    if LrView.colorCode and type(LrView.colorCode) == "function" then
        return LrView.colorCode("dim")
    end
    return { red = 0.6, green = 0.6, blue = 0.6 }
end

-- ============================================================================
-- UNDO/REDO SYSTEM
-- ============================================================================

local UndoRedoSystem = {}

function UndoRedoSystem:new()
    local obj = {
        history = {},       -- Stack de estados
        current_index = 0,  -- Índice atual no histórico
        max_history = 20,   -- Limite de estados guardados
    }
    setmetatable(obj, self)
    self.__index = self
    return obj
end

function UndoRedoSystem:save_state(photo, settings, description)
    -- Remove estados à frente se estivermos no meio do histórico
    while #self.history > self.current_index do
        table.remove(self.history)
    end

    -- Adiciona novo estado
    local state = {
        settings = settings,
        description = description or "Estado",
        timestamp = os.time(),
    }

    table.insert(self.history, state)
    self.current_index = #self.history

    -- Limita tamanho do histórico
    if #self.history > self.max_history then
        table.remove(self.history, 1)
        self.current_index = self.current_index - 1
    end

    CommonV2.log_info("UndoRedo", string.format("Estado salvo: %s (total: %d)", description, #self.history))
end

function UndoRedoSystem:can_undo()
    return self.current_index > 1
end

function UndoRedoSystem:can_redo()
    return self.current_index < #self.history
end

function UndoRedoSystem:undo(photo)
    if not self:can_undo() then
        return false, "Nenhum estado para desfazer"
    end

    self.current_index = self.current_index - 1
    local state = self.history[self.current_index]

    local catalog = LrApplication.activeCatalog()
    catalog:withWriteAccessDo("Undo", function()
        photo:applyDevelopSettings(state.settings)
    end, { timeout = 5 })

    CommonV2.log_info("UndoRedo", "Undo: " .. state.description)
    return true, state.description
end

function UndoRedoSystem:redo(photo)
    if not self:can_redo() then
        return false, "Nenhum estado para refazer"
    end

    self.current_index = self.current_index + 1
    local state = self.history[self.current_index]

    local catalog = LrApplication.activeCatalog()
    catalog:withWriteAccessDo("Redo", function()
        photo:applyDevelopSettings(state.settings)
    end, { timeout = 5 })

    CommonV2.log_info("UndoRedo", "Redo: " .. state.description)
    return true, state.description
end

function UndoRedoSystem:get_current_description()
    if self.current_index > 0 and self.current_index <= #self.history then
        return self.history[self.current_index].description
    end
    return "Nenhum estado"
end

-- ============================================================================
-- ENHANCED PROGRESS DIALOG
-- ============================================================================

local function create_enhanced_progress(title, steps)
    local progress = LrProgressScope({
        title = title,
        functionContext = nil,
    })

    local current_step = 0

    return {
        progress = progress,
        total_steps = #steps,
        current_step = 0,

        next_step = function(self, custom_caption)
            self.current_step = self.current_step + 1
            if self.current_step <= self.total_steps then
                local step_name = steps[self.current_step]
                local caption = custom_caption or step_name
                self.progress:setCaption(string.format("[%d/%d] %s", self.current_step, self.total_steps, caption))
                self.progress:setPortionComplete(self.current_step - 1, self.total_steps)
                CommonV2.log_info("Progress", caption)
            end
        end,

        done = function(self)
            self.progress:done()
        end,

        is_cancelled = function(self)
            return self.progress:isCanceled()
        end
    }
end

-- ============================================================================
-- ENHANCED PREVIEW WITH COMPARISON SLIDER
-- ============================================================================

local function show_enhanced_preview()
    LrTasks.startAsyncTask(function()
        -- Step 1: Verificar servidor
        local steps = {
            "Verificando servidor AI...",
            "Validando foto selecionada...",
            "Capturando estado original...",
            "Obtendo predição AI...",
            "Preparando preview..."
        }

        local enhanced_progress = create_enhanced_progress("NSP - Enhanced Preview", steps)

        enhanced_progress:next_step()
        if not CommonV2.ensure_server() then
            enhanced_progress:done()
            CommonV2.show_error("Servidor AI não está disponível. Inicia o servidor primeiro.")
            return
        end

        -- Step 2: Obter foto
        enhanced_progress:next_step()
        local catalog = LrApplication.activeCatalog()
        local photo = catalog:getTargetPhoto()

        if not photo then
            enhanced_progress:done()
            CommonV2.show_error("Nenhuma foto selecionada.")
            return
        end

        -- Step 3: Validar e capturar estado
        local is_valid, error_or_dims = CommonV2.validate_exif(photo)
        if not is_valid then
            enhanced_progress:done()
            CommonV2.show_error("Foto inválida: " .. tostring(error_or_dims))
            return
        end

        enhanced_progress:next_step()
        local original_settings = CommonV2.capture_current_settings(photo)
        if not original_settings then
            enhanced_progress:done()
            CommonV2.show_error("Não foi possível capturar settings originais.")
            return
        end

        -- Step 4: Obter predição
        enhanced_progress:next_step()
        local image_path = photo:getRawMetadata("path")
        local raw_meta = photo:getRawMetadata()
        local exif_data = {
            iso = raw_meta.isoSpeedRating or 0,
            width = tonumber(error_or_dims.width),
            height = tonumber(error_or_dims.height),
        }

        local prediction, err = CommonV2.predict_v2(image_path, exif_data)

        if err or not prediction or not prediction.sliders then
            enhanced_progress:done()
            CommonV2.show_error("Erro ao obter predição AI: " .. (err and err.message or "resposta inválida"))
            return
        end

        -- Step 5: Construir settings AI
        enhanced_progress:next_step()
        local ai_settings = CommonV2.build_develop_settings(prediction.sliders)
        if not ai_settings or next(ai_settings) == nil then
            enhanced_progress:done()
            CommonV2.show_error("Não foi possível construir settings AI.")
            return
        end

        enhanced_progress:done()

        -- Inicializar sistema Undo/Redo
        local undo_redo = UndoRedoSystem:new()
        undo_redo:save_state(photo, original_settings, "Original")

        -- Aplicar AI como segundo estado
        catalog:withWriteAccessDo("Apply AI Preview", function()
            photo:applyDevelopSettings(ai_settings)
        end, { timeout = 5 })

        undo_redo:save_state(photo, ai_settings, "AI Sugerido")

        -- Step 6: Mostrar dialog avançado
        LrFunctionContext.callWithContext("EnhancedPreviewDialog", function(context)
            local f = LrView.osFactory()
            local props = LrBinding.makePropertyTable(context)

            props.comparison_mode = "split"  -- "toggle", "split", "side_by_side"
            props.view_state = "after"       -- "before", "after"
            props.undo_enabled = undo_redo:can_undo()
            props.redo_enabled = undo_redo:can_redo()
            props.current_state = undo_redo:get_current_description()
            props.slider_position = 50  -- Para modo split (0-100)

            -- Preparar lista de alterações
            local changes_list = {}
            for slider_name, value in pairs(prediction.sliders) do
                local abs_value = math.abs(tonumber(value) or 0)
                if abs_value > 3 then
                    local mapping = CommonV2.PYTHON_TO_LR[slider_name]
                    local display_name = mapping and mapping.display_name or slider_name
                    local formatted = CommonV2.format_slider_value(slider_name, value)
                    table.insert(changes_list, string.format("%s: %s", display_name, formatted))
                end
            end

            local changes_text = table.concat(changes_list, "\n")
            if changes_text == "" then
                changes_text = "Ajustes subtis aplicados"
            end

            -- Funções de controle
            local function toggle_view()
                LrTasks.startAsyncTask(function()
                    if props.view_state == "before" then
                        props.view_state = "after"
                        catalog:withWriteAccessDo("Show After", function()
                            photo:applyDevelopSettings(ai_settings)
                        end, { timeout = 5 })
                    else
                        props.view_state = "before"
                        catalog:withWriteAccessDo("Show Before", function()
                            photo:applyDevelopSettings(original_settings)
                        end, { timeout = 5 })
                    end
                end)
            end

            local function do_undo()
                LrTasks.startAsyncTask(function()
                    local ok, desc = undo_redo:undo(photo)
                    if ok then
                        props.current_state = undo_redo:get_current_description()
                        props.undo_enabled = undo_redo:can_undo()
                        props.redo_enabled = undo_redo:can_redo()
                        CommonV2.log_info("EnhancedPreview", "Undo para: " .. desc)
                    end
                end)
            end

            local function do_redo()
                LrTasks.startAsyncTask(function()
                    local ok, desc = undo_redo:redo(photo)
                    if ok then
                        props.current_state = undo_redo:get_current_description()
                        props.undo_enabled = undo_redo:can_undo()
                        props.redo_enabled = undo_redo:can_redo()
                        CommonV2.log_info("EnhancedPreview", "Redo para: " .. desc)
                    end
                end)
            end

            -- UI
            local contents = f:column {
                spacing = f:control_spacing(),
                fill_horizontal = 1,

                f:row {
                    f:static_text {
                        title = "Enhanced Preview - AI Preset",
                        font = "<system/bold>",
                        size = "large",
                    },
                    f:spacer { fill_horizontal = 1 },
                    f:static_text {
                        title = string.format("Preset: %d | Confiança: %.0f%%",
                            prediction.preset_id,
                            prediction.preset_confidence * 100),
                        font = "<system>",
                    },
                },

                f:separator { fill_horizontal = 1 },

                -- Controles de comparação
                f:group_box {
                    title = "Comparação Antes/Depois",
                    fill_horizontal = 1,

                    f:column {
                        spacing = f:control_spacing(),

                        f:row {
                            spacing = f:control_spacing(),

                            f:push_button {
                                title = "⇄ Alternar Vista",
                                action = toggle_view,
                                width = 140,
                            },

                            f:static_text {
                                title = LrView.bind {
                                    key = 'view_state',
                                    transform = function(value)
                                        return value == "before" and "A mostrar: ANTES" or "A mostrar: DEPOIS (AI)"
                                    end
                                },
                                font = "<system/bold>",
                            },
                        },
                    },
                },

                f:separator { fill_horizontal = 1 },

                -- Undo/Redo controls
                f:group_box {
                    title = "Histórico de Edição",
                    fill_horizontal = 1,

                    f:column {
                        spacing = f:control_spacing(),

                        f:row {
                            spacing = f:control_spacing(),

                            f:push_button {
                                title = "↶ Desfazer",
                                action = do_undo,
                                enabled = LrView.bind('undo_enabled'),
                                width = 100,
                            },

                            f:push_button {
                                title = "↷ Refazer",
                                action = do_redo,
                                enabled = LrView.bind('redo_enabled'),
                                width = 100,
                            },

                            f:spacer { fill_horizontal = 1 },

                            f:static_text {
                                title = LrView.bind('current_state'),
                                font = "<system/bold>",
                            },
                        },
                    },
                },

                f:separator { fill_horizontal = 1 },

                -- Lista de alterações
                f:group_box {
                    title = "Ajustes Aplicados",
                    fill_horizontal = 1,

                    f:scrolled_view {
                        width = 500,
                        height = 150,

                        f:edit_field {
                            value = changes_text,
                            height_in_lines = 10,
                            enabled = false,
                        },
                    },
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = "Dica: Use ↶ Desfazer/↷ Refazer para navegar entre estados ou ⇄ Alternar para comparar rapidamente.",
                    font = "<system/small>",
                    text_color = get_dim_text_color(),
                },
            }

            local result = LrDialogs.presentModalDialog {
                title = "NSP - Enhanced Preview",
                contents = contents,
                actionVerb = "✓ Aplicar & Fechar",
                otherVerb = "✎ Ajustar Manualmente",
                cancelVerb = "✗ Cancelar (Reverter)",
                preferredWidth = 550,
            }

            -- Processar resultado
            LrTasks.sleep(0.2)

            if result == "ok" then
                -- Aplicar estado atual
                local current_settings = CommonV2.capture_current_settings(photo)

                catalog:withWriteAccessDo("Apply Final Settings", function()
                    photo:applyDevelopSettings(current_settings)
                    CommonV2.save_prediction_metadata(photo, prediction)
                end, { timeout = 10 })

                CommonV2.handle_post_apply_feedback(photo, prediction)
                CommonV2.show_info("Preset aplicado com sucesso!")

            elseif result == "other" then
                -- Manter settings para ajuste manual
                local current_settings = CommonV2.capture_current_settings(photo)

                catalog:withWriteAccessDo("Save for Manual Adjustment", function()
                    CommonV2.save_prediction_metadata(photo, prediction)
                end, { timeout = 5 })

                CommonV2.show_info("Settings mantidos para ajuste manual.")

            else
                -- Cancelar - reverter para original
                catalog:withWriteAccessDo("Revert to Original", function()
                    photo:applyDevelopSettings(original_settings)
                end, { timeout = 5 })

                CommonV2.show_info("Operação cancelada. Foto revertida ao estado original.")
            end
        end)
    end)
end

-- ============================================================================
-- ENTRY POINT
-- ============================================================================

show_enhanced_preview()
