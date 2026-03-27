--[[ 
    test_common.lua - Testes unitários para o módulo Common.lua

    COMO EXECUTAR:
    1. Instale um interpretador Lua 5.3+ (ex: `brew install lua`).
    2. Navegue para a pasta `NSP-Plugin.lrplugin`.
    3. Execute: `lua ../tests/test_common.lua`

    Este script simula o ambiente do Lightroom para testar a lógica do Common.lua
    de forma isolada.
--]]

print("=============================================")
print("A INICIAR TESTES PARA Common.lua")
print("=============================================")

-- ============================================================================
-- MOCKS (Simulação do Ambiente Lightroom)
-- ============================================================================
-- Simula o sistema de ficheiros em memória
local mock_fs = {}
local mock_prefs = {}

-- Mock para LrLogger
LrLogger = function(name)
    return {
        enable = function() end,
        info = function(...) print("[INFO] ", ...) end,
        warn = function(...) print("[WARN] ", ...) end,
        error = function(...) print("[ERROR]", ...) end,
        trace = function(...) print("[TRACE]", ...) end,
    }
end

-- Mock para LrPathUtils
LrPathUtils = {
    getStandardFilePath = function(type)
        if type == 'app_data' then return "/mock/app_data" end
        return "/mock/unknown"
    end,
    getPluginDir = function()
        return "/mock/plugin_dir"
    end,
    child = function(...)
        local parts = {...}
        return table.concat(parts, "/")
    end,
    parent = function(path)
        return path:match("(.+)/")
    end
}

-- Mock para LrFileUtils
LrFileUtils = {
    exists = function(path) return mock_fs[path] ~= nil end,
    readFile = function(path)
        if mock_fs[path] then return mock_fs[path].content end
        return nil
    end,
    writeFile = function(path, content)
        mock_fs[path] = { content = content }
        return true
    end,
    createDirectory = function(path)
        mock_fs[path] = { is_dir = true }
    end
}

-- Mock para LrHttp
LrHttp = {
    _mock_responses = {},
    get = function(url, _, timeout)
        if LrHttp._mock_responses[url] then
            return LrHttp._mock_responses[url].body, LrHttp._mock_responses[url].headers
        end
        return nil, { status = 404 }
    end,
    post = function(url, body_str, headers, method, timeout)
        if LrHttp._mock_responses[url] then
            return LrHttp._mock_responses[url].body, LrHttp._mock_responses[url].headers
        end
        return nil, { status = 404 }
    end,
    _add_mock_response = function(url, status, body)
        LrHttp._mock_responses[url] = {
            headers = { status = status },
            body = body
        }
    end
}

-- Mock para LrTasks
LrTasks = {
    _last_executed = nil,
    execute = function(cmd)
        print("[TASK] Executado:", cmd)
        LrTasks._last_executed = cmd
    end,
    sleep = function() end
}

-- Mock para LrDialogs
LrDialogs = {
    message = function(title, msg) print("[UI] " .. title .. ": " .. msg) end
}

-- Mock para `import` e `require`
function import(module_name)
    if module_name == 'LrPrefs' then
        return { prefsForPlugin = function() return mock_prefs end }
    end
    -- Retorna o próprio mock se o nome corresponder
    return _G[module_name]
end
-- O `json` é uma dependência real, vamos usar uma implementação simples para o teste
JSON = {
    encode = function(tbl) 
        -- Simples o suficiente para os testes
        local parts = {}
        for k, v in pairs(tbl) do
            table.insert(parts, string.format('"%s":"%s"', k, v))
        end
        return "{" .. table.concat(parts, ",") .. "}"
    end,
    decode = function(str)
        local tbl = {}
        for k, v in str:gmatch('"([^"]+)":"([^"]+)"') do
            tbl[k] = v
        end
        return tbl
    end
}

-- ============================================================================
-- Test Runner
-- ============================================================================
local tests = {}
local tests_passed = 0
local tests_failed = 0

