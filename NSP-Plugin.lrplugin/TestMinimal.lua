-- TestMinimal.lua
-- TESTE ABSOLUTO MÍNIMO - Zero imports custom

-- Apenas imports do Lightroom SDK (sempre disponíveis)
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'

-- Logger básico
local logger = LrLogger('TestMinimal')
logger:enable("logfile")

-- Função principal
local function main()
    -- Log ANTES de qualquer coisa
    logger:info("========================================")
    logger:info("TestMinimal.lua - INICIADO")
    logger:info("========================================")

    -- Tentar mostrar dialog
    local success, err = pcall(function()
        LrDialogs.message(
            "TESTE MÍNIMO",
            "Este é o teste MAIS SIMPLES possível.\n\n" ..
            "Se vês isto, os imports básicos funcionam!\n\n" ..
            "Data: " .. os.date("%Y-%m-%d %H:%M:%S"),
            "info"
        )
    end)

    -- Log do resultado
    if success then
        logger:info("✅ Dialog mostrado com sucesso")
    else
        logger:error("❌ ERRO ao mostrar dialog: " .. tostring(err))
    end

    logger:info("========================================")
    logger:info("TestMinimal.lua - CONCLUÍDO")
    logger:info("========================================")
end

-- EXECUTAR a função (não apenas retornar)
main()
