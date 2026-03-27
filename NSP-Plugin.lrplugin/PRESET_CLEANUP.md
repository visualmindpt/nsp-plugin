# NSP Plugin - Remoção de Funcionalidades de Presets Tradicionais

**Data:** 2025-11-25
**Versão:** 0.6.0

## 📋 Resumo das Mudanças

Este documento descreve a remoção das funcionalidades de **presets tradicionais** do NSP Plugin, mantendo apenas as funcionalidades de **AI Preset (Modelos AI partilháveis)**.

---

## ❌ Funcionalidades Removidas

As seguintes funcionalidades de presets tradicionais foram **removidas do menu** e os ficheiros foram **movidos para `disabled_presets/`**:

### 1. **Gestor de Presets** (`PresetManager.lua`)
- Interface para gerir presets tradicionais do Lightroom
- Permitia organizar, renomear e categorizar presets
- **Removido** porque o objetivo é usar apenas AI presets

### 2. **Visual Preset Browser** (`VisualPresetBrowser.lua`)
- Browser visual para navegar presets com previews
- Mostrava thumbnails de presets aplicados
- **Removido** porque AI presets não precisam de browser manual

### 3. **Exportar Preset Atual** (`ExportCurrentPreset.lua`)
- Exportava o preset atualmente aplicado numa foto
- Criava ficheiro .lrtemplate
- **Removido** porque exportação agora é feita via modelos AI

---

## ✅ Funcionalidades Mantidas (AI System)

As seguintes funcionalidades **AI-based** foram **mantidas e são o foco do plugin**:

### Core AI
- ✅ **AI Preset V2 (Auto Single/Batch)** - Aplica ajustes AI baseados em modelos treinados
- ✅ **AI Preset - Preview Antes/Depois** - Preview de ajustes AI
- ✅ **AI Preset - Enhanced Preview (Undo/Redo)** - Preview avançado com histórico

### Ferramentas AI
- ✅ **Culling Inteligente** - Análise de qualidade com AI
- ✅ **Auto-Straighten** - Nivelar horizonte automaticamente

### Gestão & Feedback
- ✅ **NSP - Feedback Rápido** - Enviar feedback sobre ajustes AI
- ✅ **AI Preset - Ver Estatísticas** - Estatísticas de uso do AI
- ✅ **NSP - Re-treinar com Feedback** - Retreinar modelos com feedback
- ✅ **NSP - Configurações** - Configurações gerais do plugin
- ✅ **🚀 Iniciar Servidor AI** - Servidor Python para inferência

---

## 🎯 Filosofia do Plugin (Após Mudanças)

### Antes (Presets Tradicionais)
- Aplicava valores fixos de ajustes
- Mesmo preset para todas as fotos
- Não adaptava a cada imagem
- Gestão manual de bibliotecas de presets

### Agora (AI Models Only)
- **Modelos AI analisam cada foto individualmente**
- **Ajustes adaptativos** baseados no conteúdo
- **Modelos partilháveis** (~770KB) entre computadores
- **Treino incremental** - adiciona conhecimento sem perder anterior
- **Cross-platform** - Mac/Windows/Linux

---

## 💾 Ficheiros Movidos

Os seguintes ficheiros foram movidos para `disabled_presets/` mas **NÃO foram apagados**:

```
NSP-Plugin.lrplugin/disabled_presets/
├── PresetManager.lua (5.4 KB)
├── VisualPresetBrowser.lua (16.4 KB)
└── ExportCurrentPreset.lua (11.3 KB)
```

**Total:** ~33 KB de código legacy preservado

---

## 🔄 Como Restaurar (Se Necessário)

Se por alguma razão precisares de restaurar as funcionalidades de presets tradicionais:

### 1. Mover Ficheiros de Volta
```bash
cd "NSP-Plugin.lrplugin"
mv disabled_presets/*.lua .
```

### 2. Adicionar de Volta ao Info.lua

Adiciona estas linhas em `Info.lua` (depois de "AUTO-TOOLS"):

```lua
        -- PRESETS
        {
            title = "Gestor de Presets",
            file = "PresetManager.lua",
        },
        {
            title = "Visual Preset Browser",
            file = "VisualPresetBrowser.lua",
        },
        {
            title = "Exportar Preset Atual",
            file = "ExportCurrentPreset.lua",
            enabledWhen = "photosSelected",
        },
```

Adiciona em **dois lugares**:
- `LrExportMenuItems` (linhas ~50)
- `LrLibraryMenuItems` (linhas ~126)

### 3. Reinicia o Lightroom

---

## 📦 Nova Funcionalidade: Gestão de Modelos AI

