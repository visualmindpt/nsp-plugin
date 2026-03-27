-- MatchReferenceStyle.lua
-- Aplica o look de uma foto de referência às fotos seleccionadas.
--
-- Fluxo:
--   1. A primeira foto seleccionada é a REFERÊNCIA (já editada pelo utilizador)
--   2. Todas as outras são as fotos ALVO (a editar)
--   3. O plugin exporta um JPEG temporário da referência
--   4. POST /predict/reference para cada foto alvo
--   5. Aplica os parâmetros devolvidos via applyDevelopSettings()

local LrApplication    = import 'LrApplication'
local LrDialogs        = import 'LrDialogs'
local LrExportSession  = import 'LrExportSession'
local LrFileUtils      = import 'LrFileUtils'
local LrLogger         = import 'LrLogger'
local LrPathUtils      = import 'LrPathUtils'
local LrProgressScope  = import 'LrProgressScope'
local LrTasks          = import 'LrTasks'

local CommonV2 = require 'Common_V2'

local logger = LrLogger('NSPPlugin.MatchReferenceStyle')
logger:enable("logfile")

-- ============================================================================
-- Exportar JPEG temporário de uma foto (com edições aplicadas)
-- ============================================================================

local function export_jpeg_preview(photo, max_size)
    max_size = max_size or 800

    local tmp_dir = LrPathUtils.getStandardFilePath("temp")
    local filename = photo:getFormattedMetadata('fileName') or "ref"
    filename = filename:gsub("[^%w%-_]", "_")
    local tmp_path = LrPathUtils.child(tmp_dir, "nsp_ref_" .. filename .. "_" .. tostring(os.time()) .. ".jpg")

    -- Usar exportSession para renderizar com edições
    local export_settings = {
        LR_export_destinationType = "specificFolder",
        LR_export_destinationPathPrefix = tmp_dir,
        LR_export_useSubfolder = false,
        LR_format = "JPEG",
        LR_jpeg_quality = 0.85,
        LR_size_doConstrain = true,
        LR_size_maxHeight = max_size,
        LR_size_maxWidth = max_size,
        LR_size_units = "pixels",
        LR_size_resizeType = "longEdge",
        LR_outputSharpeningOn = false,
        LR_export_colorSpace = "sRGB",
        LR_minimizeEmbeddedMetadata = true,
        LR_export_useSubfolder = false,
        LR_tokens_useRootFolder = false,
    }

    local session = LrExportSession({
        photosToExport = { photo },
        exportSettings = export_settings,
    })

    local result_path = nil
    local ok = pcall(function()
        for _, rendition in session:renditions() do
            local success, path_or_msg = rendition:waitForRender()
            if success then
                result_path = path_or_msg
            else
                logger:error("Falha ao exportar preview: " .. tostring(path_or_msg))
            end
        end
    end)

    if not ok or not result_path then
        logger:warn("Export falhou — a tentar via path directo")
        result_path = photo:getRawMetadata("path")
    end

    return result_path
end

-- ============================================================================
-- Predizer e aplicar parâmetros de referência para uma foto
-- ============================================================================

local function apply_reference_style(photo, reference_jpeg_path, progress_scope)
    local filename = photo:getFormattedMetadata('fileName') or "foto"

    if progress_scope then
        progress_scope:setCaption("🔍 " .. filename .. " - Analisando...")
    end

    local photo_path = photo:getRawMetadata("path")
    if not photo_path or photo_path == "" then
        return false, "Caminho de foto inválido"
    end

    -- Construir payload
    local payload = {
        image_path    = photo_path,
        reference_path = reference_jpeg_path,
    }

    if progress_scope then
        progress_scope:setCaption("🤖 " .. filename .. " - Predição AI...")
    end

    -- Chamar endpoint /predict/reference
    local server_url = CommonV2.get_server_url() or "http://127.0.0.1:5678"
    local url = server_url .. "/predict/reference"

    local JSON = require 'json'
    local body = JSON.encode(payload)
    local response_body, response_headers = LrHttp.post(
        url, body, { { field = "Content-Type", value = "application/json" } }
    )

    if not response_body then
        return false, "Sem resposta do servidor (" .. url .. ")"
    end

    local ok, result = pcall(JSON.decode, response_body)
    if not ok or not result then
        return false, "Resposta inválida: " .. tostring(response_body):sub(1, 200)
    end

    if result.detail then
        return false, "Erro do servidor: " .. tostring(result.detail)
    end

    local params = result.predicted_params
    if not params or not next(params) then
        return false, "Sem parâmetros na resposta"
    end

    if progress_scope then
        progress_scope:setCaption("✨ " .. filename .. " - Aplicando look...")
    end

    -- Converter para developSettings
    local develop_settings = CommonV2.build_develop_settings(params)
    if not develop_settings or not next(develop_settings) then
        return false, "Sem ajustes válidos para aplicar"
    end

    -- Aplicar ao catálogo
    local catalog = LrApplication.activeCatalog()
    catalog:withWriteAccessDo("NSP - Match Reference Style", function()
        photo:applyDevelopSettings(develop_settings)
    end, { timeout = 10, abortOnConflict = true })

    logger:info("Reference style aplicado a: " .. filename)
    return true, nil
