-- SendFeedback.lua
-- Abre o formulário de feedback manual para a foto selecionada.

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'

local CommonV2 = require 'Common_V2'

local function run()
    local catalog = LrApplication.activeCatalog()
    local photo = catalog:getTargetPhoto()

    if not photo then
        CommonV2.show_warning("Seleciona uma foto para enviar feedback.")
        return
    end

    CommonV2.open_feedback_dialog(photo, "manual")
end

LrTasks.startAsyncTask(run)