Em substituição dos presets tradicionais, foi adicionada uma nova UI para gestão de **modelos AI**:

### Localização
```bash
python3 scripts/ui/train_ui_clean.py
```

### Tab "📦 Gestão de Modelos"

#### 📤 Exportar Modelos
- Verifica modelos atuais e estatísticas
- Cria pacote ZIP (~770KB) com todos os modelos
- Inclui README e metadados
- Download automático

#### 📥 Importar Modelos
- Upload de ZIP de modelos
- Inspeção automática (mostra estatísticas)
- Backups automáticos de modelos existentes
- Instalação com um clique

### Workflow Completo

**Computador A (treino):**
1. Treina modelos com catálogos Lightroom
2. Exporta modelos via UI (cria ZIP)
3. Transfere ZIP para Computador B

**Computador B (produção):**
1. Importa ZIP via UI
2. Reinicia servidor: `./start_server.sh`
3. Usa imediatamente no Lightroom
4. (Opcional) Treina incrementalmente com mais catálogos

---

## 🔍 Verificação das Mudanças

### Verificar Menu do Plugin

Abre Lightroom e verifica o menu **File > Plug-in Extras > NSP Plugin**.

**Devias ver:**
- ✅ Iniciar Servidor AI
- ✅ AI Preset V2 (Auto Single/Batch)
- ✅ AI Preset - Preview Antes/Depois
- ✅ AI Preset - Enhanced Preview (Undo/Redo)
- ✅ Culling Inteligente
- ✅ Auto-Straighten
- ✅ Feedback Rápido
- ✅ Ver Estatísticas
- ✅ Re-treinar com Feedback
- ✅ Configurações

**NÃO devias ver:**
- ❌ Gestor de Presets
- ❌ Visual Preset Browser
- ❌ Exportar Preset Atual

### Verificar Ficheiros

```bash
# Ficheiros movidos (não devem existir aqui)
ls NSP-Plugin.lrplugin/PresetManager.lua  # ❌ Não existe
ls NSP-Plugin.lrplugin/VisualPresetBrowser.lua  # ❌ Não existe
ls NSP-Plugin.lrplugin/ExportCurrentPreset.lua  # ❌ Não existe

# Ficheiros em disabled_presets (devem existir)
ls NSP-Plugin.lrplugin/disabled_presets/*.lua  # ✅ 3 ficheiros
```

---

## 📊 Impacto das Mudanças

### Código Removido
- **3 ficheiros Lua** (~33 KB)
- **6 entradas de menu** (3 em File, 3 em Library)
- **0 quebras de compatibilidade** (funcionalidades AI intactas)

### Código Mantido
- **100% das funcionalidades AI** preservadas
- **Servidor Python** intacto
- **Sistema de treino** intacto
- **Modelos V2** funcionais

### Nova Funcionalidade
- **UI de Gestão de Modelos** (+520 linhas Python)
- **Export/Import automático** de modelos
- **Metadata e README** em cada export
- **Backups automáticos** no import

---

## ⚠️ Notas Importantes

1. **Compatibilidade**: Esta mudança **não afeta** catálogos ou fotos existentes. Apenas remove opções do menu do plugin.

2. **Modelos AI**: Todos os modelos treinados anteriormente **continuam a funcionar** normalmente.

3. **Lightroom Presets**: Os **presets nativos do Lightroom** (File > Develop Presets) **não são afetados**. Esta mudança remove apenas as funcionalidades customizadas do NSP Plugin.

4. **Reversível**: As mudanças são **completamente reversíveis**. Os ficheiros estão preservados em `disabled_presets/`.

5. **Server**: O servidor Python **não requer mudanças**. Continue a usar `./start_server.sh`.

---

## 🎯 Objetivo Final

**Criar um sistema AI puro e partilhável:**
- ✅ Modelos AI leves (~770KB) em vez de bibliotecas de presets
- ✅ Ajustes adaptativos por foto (não valores fixos)
- ✅ Partilha fácil entre computadores (ZIP)
- ✅ Treino incremental (sem perder conhecimento)
- ✅ Cross-platform (Mac/Windows/Linux)
- ✅ Focado em machine learning, não em gestão manual

---

## 📞 Suporte

Se tiveres problemas após estas mudanças:

1. **Verifica o servidor**: `curl http://127.0.0.1:5678/health`
2. **Logs do servidor**: `tail -f logs/server.log`
3. **Logs do Lightroom**: `~/Library/Logs/Adobe/Lightroom Classic/`
4. **Restaura presets tradicionais**: Segue instruções na secção "Como Restaurar"

---

**Última atualização:** 2025-11-25
**Autor:** Claude Code + Nelson Silva
**Versão do Plugin:** 0.6.0
