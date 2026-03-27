-- Settings.lua
-- Provides a UI for configuring the FastAPI server URL for the AI Preset plugin.

local LrDialogs = import 'LrDialogs'
local LrPrefs = import 'LrPrefs'
local LrHttp = import 'LrHttp'
local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'

-- Default server URL
local DEFAULT_SERVER_URL = "http://127.0.0.1:5678"
local PREF_SERVER_URL = "NSP_AI_SERVER_URL"
local PREF_FEEDBACK_ENABLED = "NSP_FEEDBACK_ENABLED"
local PREF_FEEDBACK_INTERVAL = "NSP_FEEDBACK_INTERVAL"
local DEFAULT_FEEDBACK_INTERVAL = 8

-- Function to get the current server URL from preferences
local function getServerUrl()
    local prefs = LrPrefs.prefsForPlugin()
    return prefs[PREF_SERVER_URL] or DEFAULT_SERVER_URL
end

-- Function to save the server URL to preferences
local function saveServerUrl(url)
    local prefs = LrPrefs.prefsForPlugin()
    prefs[PREF_SERVER_URL] = url
end

local function getFeedbackSettings()
    local prefs = LrPrefs.prefsForPlugin()
    local enabled = prefs[PREF_FEEDBACK_ENABLED]
    if enabled == nil then
        enabled = true
    end
    local interval = prefs[PREF_FEEDBACK_INTERVAL] or DEFAULT_FEEDBACK_INTERVAL
    return enabled, interval
end

local function saveFeedbackSettings(enabled, interval)
    local prefs = LrPrefs.prefsForPlugin()
    prefs[PREF_FEEDBACK_ENABLED] = enabled and true or false
    prefs[PREF_FEEDBACK_INTERVAL] = tonumber(interval) or DEFAULT_FEEDBACK_INTERVAL
end

-- Function to test connection to the server
local function testConnection(serverUrl)
    LrTasks.startAsyncTask(function()
        -- Carregar módulo JSON
        local json_ok, JSON = pcall(require, 'json')
        if not json_ok or not JSON then
            LrDialogs.showAlert("Erro", "Módulo JSON não foi carregado. Verifique json.lua no diretório do plugin.")
            return
        end

        -- Usar LrHttp.get() em vez de post() para /health endpoint
        local responseBody, responseHeaders = LrHttp.get(serverUrl .. "/health", {
            { field = "Content-Type", value = "application/json" }
        })

        if responseHeaders and responseHeaders.status == 200 and responseBody then
            -- Decodificar resposta JSON corretamente
            local decode_ok, status = pcall(function() return JSON:decode(responseBody) end)
            if decode_ok and status and status.status == "ok" then
                LrDialogs.showAlert("Sucesso", "Conexão com o servidor AI estabelecida com sucesso!\n\nResposta: " .. responseBody)
            else
                LrDialogs.showAlert("Erro", "Conexão com o servidor AI falhou. Resposta: " .. tostring(responseBody))
            end
        else
            local status_code = responseHeaders and responseHeaders.status or "sem resposta"
            LrDialogs.showAlert("Erro", "Não foi possível conectar ao servidor AI.\n\nStatus HTTP: " .. status_code .. "\n\nVerifique:\n1. O servidor está a correr? (./start_server.sh)\n2. Porta 5678 está livre?\n3. Firewall está a bloquear?")
        end
    end)
end

-- Main function to display the settings dialog
local function showSettingsDialog()
    return LrFunctionContext.callWithContext("settings", function(context)
        local LrView = import 'LrView'
        local f = LrView.osFactory()
        local LrBinding = import 'LrBinding'

        local props = LrBinding.makePropertyTable(context)
        local feedbackEnabled, feedbackInterval = getFeedbackSettings()
        props.serverUrl = getServerUrl()
        props.feedbackEnabled = feedbackEnabled
        props.feedbackInterval = feedbackInterval

        local contents = f:column {
            spacing = f:control_spacing(),
            fill_horizontal = 1,

            f:static_text {
                title = "URL do Servidor FastAPI:",
                font = "<system/bold>",
            },

            f:edit_field {
                value = LrView.bind('serverUrl'),
                width_in_chars = 40,
                immediate = true,
            },

            f:push_button {
                title = "Testar Conexão",
                action = function()
                    saveServerUrl(props.serverUrl)
                    testConnection(props.serverUrl)
                end,
            },

            f:spacer { height = 10 },

            f:static_text {
                title = "Porta padrão: 5678",
                size = 'small',
            },

            f:spacer { height = 15 },

            f:static_text {
                title = "Feedback automático",
                font = "<system/bold>",
            },

            f:checkbox {
                title = "Ativar pedidos automáticos de feedback após aplicar presets",
                value = LrView.bind('feedbackEnabled'),
            },

            f:row {
                spacing = f:control_spacing(),
                f:static_text {
                    title = "Solicitar feedback a cada",
                    enabled = LrView.bind('feedbackEnabled'),
                },
                f:popup_menu {
                    items = {
                        { title = "3 aplicações", value = 3 },
                        { title = "5 aplicações", value = 5 },
                        { title = "8 aplicações", value = 8 },
                        { title = "10 aplicações", value = 10 },
                        { title = "15 aplicações", value = 15 },
                    },
                    value = LrView.bind('feedbackInterval'),
                    enabled = LrView.bind('feedbackEnabled'),
                },
                f:static_text {
                    title = "aplicações",
                    enabled = LrView.bind('feedbackEnabled'),
                },
            },

            f:static_text {
                title = "Dica: podes ajustar esta frequência quando quiseres; o plugin força feedback se detetar baixa confiança.",
                size = 'small',
            },
        }

        local result = LrDialogs.presentModalDialog {
            title = "Configurações do AI Preset",
            contents = contents,
            actionVerb = "OK",
        }

        if result == "ok" then
            saveServerUrl(props.serverUrl)
            saveFeedbackSettings(props.feedbackEnabled, props.feedbackInterval)
        end
    end)
end

-- EXECUTAR a função
showSettingsDialog()
