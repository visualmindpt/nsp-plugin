-- TestSimple.lua
-- Teste ULTRA simples - apenas mostrar um alerta

local LrDialogs = import 'LrDialogs'

local function main()
    LrDialogs.message("TESTE ULTRA SIMPLES", "Se vês esta mensagem, o plugin ESTÁ A FUNCIONAR!", "info")
end

-- EXECUTAR a função
main()
