-- TestError.lua
-- Teste com captura de erros detalhada

local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'

local logger = LrLogger('TestError')
logger:enable("logfile")

local function main()
    logger:info("========================================")
    logger:info("TESTE DE ERRO - Iniciando...")
    logger:info("========================================")

    local results = {}

    -- 1. Teste básico de dialog
    logger:info("1. Teste básico de dialog...")
    local ok1, err1 = pcall(function()
        -- Este deve sempre funcionar
        return true
    end)
    results[1] = {ok = ok1, error = tostring(err1)}
    logger:info("   Resultado: " .. (ok1 and "OK" or "FALHOU - " .. tostring(err1)))

    -- 2. Teste de require JSON
    logger:info("2. Teste de require JSON...")
    local ok2, result2 = pcall(require, 'json')
    results[2] = {ok = ok2, error = not ok2 and tostring(result2) or nil}
    logger:info("   Resultado: " .. (ok2 and "OK" or "FALHOU - " .. tostring(result2)))

    if ok2 and result2 then
        logger:info("   JSON.encode existe: " .. tostring(result2.encode ~= nil))
        logger:info("   JSON.decode existe: " .. tostring(result2.decode ~= nil))
        logger:info("   Tipo de JSON: " .. type(result2))
    end

    -- 3. Teste de require Common_V2
    logger:info("3. Teste de require Common_V2...")
    local ok3, result3 = pcall(require, 'Common_V2')
    results[3] = {ok = ok3, error = not ok3 and tostring(result3) or nil}
    logger:info("   Resultado: " .. (ok3 and "OK" or "FALHOU - " .. tostring(result3)))

    if ok3 and result3 then
        logger:info("   Common_V2 tipo: " .. type(result3))
        logger:info("   Common_V2.ensure_server existe: " .. tostring(result3.ensure_server ~= nil))
    end

    -- Mostrar resultado final
    local message = "RESULTADOS DOS TESTES:\n\n"
    message = message .. "1. Dialog básico: " .. (results[1].ok and "✅ OK" or "❌ FALHOU") .. "\n"
    message = message .. "2. JSON require: " .. (results[2].ok and "✅ OK" or "❌ FALHOU") .. "\n"
    message = message .. "3. Common_V2 require: " .. (results[3].ok and "✅ OK" or "❌ FALHOU") .. "\n\n"

    -- Adicionar erros
    if not results[2].ok then
        message = message .. "\n❌ Erro JSON:\n" .. (results[2].error or "desconhecido") .. "\n"
    end
    if not results[3].ok then
        message = message .. "\n❌ Erro Common_V2:\n" .. (results[3].error or "desconhecido") .. "\n"
    end

    message = message .. "\n📝 Ver logs detalhados em:\n~/Library/Logs/LrClassicLogs/"

    LrDialogs.message("TESTE DE ERRO - Resultados", message, results[3].ok and "info" or "critical")

    logger:info("========================================")
    logger:info("TESTE DE ERRO - Concluído")
    logger:info("Resultados: " .. (results[3].ok and "SUCESSO" or "FALHA"))
    logger:info("========================================")
end

-- EXECUTAR a função
main()
