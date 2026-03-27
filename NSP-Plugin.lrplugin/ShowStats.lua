-- ShowStats.lua
-- Displays feedback statistics retrieved from the FastAPI server.

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrHttp = import 'LrHttp'
local LrPrefs = import 'LrPrefs'
local LrLogger = import 'LrLogger'

local JSON = require 'json' -- Assuming json.lua is available in the plugin folder

-- Configurar logger
local logger = LrLogger('NSPPlugin.ShowStats')
logger:enable("logfile")

-- Default server URL (should be configured via Settings.lua)
local DEFAULT_SERVER_URL = "http://127.0.0.1:5678"
local PREF_SERVER_URL = "NSP_AI_SERVER_URL"

-- Function to get the current server URL from preferences
local function getServerUrl()
    local prefs = LrPrefs.prefsForPlugin()
    return prefs[PREF_SERVER_URL] or DEFAULT_SERVER_URL
end

local function showFeedbackStats()
    LrTasks.startAsyncTask(function()
        local serverUrl = getServerUrl()
        if not serverUrl or serverUrl == "" then
            LrDialogs.message("Erro de Configuração", "O URL do servidor AI não está configurado. Por favor, vá a 'AI Preset - Configurações' para definir o URL.", "critical")
            return
        end

        -- Criar function context para modal progress dialog
        local LrFunctionContext = import 'LrFunctionContext'
        LrFunctionContext.callWithContext("stats", function(context)
            local progressScope = LrDialogs.showModalProgressDialog({
                title = "Estatísticas do AI Preset",
                caption = "A obter estatísticas do servidor AI...",
                functionContext = context,
            })

            local statsUrl = serverUrl .. "/stats"
            logger:info("A fazer pedido GET para: " .. statsUrl)
            local responseBody, responseHeaders = LrHttp.get(statsUrl)

            -- Progress dialog será fechado automaticamente quando sair do function context

            if responseHeaders and responseHeaders.status == 200 and responseBody then
                logger:info("Response recebida com sucesso. Status: 200")
                logger:info("Response body: " .. tostring(responseBody))

                local decode_ok, decodedResponse = pcall(function() return JSON.decode(responseBody) end)
                if not decode_ok then
                    logger:warn("Primeira tentativa de decode (JSON.decode) falhou: " .. tostring(decodedResponse))
                    decode_ok, decodedResponse = pcall(function() return JSON:decode(responseBody) end)
                end

                if decode_ok and decodedResponse then
                    local statsText = "Estatísticas do Feedback AI:\n\n"
                    statsText = statsText .. "Total de Predições: " .. (decodedResponse.total_predictions or "N/A") .. "\n"
                    statsText = statsText .. "Predições com Feedback: " .. (decodedResponse.predictions_with_feedback or "N/A") .. "\n"
                    statsText = statsText .. "Taxa de Feedback: " .. string.format("%.1f%%", decodedResponse.feedback_rate or 0) .. "\n"
                    statsText = statsText .. "Rating Médio: " .. string.format("%.2f", decodedResponse.average_rating or 0) .. "\n\n"

                    if decodedResponse.preset_distribution then
                        statsText = statsText .. "Distribuição de Presets:\n"
                        for presetId, count in pairs(decodedResponse.preset_distribution) do
                            statsText = statsText .. "  Preset " .. (presetId + 1) .. ": " .. count .. " vezes\n"
                        end
                    end

                    LrDialogs.message("Estatísticas do AI Preset", statsText, "info")
                else
                    local error_msg = "Não foi possível decodificar a resposta do servidor AI.\n\nErro: " .. tostring(decodedResponse) .. "\n\nResponse body: " .. tostring(responseBody)
                    LrDialogs.message("Erro na Resposta", error_msg, "critical")
                    logger:error("Stats Decode Error: " .. tostring(decodedResponse))
                    logger:error("Response body era: " .. tostring(responseBody))
                end
            else
                local status_code = responseHeaders and responseHeaders.status or "sem resposta"
                local error_msg = "Não foi possível conectar ao servidor AI para obter estatísticas.\n\nStatus HTTP: " .. status_code .. "\n\nVerifique:\n1. O servidor está a correr?\n2. Porta 5678 está acessível?"
                LrDialogs.message("Erro de Conexão", error_msg, "critical")
                logger:error("Stats Connection Error - Status: " .. status_code)
            end
        end)
    end)
end

-- EXECUTAR a função
showFeedbackStats()
