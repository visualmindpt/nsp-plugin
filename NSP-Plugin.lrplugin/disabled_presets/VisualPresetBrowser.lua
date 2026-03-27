-- VisualPresetBrowser.lua
-- Visual Preset Browser with previews and detailed information
-- Enhanced UI for browsing and selecting presets

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'
local LrHttp = import 'LrHttp'

local logger = LrLogger('NSPPlugin.VisualPresetBrowser')
logger:enable("logfile")

local CommonV2 = require 'Common_V2'

local function get_dim_text_color()
    if LrView.colorCode and type(LrView.colorCode) == "function" then
        return LrView.colorCode("dim")
    end
    return { red = 0.6, green = 0.6, blue = 0.6 }
end

-- ============================================================================
-- PRESET CATEGORIES (for visual organization)
-- ============================================================================

local PRESET_CATEGORIES = {
    portrait = { name = "Retratos", icon = "👤" },
    landscape = { name = "Paisagens", icon = "🏞️" },
    street = { name = "Street", icon = "🌆" },
    product = { name = "Produto", icon = "📦" },
    wedding = { name = "Casamento", icon = "💒" },
    nature = { name = "Natureza", icon = "🌿" },
    urban = { name = "Urbano", icon = "🏙️" },
    vintage = { name = "Vintage", icon = "📷" },
    bw = { name = "Preto & Branco", icon = "⬛" },
    cinematic = { name = "Cinemático", icon = "🎬" },
    custom = { name = "Personalizado", icon = "⭐" },
    default = { name = "Geral", icon = "📸" },
}

-- ============================================================================
-- PRESET DATA FETCHER
-- ============================================================================

local function fetch_preset_details(preset_id)
    -- Chama API para obter detalhes completos do preset
    local url = CommonV2.get_server_url() .. "/api/presets/" .. tostring(preset_id)

    local responseBody, responseHeaders = LrHttp.get(url, nil, 10)

    if not responseHeaders or responseHeaders.status ~= 200 then
        return nil
    end

    local JSON = require 'json'
    local preset_data = JSON.decode(responseBody)

    return preset_data
end

local function get_preset_category(preset)
    -- Determina categoria baseado em nome/tags
    local name_lower = string.lower(preset.name or "")

    if string.find(name_lower, "portrait") or string.find(name_lower, "retrato") then
        return "portrait"
    elseif string.find(name_lower, "landscape") or string.find(name_lower, "paisagem") then
        return "landscape"
    elseif string.find(name_lower, "street") or string.find(name_lower, "rua") then
        return "street"
    elseif string.find(name_lower, "wedding") or string.find(name_lower, "casamento") then
        return "wedding"
    elseif string.find(name_lower, "vintage") or string.find(name_lower, "film") then
        return "vintage"
    elseif string.find(name_lower, "bw") or string.find(name_lower, "preto") or string.find(name_lower, "black") then
        return "bw"
    elseif string.find(name_lower, "cinematic") or string.find(name_lower, "cinema") then
        return "cinematic"
    elseif string.find(name_lower, "product") or string.find(name_lower, "produto") then
        return "product"
    elseif string.find(name_lower, "nature") or string.find(name_lower, "natureza") then
        return "nature"
    elseif string.find(name_lower, "urban") or string.find(name_lower, "urbano") then
        return "urban"
    elseif string.find(name_lower, "custom") or string.find(name_lower, "custom") then
        return "custom"
    else
        return "default"
    end
end

-- ============================================================================
-- VISUAL PRESET BROWSER
-- ============================================================================

