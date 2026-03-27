-- WorkflowPreset.lua
-- Permite aplicar predefinições rápidas (Catálogo gigante vs Modo criativo).

local LrBinding = import 'LrBinding'
local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrFunctionContext = import 'LrFunctionContext'
local LrPathUtils = import 'LrPathUtils'
local LrPrefs = import 'LrPrefs'
local LrView = import 'LrView'

local JSON = require 'json'

local HOME = LrPathUtils.getStandardFilePath("home") or ""
local CONFIG_PATH = HOME ~= "" and (HOME .. "/Library/Application Support/NSP/config/nsp_config.json") or nil

local function load_config()
    if not CONFIG_PATH or not LrFileUtils.exists(CONFIG_PATH) then
        return nil
    end
    local contents = LrFileUtils.readFile(CONFIG_PATH)
    if not contents or contents == "" then
        return nil
    end
    local ok, data = pcall(JSON.decode, contents)
    if not ok or type(data) ~= "table" then
        return nil
    end
    return data
end

local function write_file(path, contents)
    if LrFileUtils.writeFile then
        return LrFileUtils.writeFile(path, contents)
    end
    local handle = assert(io.open(path, "w"))
    handle:write(contents)
    handle:close()
end

local function save_config(mutator)
    if not CONFIG_PATH then
        return
    end
    local cfg = load_config() or {}
    mutator(cfg)
    local dir = LrPathUtils.parent(CONFIG_PATH)
    if dir then
        LrFileUtils.createAllDirectories(dir)
    end
    write_file(CONFIG_PATH, JSON.encode(cfg))
end

local function get_current_workflow()
    local cfg = load_config()
    local model = cfg and cfg.default_model or "nn"
    if type(model) ~= "string" then
        model = "nn"
    end
    return (model:lower() == "nn") and "creative" or "catalog"
end

local function apply_workflow(workflow)
    local prefs = LrPrefs.prefsForPlugin()
    if workflow == "creative" then
        prefs.defaultModel = "nn"
        save_config(function(cfg)
            cfg.default_model = "nn"
        end)
        return "Rede Neural", "Modo criativo aplicado — ideal para sessões premium."
    else
        prefs.defaultModel = "nn"
        save_config(function(cfg)
            cfg.default_model = "nn"
        end)
        return "Rede Neural", "Modo catálogo gigante aplicado — prioriza velocidade."
    end
end

LrFunctionContext.callWithContext("NSP Workflow Presets", function(context)
    local props = LrBinding.makePropertyTable(context)
    props.workflow = get_current_workflow()

    local f = LrView.osFactory()

    local cards = f:row {
        spacing = 16,
        f:group_box {
            title = "Catálogo gigante",
            fill_horizontal = 1,
            f:column {
                spacing = 6,
                f:static_text {
                    title = "Rede Neural em modo otimizado. Indicado para >5K fotos.",
                    width_in_chars = 34,
                },
                f:push_button {
                    title = "Ativar modo rápido",
                    action = function()
                        props.workflow = "catalog"
                        LrDialogs.stopModalWithResult("apply")
                    end,
                },
            },
        },
        f:group_box {
            title = "Modo criativo",
            fill_horizontal = 1,
            f:column {
                spacing = 6,
                f:static_text {
                    title = "Rede Neural para looks artísticos e controle fino.",
                    width_in_chars = 34,
                },
                f:push_button {
                    title = "Ativar modo criativo",
                    action = function()
                        props.workflow = "creative"
                        LrDialogs.stopModalWithResult("apply")
                    end,
                },
            },
        },
    }

    local contents = f:column {
        spacing = 12,
        f:static_text {
            title = "Predefinições prontas para uso: escolhe o workflow e aplicamos o motor correto.",
            width_in_chars = 70,
        },
        cards,
    }

    local result = LrDialogs.presentModalDialog {
        title = "NSP – Workflows rápidos",
        contents = contents,
        actionVerb = "Fechar",
        otherVerb = "Cancelar",
    }

    if result == "apply" then
        local label, message = apply_workflow(props.workflow)
        LrDialogs.message("NSP Plugin", string.format("%s definido como predefinição.\n%s", label, message), "info")
    end
end)
