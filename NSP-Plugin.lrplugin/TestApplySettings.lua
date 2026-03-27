-- TestApplySettings.lua
-- Teste para confirmar que applyDevelopSettings() funciona
-- Aplica valores HARDCODED extremos para diagnóstico

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrLogger = import 'LrLogger'

local logger = LrLogger('NSPPlugin.TestApplySettings')
logger:enable("logfile")

local function main()
    LrTasks.startAsyncTask(function()
        local catalog = LrApplication.activeCatalog()
        local photos = catalog:getTargetPhotos()

        if not photos or #photos == 0 then
            LrDialogs.message("Erro", "Selecione uma foto primeiro!", "critical")
            return
        end

        local photo = photos[1]

        -- Valores HARDCODED extremos para confirmar que funciona
        local testSettings = {
            Exposure2012 = 2.0,           -- +2 EV (muito visível!)
            Contrast2012 = 50,            -- Contraste alto
            Temperature = 8000,           -- Muito quente (laranja)
            Saturation = 50,              -- Saturação alta
            HueAdjustmentRed = 50,        -- Shift vermelho
            SaturationAdjustmentRed = 50, -- Saturação vermelho
        }

        logger:info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger:info("🧪 TESTE DE APLICAÇÃO DE SETTINGS HARDCODED")
        logger:info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger:info("📋 Foto: " .. photo:getFormattedMetadata('fileName'))
        logger:info("")
        logger:info("A aplicar settings HARDCODED:")
        for k, v in pairs(testSettings) do
            logger:info("   " .. k .. " = " .. tostring(v))
        end
        logger:info("")

        logger:info("🚀 A chamar photo:applyDevelopSettings()...")
        catalog:withWriteAccessDo("NSP Test Apply Settings", function()
            photo:applyDevelopSettings(testSettings)
        end)

        logger:info("✅ photo:applyDevelopSettings() executado!")
        logger:info("")

        -- Verificar se foi aplicado
        logger:info("🔍 Verificação pós-aplicação:")
        local applied = photo:getDevelopSettings()

        local all_match = true
        for k, v in pairs(testSettings) do
            local actual = applied[k]
            local match = (tostring(v) == tostring(actual))
            if not match then all_match = false end

            local symbol = match and "✅" or "❌"
            logger:info(string.format("   %s %-30s | Esperado: %-10s | Atual: %-10s",
                symbol, k, tostring(v), tostring(actual)))
        end

        logger:info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        if all_match then
            logger:info("✅ TESTE PASSOU: Todos os settings foram aplicados corretamente!")
            LrDialogs.message("Teste Concluído - SUCESSO",
                "Settings hardcoded aplicados com SUCESSO!\n\n" ..
                "A foto deve estar:\n" ..
                "• Muito clara (+2 EV)\n" ..
                "• Muito laranja (temp 8000K)\n" ..
                "• Muito saturada\n\n" ..
                "Se vê estas mudanças, o Lightroom SDK está a funcionar!",
                "info")
        else
            logger:error("❌ TESTE FALHOU: Alguns settings NÃO foram aplicados!")
            LrDialogs.message("Teste Concluído - FALHA",
                "ATENÇÃO: Alguns settings NÃO foram aplicados!\n\n" ..
                "Isto indica um problema com:\n" ..
                "1. Lightroom SDK (applyDevelopSettings não funciona)\n" ..
                "2. Permissões do plugin\n" ..
                "3. Tipo de ficheiro da foto\n\n" ..
                "Consulte o log para detalhes.",
                "critical")
        end
    end)
end

main()