local function show_visual_preset_browser()
    LrTasks.startAsyncTask(function()
        -- Verificar servidor
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor AI não está disponível. Inicia o servidor primeiro.")
            return
        end

        -- Obter lista de presets
        local presets, err = CommonV2.list_available_presets()

        if err then
            CommonV2.show_error("Erro ao listar presets: " .. (err.message or "desconhecido"))
            return
        end

        if not presets or #presets == 0 then
            CommonV2.show_warning("Nenhum preset disponível.")
            return
        end

        CommonV2.log_info("VisualPresetBrowser", "Listados " .. #presets .. " presets")

        -- Obter preset ativo
        local active_preset, active_err = CommonV2.get_active_preset()
        local active_preset_id = active_preset and active_preset.id or "default"

        -- Organizar presets por categoria
        local presets_by_category = {}
        for _, preset in ipairs(presets) do
            local category = get_preset_category(preset)
            if not presets_by_category[category] then
                presets_by_category[category] = {}
            end
            table.insert(presets_by_category[category], preset)
        end

        -- Obter foto selecionada (para preview)
        local catalog = LrApplication.activeCatalog()
        local photo = catalog:getTargetPhoto()
        local has_photo = (photo ~= nil)

        -- Mostrar dialog
        LrFunctionContext.callWithContext("VisualPresetBrowserDialog", function(context)
            local f = LrView.osFactory()
            local props = LrBinding.makePropertyTable(context)

            -- Criar lista de categorias para filtro
            local category_items = {{ title = "Todas as Categorias", value = "all" }}
            for cat_id, cat_info in pairs(PRESET_CATEGORIES) do
                if presets_by_category[cat_id] then
                    table.insert(category_items, {
                        title = string.format("%s %s (%d)", cat_info.icon, cat_info.name, #presets_by_category[cat_id]),
                        value = cat_id
                    })
                end
            end

            props.selected_category = "all"
            props.selected_preset = active_preset_id
            props.preset_info = ""
            props.preset_details = ""
            props.can_preview = has_photo

            -- Função para obter presets filtrados
            local function get_filtered_presets()
                if props.selected_category == "all" then
                    return presets
                else
                    return presets_by_category[props.selected_category] or {}
                end
            end

            -- Função para atualizar lista de presets no UI
            local function update_preset_list()
                local filtered = get_filtered_presets()
                local preset_items = {}

                for _, preset in ipairs(filtered) do
                    local category = get_preset_category(preset)
                    local cat_info = PRESET_CATEGORIES[category]
                    local display_name = preset.name or preset.id

                    if preset.id == active_preset_id then
                        display_name = "★ " .. display_name .. " (ATIVO)"
                    else
                        display_name = cat_info.icon .. " " .. display_name
                    end

                    table.insert(preset_items, {
                        title = display_name,
                        value = preset.id
                    })
                end

                return preset_items
            end

            -- Função para atualizar informação do preset
            local function update_preset_info()
                local selected_id = props.selected_preset

                for _, preset in ipairs(presets) do
                    if preset.id == selected_id then
                        local category = get_preset_category(preset)
                        local cat_info = PRESET_CATEGORIES[category]

                        local info_text = string.format(
                            "Nome: %s\nCategoria: %s %s\nVersão: %s\nID: %s",
                            preset.name or "N/A",
                            cat_info.icon,
                            cat_info.name,
                            preset.version or "N/A",
                            preset.id
                        )

                        local details_text = preset.description or "Sem descrição disponível."

                        -- Tentar obter detalhes adicionais do servidor
                        local detailed = fetch_preset_details(preset.id)
                        if detailed and detailed.stats then
                            details_text = details_text .. string.format(
                                "\n\nEstatísticas:\n- Aplicações: %d\n- Rating médio: %.1f/5\n- Última atualização: %s",
                                detailed.stats.usage_count or 0,
                                detailed.stats.avg_rating or 0.0,
                                detailed.stats.last_updated or "N/A"
                            )
                        end

                        props.preset_info = info_text
                        props.preset_details = details_text
                        break
                    end
                end
            end

            update_preset_info()

            -- Observers
            props:addObserver("selected_preset", function()
                update_preset_info()
            end)

            local preset_list_items = update_preset_list()

            props:addObserver("selected_category", function()
                -- Quando categoria muda, resetar seleção para o primeiro preset da nova categoria
                local filtered = get_filtered_presets()
                if #filtered > 0 then
                    props.selected_preset = filtered[1].id
                end
            end)

            -- Função para preview do preset
            local function preview_preset()
                if not has_photo then
                    CommonV2.show_warning("Selecione uma foto para visualizar o preset.")
                    return
                end

                LrTasks.startAsyncTask(function()
                    -- Aqui implementaríamos um preview rápido aplicando o preset
                    CommonV2.show_info("Preview do preset (funcionalidade em desenvolvimento)...")
                end)
            end

            -- Função para ativar preset
            local function activate_preset()
                local selected_id = props.selected_preset

                if selected_id == active_preset_id then
                    CommonV2.show_info("Este preset já está ativo.")
                    return
                end

                local success, set_err = CommonV2.set_active_preset(selected_id)

                if success then
                    CommonV2.show_info("Preset ativado com sucesso!")
                    active_preset_id = selected_id
                    update_preset_info()
                else
                    CommonV2.show_error("Erro ao ativar preset: " .. tostring(set_err))
                end
            end

            -- UI Layout
            local contents = f:column {
                spacing = f:control_spacing(),
                fill_horizontal = 1,

                -- Header
                f:row {
                    f:static_text {
                        title = "Visual Preset Browser",
                        font = "<system/bold>",
                        size = "large",
                    },
                    f:spacer { fill_horizontal = 1 },
                    f:static_text {
                        title = string.format("Total: %d presets", #presets),
                        font = "<system>",
                    },
                },

                f:separator { fill_horizontal = 1 },

                -- Filtro por categoria
                f:row {
                    spacing = f:control_spacing(),
                    fill_horizontal = 1,

                    f:static_text {
                        title = "Filtrar por categoria:",
                        width = 140,
                    },

                    f:popup_menu {
                        items = category_items,
                        value = LrView.bind('selected_category'),
                        fill_horizontal = 1,
                    },
                },

                f:separator { fill_horizontal = 1 },

                -- Main content
                f:row {
                    spacing = f:control_spacing(),
                    fill_horizontal = 1,

                    -- Coluna esquerda: Lista de presets
                    f:column {
                        spacing = f:control_spacing(),
                        width = 250,

                        f:static_text {
                            title = "Presets Disponíveis:",
                            font = "<system/bold>",
                        },

                        f:scrolled_view {
                            width = 250,
                            height = 300,

                            f:simple_list {
                                items = preset_list_items,
                                value = LrView.bind('selected_preset'),
                                allows_multiple_selection = false,
                            },
                        },
                    },

                    -- Coluna direita: Detalhes do preset
                    f:column {
                        spacing = f:control_spacing(),
                        fill_horizontal = 1,

                        f:group_box {
                            title = "Informação do Preset",
                            fill_horizontal = 1,

                            f:edit_field {
                                value = LrView.bind('preset_info'),
                                height_in_lines = 5,
                                enabled = false,
                            },
                        },

                        f:group_box {
                            title = "Descrição & Estatísticas",
                            fill_horizontal = 1,

                            f:scrolled_view {
                                height = 150,
                                width = 300,

                                f:edit_field {
                                    value = LrView.bind('preset_details'),
                                    height_in_lines = 8,
                                    enabled = false,
                                },
                            },
                        },

                        -- Botões de ação
                        f:row {
                            spacing = f:control_spacing(),

                            f:push_button {
                                title = "👁️ Preview",
                                action = preview_preset,
                                enabled = LrView.bind('can_preview'),
                                width = 120,
                            },

                            f:push_button {
                                title = "✓ Ativar Preset",
                                action = activate_preset,
                                width = 140,
                            },
                        },
                    },
                },

                f:separator { fill_horizontal = 1 },

                f:static_text {
                    title = "Dica: Selecione um preset da lista para ver detalhes e ativar.",
                    font = "<system/small>",
                    text_color = get_dim_text_color(),
                },
            }

            LrDialogs.presentModalDialog {
                title = "NSP - Visual Preset Browser",
                contents = contents,
                actionVerb = "Fechar",
                preferredWidth = 650,
                preferredHeight = 550,
            }
        end)
    end)
end

-- ============================================================================
-- ENTRY POINT
-- ============================================================================

show_visual_preset_browser()
