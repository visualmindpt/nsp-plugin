-- PresetManager.lua
-- Gestor de presets do NSP Plugin
-- Permite listar, ativar e desinstalar presets instalados

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NSPPlugin.PresetManager')
logger:enable("logfile")

-- Importar Common_V2 para funções auxiliares
local CommonV2 = require 'Common_V2'

-- ============================================================================
-- FUNÇÕES PRINCIPAIS
-- ============================================================================

local function preset_manager()
    -- Função principal que abre o gestor de presets

    LrTasks.startAsyncTask(function()
        -- 1. Verificar que o servidor está disponível
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor AI não está disponível. Inicia o servidor primeiro.")
            return
        end

        -- 2. Listar presets disponíveis
        local presets, err = CommonV2.list_available_presets()

        if err then
            CommonV2.show_error("Erro ao listar presets: " .. (err.message or "desconhecido"))
            return
        end

        if not presets or #presets == 0 then
            CommonV2.show_warning("Nenhum preset disponível.")
            return
        end

        CommonV2.log_info("PresetManager", "Listados " .. #presets .. " presets")

        -- 3. Obter preset ativo
        local active_preset, active_err = CommonV2.get_active_preset()
        local active_preset_id = active_preset and active_preset.id or "default"

        -- 4. Mostrar diálogo de gestão
        LrFunctionContext.callWithContext("PresetManagerDialog", function(context)
            local f = LrView.osFactory()
            local props = LrBinding.makePropertyTable(context)

            -- Preparar lista de presets
            local preset_items = {}
            for _, preset in ipairs(presets) do
                local display_name = preset.name or preset.id
                if preset.id == active_preset_id then
                    display_name = display_name .. " (ATIVO)"
                end

                table.insert(preset_items, {
                    title = display_name,
                    value = preset.id
                })
            end

            props.selected_preset = active_preset_id
            props.preset_info = ""

            -- Função para atualizar info
            local function update_preset_info()
                local selected_id = props.selected_preset

                for _, preset in ipairs(presets) do
                    if preset.id == selected_id then
                        local info_text = string.format(
                            "Nome: %s\nVersão: %s\nDescrição: %s",
                            preset.name or "N/A",
                            preset.version or "N/A",
                            preset.description or "Sem descrição"
                        )
                        props.preset_info = info_text
                        break
                    end
                end
            end

            update_preset_info()

            props:addObserver("selected_preset", function()
                update_preset_info()
            end)

            local contents = f:column {
                spacing = f:control_spacing(),
                fill_horizontal = 1,

                f:static_text {
                    title = "Gestor de Presets NSP",
                    font = "<system/bold>",
                },

                f:separator { fill_horizontal = 1 },

                f:popup_menu {
                    items = preset_items,
                    value = LrView.bind('selected_preset'),
                },

                f:edit_field {
                    value = LrView.bind('preset_info'),
                    height_in_lines = 6,
                    width_in_chars = 40,
                    enabled = false,
                },

                f:push_button {
                    title = "Ativar Preset",
                    action = function()
                        local selected_id = props.selected_preset

                        if selected_id == active_preset_id then
                            CommonV2.show_info("Este preset já está ativo.")
                            return
                        end

                        local success, set_err = CommonV2.set_active_preset(selected_id)

                        if success then
                            CommonV2.show_info("Preset ativado!")
                            active_preset_id = selected_id
                            update_preset_info()
                        else
                            CommonV2.show_error("Erro ao ativar preset.")
                        end
                    end,
                },
            }

            LrDialogs.presentModalDialog {
                title = "NSP - Gestor de Presets",
                contents = contents,
                actionVerb = "Fechar",
            }
        end)
    end)
end

-- ============================================================================
-- PONTO DE ENTRADA
-- ============================================================================

preset_manager()
