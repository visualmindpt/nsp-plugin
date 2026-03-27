-- StartServer.lua
-- Inicia automaticamente o servidor FastAPI AI em background

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrHttp = import 'LrHttp'
local LrFunctionContext = import 'LrFunctionContext'
local LrPrefs = import 'LrPrefs'
local LrLogger = import 'LrLogger'

-- Configurar logger
local logger = LrLogger('NSPPlugin.StartServer')
logger:enable("logfile")

-- Configuração
local DEFAULT_SERVER_URL = "http://127.0.0.1:5678"
local PREF_SERVER_URL = "NSP_AI_SERVER_URL"
local SERVER_SCRIPT_PATH = "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/start_server.sh"
local HEALTH_CHECK_TIMEOUT = 30 -- segundos
local POLL_INTERVAL = 1 -- segundo

-- Function to get the current server URL from preferences
local function getServerUrl()
    local prefs = LrPrefs.prefsForPlugin()
    return prefs[PREF_SERVER_URL] or DEFAULT_SERVER_URL
end

-- Verifica se o servidor está online
local function isServerOnline(serverUrl)
    local healthUrl = serverUrl .. "/health"
    local responseBody, responseHeaders = LrHttp.get(healthUrl, nil, nil, "GET", 2000) -- timeout 2s

    if responseHeaders and responseHeaders.status == 200 then
        return true
    end
    return false
end

-- Verifica se o script start_server.sh existe
local function scriptExists()
    local handle = io.open(SERVER_SCRIPT_PATH, "r")
    if handle then
        handle:close()
        return true
    end
    return false
end

-- Executa o script de start do servidor
local function executeStartScript()
    -- Comando para executar o script em background
    -- O script já tem lógica para correr em background, então apenas o executamos
    local command = string.format('bash -c "cd \\"%s\\" && ./start_server.sh > /dev/null 2>&1 &"',
        "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package")

    local success, result = LrTasks.pcall(function()
        LrTasks.execute(command)
    end)

    return success
end

-- Função principal
local function startServerAI()
    LrTasks.startAsyncTask(function()
        local serverUrl = getServerUrl()

        if isServerOnline(serverUrl) then
            LrDialogs.message("Servidor AI Online",
                "O servidor AI já está online e a responder!\n\n" ..
                "URL: " .. serverUrl .. "\n" ..
                "Estado: Operacional", "info")
            logger:info("StartServer: Servidor já está online")
            return
        end

        -- Verificar se o script existe
        if not scriptExists() then
            LrDialogs.message("Erro - Script Não Encontrado",
                "O script de inicialização do servidor não foi encontrado.\n\n" ..
                "Caminho esperado:\n" .. SERVER_SCRIPT_PATH .. "\n\n" ..
                "Por favor, verifique se o ficheiro existe e tem permissões de execução.", "critical")
            logger:error("StartServer ERROR: Script não encontrado em " .. SERVER_SCRIPT_PATH)
            return
        end

        -- Criar progress dialog
        LrFunctionContext.callWithContext("startServer", function(context)
            local progressScope = LrDialogs.showModalProgressDialog({
                title = "A Iniciar Servidor AI",
                caption = "A executar script de inicialização...",
                functionContext = context,
            })

            -- Executar o script
            logger:info("StartServer: A executar script: " .. SERVER_SCRIPT_PATH)
            local scriptSuccess = executeStartScript()

            if not scriptSuccess then
                progressScope:done()
                LrDialogs.message("Erro ao Iniciar Servidor",
                    "Não foi possível executar o script de inicialização.\n\n" ..
                    "Tente iniciar manualmente:\n" ..
                    "Terminal: cd <pasta> && ./start_server.sh", "critical")
                logger:error("StartServer ERROR: Falha ao executar script")
                return
            end

            -- Aguardar que o servidor fique online (polling)
            progressScope:setCaption("Servidor a inicializar... A aguardar resposta...")
            logger:info("StartServer: Script executado. A fazer polling do /health endpoint...")

            local maxAttempts = HEALTH_CHECK_TIMEOUT / POLL_INTERVAL
            local attempt = 0
            local serverReady = false

            while attempt < maxAttempts do
                attempt = attempt + 1
                progressScope:setCaption(string.format("A aguardar servidor... (%d/%d segundos)",
                    attempt * POLL_INTERVAL, HEALTH_CHECK_TIMEOUT))

                -- Verificar se servidor está online
                if isServerOnline(serverUrl) then
                    serverReady = true
                    logger:info("StartServer: Servidor online após " .. (attempt * POLL_INTERVAL) .. " segundos")
                    break
                end

                -- Aguardar antes do próximo poll
                LrTasks.sleep(POLL_INTERVAL)
            end

            progressScope:done()

            -- Mostrar resultado
            if serverReady then
                LrDialogs.message("Servidor AI Iniciado com Sucesso!",
                    "O servidor AI está online e pronto a usar!\n\n" ..
                    "URL: " .. serverUrl .. "\n" ..
                    "Tempo de arranque: ~" .. (attempt * POLL_INTERVAL) .. " segundos\n\n" ..
                    "✅ Pode agora usar as funções de AI Preset", "info")
                logger:info("StartServer SUCCESS: Servidor iniciado e operacional")
            else
                LrDialogs.message("Timeout ao Iniciar Servidor",
                    "O script foi executado mas o servidor não respondeu em " .. HEALTH_CHECK_TIMEOUT .. " segundos.\n\n" ..
                    "Possíveis causas:\n" ..
                    "• Servidor ainda está a inicializar (aguarde mais)\n" ..
                    "• Erro no servidor (verifique logs)\n" ..
                    "• Porta 5678 em uso\n\n" ..
                    "Verifique:\n" ..
                    "Terminal: ps aux | grep uvicorn\n" ..
                    "Logs: <pasta>/server_logs/", "warning")
                logger:warn("StartServer WARNING: Timeout - servidor não respondeu em " .. HEALTH_CHECK_TIMEOUT .. "s")
            end
        end)
    end)
end

-- EXECUTAR a função
startServerAI()
