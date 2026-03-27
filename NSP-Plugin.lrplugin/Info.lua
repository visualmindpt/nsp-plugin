-- Info.lua
--
-- Main configuration file for the NSP Plugin.

return {
    LrSdkVersion = 14.5, -- Target Lightroom SDK version
    LrPluginName = "NSP Plugin",
    LrToolkitIdentifier = "com.nelsonsilva.nspplugin",
    VERSION = { major=0, minor=6, revision=0, build=1 }, -- V2 com modelo Classificador + Refinador

    -- Expose the action under File > Plug-in Extras
    LrExportMenuItems = {
        -- SERVIDOR
        {
            title = "🚀 Iniciar Servidor AI",
            file = "StartServer.lua",
        },

        -- APLICAÇÃO
        {
            title = "AI Preset V2 (Auto Single/Batch)",
            file = "ApplyAIPresetV2.lua",
            enabledWhen = "photosSelected",
        },
        {
            title = "AI Preset - Preview Antes/Depois",
            file = "PreviewBeforeAfter.lua",
            enabledWhen = "photosSelected",
        },
        {
            title = "AI Preset - Enhanced Preview (Undo/Redo)",
            file = "EnhancedPreview.lua",
            enabledWhen = "photosSelected",
        },

        -- CULLING
        {
            title = "Culling Inteligente - Análise de Qualidade",
            file = "IntelligentCulling.lua",
            enabledWhen = "photosSelected",
        },

        -- AUTO-TOOLS
        {
            title = "Auto-Straighten - Nivelar Horizonte",
            file = "AutoStraighten.lua",
            enabledWhen = "photosSelected",
        },

        -- FEEDBACK
        {
            title = "NSP – Feedback Rápido…",
            file = "SendFeedback.lua",
            enabledWhen = "photosSelected",
        },
        {
            title = "AI Preset - Ver Estatísticas",
            file = "ShowStats.lua",
        },
        {
            title = "NSP – Re-treinar com Feedback",
            file = "TriggerRetrain.lua",
        },

        -- SETTINGS
        {
            title = "NSP – Configurações",
            file = "Settings.lua",
        },
    },

    -- Also expose it under Library > Plug-in Extras
    LrLibraryMenuItems = {
        -- SERVIDOR
        {
            title = "🚀 Iniciar Servidor AI",
            file = "StartServer.lua",
        },

        -- APLICAÇÃO
        {
            title = "AI Preset V2 (Auto Single/Batch)",
            file = "ApplyAIPresetV2.lua",
            enabledWhen = "photosSelected",
        },
        {
            title = "AI Preset - Preview Antes/Depois",
            file = "PreviewBeforeAfter.lua",
            enabledWhen = "photosSelected",
        },
        {
            title = "AI Preset - Enhanced Preview (Undo/Redo)",
            file = "EnhancedPreview.lua",
            enabledWhen = "photosSelected",
        },

        -- CULLING
        {
            title = "Culling Inteligente - Análise de Qualidade",
            file = "IntelligentCulling.lua",
            enabledWhen = "photosSelected",
        },

        -- AUTO-TOOLS
        {
            title = "Auto-Straighten - Nivelar Horizonte",
            file = "AutoStraighten.lua",
            enabledWhen = "photosSelected",
        },

        -- FEEDBACK
        {
            title = "NSP – Feedback Rápido…",
            file = "SendFeedback.lua",
            enabledWhen = "photosSelected",
        },
        {
            title = "AI Preset - Ver Estatísticas",
            file = "ShowStats.lua",
        },
        {
            title = "NSP – Re-treinar com Feedback",
            file = "TriggerRetrain.lua",
        },

        -- SETTINGS
        {
            title = "NSP – Configurações",
            file = "Settings.lua",
        },
    },

    -- Declarar as propriedades que o plugin guarda nas fotos
    publishedProperties = {
        ["com.nelsonsilva.nspplugin"] = {
            nsp_vector_before = {
                title = "NSP Feedback Vector (Before)",
                dataType = "string",
            },
            nsp_vector_ai = {
                title = "NSP Feedback Vector (AI)",
                dataType = "string",
            },
            nsp_last_prediction = {
                title = "NSP Última Predição AI",
                dataType = "string",
            },
        }
    },
}
