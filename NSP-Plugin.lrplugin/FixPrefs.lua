-- FixPrefs.lua
--
-- Limpa a preferência 'server_url' para forçar o plugin a usar o valor por defeito.

local LrFunctionContext = import 'LrFunctionContext'
local LrPrefs = import 'LrPrefs'
local LrDialogs = import 'LrDialogs'

LrFunctionContext.callWithContext("Reset Server URL", function(context)
    local prefs = LrPrefs.prefsForPlugin()
    
    if prefs.server_url then
        prefs.server_url = nil
        LrDialogs.message("Preferências Corrigidas", "O URL do servidor foi reiniciado para o valor por defeito (http://127.0.0.1:5678). Por favor, reinicie o Lightroom.", "info")
    else
        LrDialogs.message("Preferências Corrigidas", "Nenhum URL personalizado encontrado. Nenhuma ação foi necessária.", "info")
    end
end)