function tests:run()
    for name, test_func in pairs(self) do
        if type(test_func) == 'function' and name ~= 'run' then
            -- Resetar mocks para um ambiente limpo
            mock_fs = {}
            mock_prefs = {}
            LrHttp._mock_responses = {}
            LrTasks._last_executed = nil

            -- GARANTIR ISOLAMENTO: Forçar a recarga do módulo Common antes de cada teste
            -- para limpar qualquer estado interno (como configurações carregadas).
            package.loaded['Common'] = nil
            Common = require 'Common'

            print("\n--- A executar teste: " .. name .. " ---")
            local success, err = pcall(test_func)
            if success then
                print("--- PASSOU ---")
                tests_passed = tests_passed + 1
            else
                print("--- FALHOU ---")
                print(err)
                tests_failed = tests_failed + 1
            end
        end
    end
end

-- Função de asserção simples
function assert_equal(a, b, message)
    if a ~= b then
        error(string.format("%s: '%s' ~= '%s'", message, tostring(a), tostring(b)))
    end
end

-- ============================================================================
-- Casos de Teste
-- ============================================================================

-- Carregar o módulo Common DEPOIS de definir os mocks
local Common = require 'Common'

function tests:test_config_loads_defaults_when_no_file_exists()
    -- O init() já correu ao carregar o módulo
    local url = Common.get_config('SERVER_URL')
    assert_equal(url, "http://127.0.0.1:5678", "Deveria usar o URL por defeito")
end

function tests:test_config_overrides_defaults_from_file()
    -- Simular um ficheiro de configuração
    local config_path = Common.get_config('CONFIG_PATH')
    mock_fs[config_path] = { content = '{"SERVER_URL":"http://custom.url:1234"}' }

    -- Recarregar o módulo para forçar a releitura da config
    package.loaded['Common'] = nil
    Common = require 'Common'

    local url = Common.get_config('SERVER_URL')
    assert_equal(url, "http://custom.url:1234", "Deveria usar o URL do ficheiro de config")
end

function tests:test_security_blocks_script_outside_plugin_dir()
    mock_prefs.start_server_script = "/usr/local/bin/malicious.sh"
    local result = Common.try_auto_start_server()
    assert_equal(result, false, "Deveria ter bloqueado o script")
    assert_equal(LrTasks._last_executed, nil, "Não deveria ter executado nenhum comando")
end

function tests:test_security_allows_script_inside_plugin_dir()
    local safe_script = LrPathUtils.child(LrPathUtils.getPluginDir(), "start.sh")
    mock_prefs.start_server_script = safe_script
    mock_fs[safe_script] = { content = "#!/bin/bash\necho 'hello'" } -- Simular que o ficheiro existe

    -- Simular que o servidor fica online depois do script correr
    LrHttp._add_mock_response("http://127.0.0.1:5678/health", 200, "OK")

    local result = Common.try_auto_start_server()

    assert_equal(result, true, "Deveria ter arrancado o servidor com sucesso")
    assert_equal(LrTasks._last_executed, 'bash "' .. safe_script .. '"', "Deveria ter executado o comando seguro")
end

function tests:test_post_json_handles_server_error()
    LrHttp._add_mock_response("http://127.0.0.1:5678/error-endpoint", 500, "Internal Server Error")
    local response, err = Common.post_json("/error-endpoint", {})

    assert_equal(response, nil, "Resposta deveria ser nula em caso de erro")
    assert_equal(err.status, 500, "Deveria reportar o status 500")
    assert_equal(err.body, "Internal Server Error", "Deveria reportar o corpo do erro")
end

function tests:test_post_json_handles_invalid_json_response()
    LrHttp._add_mock_response("http://127.0.0.1:5678/invalid-json", 200, "isto-nao-e-json")
    local response, err = Common.post_json("/invalid-json", {})

    assert_equal(response, nil, "Resposta deveria ser nula em caso de JSON inválido")
    assert_equal(err.message, "Resposta inválida ou malformada do servidor.", "Deveria reportar erro de parse de JSON")
end

-- ============================================================================
-- Execução
-- ============================================================================
tests:run()

print("=============================================")
print(string.format("Resultados: %d passaram, %d falharam.", tests_passed, tests_failed))
print("=============================================")

if tests_failed > 0 then
    os.exit(1)
end
