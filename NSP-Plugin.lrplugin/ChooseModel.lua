-- ChooseModel.lua
-- Redireciona o utilizador para o Control Center para configuração.

local LrDialogs = import 'LrDialogs'
local LrFunctionContext = import 'LrFunctionContext'

LrFunctionContext.callWithContext("NSP Escolher Modelo", function()
    LrDialogs.message(
        "Configuração do Modelo",
        "O modelo de IA utilizado é a Rede Neural (ONNX). Use 'NSP Control Center' para configurações avançadas.",
        "info"
    )
end)
