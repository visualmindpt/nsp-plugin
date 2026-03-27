-- TriggerRetrain.lua
-- Dispara re-treino no servidor usando feedback recolhido

local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'
local LrView = import 'LrView'
local LrBinding = import 'LrBinding'
local LrLogger = import 'LrLogger'

local CommonV2 = require 'Common_V2'

local logger = LrLogger('NSPPlugin.TriggerRetrain')
logger:enable("logfile")

local function main()
    LrTasks.startAsyncTask(function()
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor NSP offline. Inicie o NSP Control Center antes de re-treinar.")
            return
        end

        LrFunctionContext.callWithContext("TriggerRetrain", function(context)
            -- Parâmetros hardcoded e explicação breve
            local payload = {
                min_samples = 50,
                epochs = 20,
                batch_size = 16,
            }

            LrDialogs.message(
                "NSP – Re-treinar com Feedback",
                string.format(
                    "Se houver pelo menos %d samples, vamos re-treinar com os feedbacks recolhidos.\n\n"
                    .. "Se não houver dados suficientes, nada será feito.",
                    payload.min_samples
                ),
                "info"
            )

            CommonV2.log_info("Retrain", string.format(
                "A iniciar re-treino (min_samples=%d, epochs=%d, batch=%d)",
                payload.min_samples, payload.epochs, payload.batch_size
            ))

            local response, err = CommonV2.post_json("/retrain", payload)

            if err then
                local detail = err.body or err.message or "desconhecido"
                CommonV2.show_error("Erro ao iniciar re-treino: " .. tostring(detail))
                return
            end

            local msg = response and response.message or "Re-treino iniciado."
            CommonV2.show_info(msg)
        end)
    end)
end

main()
