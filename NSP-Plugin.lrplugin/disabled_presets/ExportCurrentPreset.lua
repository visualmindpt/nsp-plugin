-- ExportCurrentPreset.lua
-- Exporta os develop settings atuais da foto como preset .nsppreset
-- Permite guardar e partilhar presets personalizados

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'

local logger = LrLogger('NSPPlugin.ExportCurrentPreset')
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

local function show_export_dialog()
    -- Mostra diálogo para configurar exportação do preset
    -- Retorna {name, author, description, category, output_path} ou nil se cancelado

    return LrFunctionContext.callWithContext("ExportDialog", function(context)
        local f = LrView.osFactory()
        local props = LrBinding.makePropertyTable(context)

        -- Valores por defeito
        props.preset_name = "Meu Preset Custom"
        props.preset_author = "Utilizador"  -- Lua não tem os.getenv
        props.preset_description = ""
        props.preset_category = "Custom"

        -- Obter Desktop do utilizador como localização padrão
        local desktop_path = LrPathUtils.getStandardFilePath("desktop")
        props.output_folder = desktop_path

        local contents = f:column {
            spacing = f:control_spacing(),
            fill_horizontal = 1,

            f:static_text {
                title = "Exportar Preset Atual",
                font = "<system/bold>",
                size = "large",
            },

            f:separator { fill_horizontal = 1 },

            f:row {
                spacing = f:label_spacing(),

                f:static_text {
                    title = "Nome do Preset:",
                    alignment = 'right',
                    width = LrView.share 'label_width',
                },

                f:edit_field {
                    value = LrView.bind('preset_name'),
                    width_in_chars = 30,
                    immediate = true,
                },
            },

            f:row {
                spacing = f:label_spacing(),

                f:static_text {
                    title = "Autor:",
                    alignment = 'right',
                    width = LrView.share 'label_width',
                },

                f:edit_field {
                    value = LrView.bind('preset_author'),
                    width_in_chars = 30,
                    immediate = true,
                },
            },

            f:row {
                spacing = f:label_spacing(),

                f:static_text {
                    title = "Categoria:",
                    alignment = 'right',
                    width = LrView.share 'label_width',
                },

                f:popup_menu {
                    value = LrView.bind('preset_category'),
                    items = {
                        { title = "Custom", value = "Custom" },
                        { title = "Portrait", value = "Portrait" },
                        { title = "Landscape", value = "Landscape" },
                        { title = "Black & White", value = "BW" },
                        { title = "Vintage", value = "Vintage" },
                        { title = "Cinematic", value = "Cinematic" },
                        { title = "Other", value = "Other" },
                    },
                    width = 200,
                },
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = "Descrição (opcional):",
            },

            f:edit_field {
                value = LrView.bind('preset_description'),
                height_in_lines = 3,
                width_in_chars = 40,
            },

            f:separator { fill_horizontal = 1 },

            f:static_text {
                title = "Localização de destino:",
                font = "<system/bold>",
            },

            f:row {
                spacing = f:label_spacing(),

                f:edit_field {
                    value = LrView.bind('output_folder'),
                    width_in_chars = 35,
                    enabled = false,
                },

                f:push_button {
                    title = "Escolher...",
                    action = function()
                        local folder = LrDialogs.runOpenPanel({
                            title = "Escolher pasta de destino",
                            canChooseFiles = false,
                            canChooseDirectories = true,
                            canCreateDirectories = true,
                            allowsMultipleSelection = false,
                        })

                        if folder and folder[1] then
                            props.output_folder = folder[1]
                        end
                    end,
                },
            },
        }

        local result = LrDialogs.presentModalDialog {
            title = "NSP - Exportar Preset",
            contents = contents,
            actionVerb = "Exportar",
            cancelVerb = "Cancelar",
        }

        if result == "ok" then
            -- Validar que nome não está vazio
            if not props.preset_name or props.preset_name == "" then
                CommonV2.show_warning("Por favor, fornece um nome para o preset.")
                return nil
            end

            -- Construir nome do ficheiro (sanitizar caracteres especiais)
            local safe_name = props.preset_name:gsub("[^%w%s%-_]", ""):gsub("%s+", "_")
            local filename = safe_name .. ".nsppreset"
            local output_path = LrPathUtils.child(props.output_folder, filename)

            return {
                name = props.preset_name,
                author = props.preset_author,
                description = props.preset_description ~= "" and props.preset_description or nil,
                category = props.preset_category,
                output_path = output_path
            }
        else
            return nil
        end
    end)
