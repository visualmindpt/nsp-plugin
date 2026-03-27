-- TestConnection.lua
-- Script de teste minimalista para verificar conectividade

local LrDialogs = import 'LrDialogs'
local LrHttp = import 'LrHttp'
local LrApplication = import 'LrApplication'
local LrLogger = import 'LrLogger'
local LrTasks = import 'LrTasks'

local logger = LrLogger('NSPPlugin.TestConnection')
logger:enable("logfile")

local function main()
    logger:info("========================================")
    logger:info("TESTE DE CONEXÃO - INICIADO")
    logger:info("========================================")

    -- Teste 1: Verificar se consegue mostrar dialog
    logger:info("Teste 1: Mostrar dialog")
    LrDialogs.message("NSP Test", "Plugin carregado com sucesso!\n\nVou testar a conexão ao servidor...", "info")

    -- Teste 2: Verificar se tem fotos selecionadas
    logger:info("Teste 2: Verificar fotos selecionadas")
    local catalog = LrApplication.activeCatalog()
    local photos = catalog:getTargetPhotos()

    if not photos or #photos == 0 then
        logger:warn("Nenhuma foto selecionada")
        LrDialogs.message("NSP Test", "⚠️ Nenhuma foto selecionada.\n\nPor favor, selecione pelo menos 1 foto e tente novamente.", "warning")
        return
    end

    logger:info("Fotos selecionadas: " .. #photos)

    -- Teste 3: Testar conexão ao servidor (dentro de task assíncrona)
    logger:info("Teste 3: Testar conexão HTTP ao servidor")

    LrTasks.startAsyncTask(function()
        local server_url = "http://127.0.0.1:5678"  -- Porta correta
        local endpoint = server_url .. "/health"

        logger:info("A conectar a: " .. endpoint)

        local response_body, response_headers = LrHttp.get(endpoint, {
            { field = "Content-Type", value = "application/json" }
        })

        logger:info("Response body: " .. tostring(response_body))
        logger:info("Response headers: " .. tostring(response_headers and response_headers.status or "nil"))

        if response_headers and response_headers.status == 200 then
            logger:info("✅ Servidor está ONLINE")
            LrDialogs.message(
                "NSP Test - Sucesso",
                "✅ TODOS OS TESTES PASSARAM!\n\n" ..
                "• Plugin carregado: OK\n" ..
                "• Fotos selecionadas: " .. #photos .. "\n" ..
                "• Servidor online: OK\n" ..
                "• Resposta: " .. (response_body or "vazio"),
                "info"
            )
        else
            logger:error("❌ Servidor NÃO está acessível")
            local status = response_headers and response_headers.status or "sem resposta"
            LrDialogs.message(
                "NSP Test - Erro",
                "❌ SERVIDOR NÃO ACESSÍVEL\n\n" ..
                "Status HTTP: " .. status .. "\n" ..
                "URL testado: " .. endpoint .. "\n\n" ..
                "Por favor, verifique:\n" ..
                "1. Servidor está a correr? (./start_server.sh)\n" ..
                "2. Porta 5678 está livre?\n" ..
                "3. Firewall está a bloquear?",
                "critical"
            )
        end

        logger:info("========================================")
        logger:info("TESTE DE CONEXÃO - CONCLUÍDO")
        logger:info("========================================")
    end)
end

-- EXECUTAR a função
main()
