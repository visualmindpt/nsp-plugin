-- SyncFeedback.lua
-- Desativado graciosamente devido a incompatibilidade de IDs.

local LrFunctionContext = import 'LrFunctionContext'
local LrDialogs = import 'LrDialogs'

LrFunctionContext.callWithContext("NSP Sync Feedback", function()
    LrDialogs.message(
        "Funcionalidade Indisponível",
        "A funcionalidade 'Sincronizar Feedback' não pode ser usada porque o servidor espera um ID numérico que o plugin não consegue obter do Lightroom de forma fiável. O Lightroom usa IDs de texto (UUIDs).",
        "warning"
    )
end)