end

-- ============================================================================
-- ENTRY POINT
-- ============================================================================

local function main()
    LrTasks.startAsyncTask(function()
        local catalog = LrApplication.activeCatalog()
        local photos = catalog:getTargetPhotos()

        -- Validar selecção mínima
        if not photos or #photos < 2 then
            LrDialogs.message(
                "NSP — Match Reference Style",
                "Selecione pelo menos 2 fotos:\n" ..
                "  • 1ª foto: referência (já editada)\n" ..
                "  • Restantes: fotos a editar",
                "warning"
            )
            return
        end

        -- Verificar servidor
        if not CommonV2.ensure_server() then
            CommonV2.show_error("Servidor NSP offline. Por favor inicie o NSP Control Center.")
            return
        end

        local reference_photo = photos[1]
        local target_photos   = {}
        for i = 2, #photos do
            target_photos[#target_photos + 1] = photos[i]
        end

        local ref_name = reference_photo:getFormattedMetadata('fileName') or "referência"

        -- Confirmar com o utilizador
        local confirm = LrDialogs.confirm(
            "NSP — Match Reference Style",
            "Referência: " .. ref_name .. "\n\n" ..
            "Fotos a editar: " .. #target_photos .. "\n\n" ..
            "O look da referência será aplicado a todas as fotos seleccionadas.\n" ..
            "Esta operação pode ser anulada com Ctrl+Z / Cmd+Z.",
            "Aplicar", "Cancelar"
        )
        if confirm ~= "ok" then return end

        local progress = LrProgressScope({
            title   = "NSP — Match Reference Style",
            caption = "A exportar referência...",
        })

        -- Exportar JPEG da referência
        local ref_jpeg_path = export_jpeg_preview(reference_photo, 800)
        if not ref_jpeg_path then
            progress:done()
            CommonV2.show_error("Falha ao exportar JPEG da foto de referência.")
            return
        end
        logger:info("Referência exportada: " .. tostring(ref_jpeg_path))

        -- Processar cada foto alvo
        local success_count, fail_count = 0, 0
        local errors = {}

        for i, photo in ipairs(target_photos) do
            if progress:isCanceled() then break end

            progress:setPortionComplete(i - 1, #target_photos)
            local ok, err = apply_reference_style(photo, ref_jpeg_path, progress)

            if ok then
                success_count = success_count + 1
            else
                fail_count = fail_count + 1
                errors[#errors + 1] = (photo:getFormattedMetadata('fileName') or "?") .. ": " .. (err or "erro")
                logger:error("Falha em " .. tostring(photo:getFormattedMetadata('fileName')) .. ": " .. tostring(err))
            end
        end

        -- Limpar JPEG temporário (apenas se foi criado numa pasta temp)
        local tmp_marker = "nsp_ref_"
        if ref_jpeg_path and ref_jpeg_path:find(tmp_marker) then
            pcall(LrFileUtils.delete, ref_jpeg_path)
        end

        progress:done()

        -- Relatório final
        local msg = success_count .. " foto(s) processada(s) com o look de «" .. ref_name .. "»."
        if fail_count > 0 then
            msg = msg .. "\n\n" .. fail_count .. " erro(s):\n" .. table.concat(errors, "\n"):sub(1, 400)
            LrDialogs.message("NSP — Match Reference Style", msg, "warning")
        else
            pcall(function()
                LrDialogs.showBezel("✅ " .. msg, 3)
            end)
        end
    end)
end

local LrHttp = import 'LrHttp'
main()