end

-- ============================================================================
-- LÓGICA PRINCIPAL
-- ============================================================================

local function export_current_preset()
    -- Função principal que exporta o preset

    LrTasks.startAsyncTask(function()
        -- 1. Obter foto selecionada
        local photo = get_selected_photo()
        if not photo then
            return
        end

        -- 2. Capturar settings atuais
        local settings = CommonV2.capture_current_settings(photo)
        if not settings then
            CommonV2.show_error("Não foi possível capturar os settings atuais da foto.")
            return
        end

        CommonV2.log_info("ExportCurrentPreset", "Settings capturados com sucesso")

        -- 3. Mostrar diálogo de exportação
        local config = show_export_dialog()
        if not config then
            CommonV2.log_info("ExportCurrentPreset", "Utilizador cancelou exportação")
            return
        end

        CommonV2.log_info("ExportCurrentPreset", "A exportar preset: " .. config.name)

        -- 4. Converter settings para formato de sliders
        local sliders = CommonV2.collect_develop_vector(photo)

        -- 5. Construir estrutura do preset
        local preset_data = {
            format_version = "1.0",
            preset_info = {
                name = config.name,
                version = "1.0.0",
                author = config.author,
                description = config.description,
                category = config.category,
                created_at = os.date("%Y-%m-%d %H:%M:%S"),
                is_default = false,
            },
            sliders = sliders,
            metadata = {
                exported_from = "NSP Plugin - Lightroom",
                source_photo = photo:getFormattedMetadata('fileName') or "unknown",
                lightroom_version = "Classic",
            }
        }

        -- 6. Serializar para JSON
        local JSON = require 'json'
        local ok, json_str = pcall(function()
            return JSON.encode(preset_data)
        end)

        if not ok then
            CommonV2.log_error("ExportCurrentPreset", "Falha ao serializar preset: " .. tostring(json_str))
            CommonV2.show_error("Erro ao criar ficheiro de preset: falha na serialização")
            return
        end

        -- 7. Escrever para ficheiro
        local file_ok, file_err = pcall(function()
            local file = io.open(config.output_path, "w")
            if not file then
                error("Não foi possível criar ficheiro")
            end
            file:write(json_str)
            file:close()
        end)

        if not file_ok then
            CommonV2.log_error("ExportCurrentPreset", "Erro ao escrever ficheiro: " .. tostring(file_err))
            CommonV2.show_error("Erro ao escrever ficheiro: " .. tostring(file_err))
            return
        end

        CommonV2.log_info("ExportCurrentPreset", "Preset exportado para: " .. config.output_path)

        -- 8. Mostrar sucesso com informação do ficheiro
        local file_size = LrFileUtils.fileAttributes(config.output_path).fileSize or 0
        local file_size_kb = math.floor(file_size / 1024 * 10 + 0.5) / 10

        local message = string.format(
            "Preset exportado com sucesso!\n\n" ..
            "Nome: %s\n" ..
            "Localização: %s\n" ..
            "Tamanho: %.1f KB\n\n" ..
            "Podes partilhar este ficheiro .nsppreset com outros utilizadores.",
            config.name,
            config.output_path,
            file_size_kb
        )

        CommonV2.show_info(message)

        -- 9. Perguntar se quer revelar no Finder (macOS) ou Explorer (Windows)
        local reveal = LrDialogs.confirm(
            "Preset exportado",
            "Queres abrir a pasta onde o preset foi guardado?",
            "Abrir Pasta",
            "Fechar"
        )

        if reveal == "ok" then
            -- Revelar ficheiro no Finder/Explorer
            if MAC_ENV then
                LrTasks.execute('open -R "' .. config.output_path .. '"')
            else
                LrTasks.execute('explorer /select,"' .. config.output_path .. '"')
            end
        end
    end)
end

-- ============================================================================
-- PONTO DE ENTRADA
-- ============================================================================

-- Executar a função principal
export_current_preset()
