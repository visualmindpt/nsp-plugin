# Guia de Instalação - NSP Plugin V2

## Requisitos

- Adobe Lightroom Classic (versão 14.5 ou superior)
- Python 3.11+
- macOS ou Windows

---

## Instalação Rápida

### 1. Instalar Plugin no Lightroom

1. Localizar pasta do plugin:
   ```
   /Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin/
   ```

2. Abrir Lightroom Classic

3. Ir a `File > Plug-in Manager...`

4. Clicar em `Add` (botão inferior esquerdo)

5. Navegar até a pasta `NSP-Plugin.lrplugin` e selecionar

6. Clicar em `Add Plug-in`

7. Verificar que "NSP Plugin" aparece na lista e está ativo

### 2. Configurar Servidor AI

1. Abrir Terminal

2. Navegar até a pasta do projeto:
   ```bash
   cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
   ```

3. Criar ambiente virtual Python (se ainda não existe):
   ```bash
   python3 -m venv venv
   ```

4. Ativar ambiente virtual:
   ```bash
   source venv/bin/activate  # macOS/Linux
   # ou
   venv\Scripts\activate  # Windows
   ```

5. Instalar dependências:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Iniciar Servidor

**Opção A: Via Lightroom** (Recomendado)
1. No Lightroom: `File > Plug-in Extras > 🚀 Iniciar Servidor AI`
2. Aguardar mensagem de confirmação

**Opção B: Via Terminal**
```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate
python -m uvicorn services.server:app --host 127.0.0.1 --port 5678
```

### 4. Verificar Instalação

1. No Lightroom: `File > Plug-in Extras`

2. Verificar que o menu mostra:
   ```
   SERVIDOR
   - 🚀 Iniciar Servidor AI

   APLICAÇÃO
   - AI Preset V2 - Foto Individual
   - AI Preset V2 - Processamento em Lote
   - AI Preset - Preview Antes/Depois

   CULLING
   - Culling Inteligente - Análise de Qualidade
   - Culling - Marcar Melhores Fotos

   PRESETS
   - Gestor de Presets
   - Exportar Preset Atual

   FEEDBACK
   - NSP - Feedback Rápido
   - AI Preset - Ver Estatísticas

   SETTINGS
   - NSP - Configurações
   ```

3. Selecionar uma foto e testar: `AI Preset - Preview Antes/Depois`

---

## Guia de Uso Rápido

### Preview Antes/Depois

**Para que serve:**
- Visualizar resultado do preset AI antes de aplicar
- Comparar lado-a-lado foto original vs editada
- Decidir se aplicar, ajustar ou cancelar

**Como usar:**
1. Selecionar UMA foto
2. `AI Preset - Preview Antes/Depois`
3. Clicar em "⇄ Alternar Antes/Depois" para comparar
4. Escolher:
   - ✓ Aplicar Definitivamente
   - ✎ Ajustar Manualmente
   - ✗ Cancelar

### Culling Inteligente

**Para que serve:**
- Analisar qualidade de múltiplas fotos
- Obter scores de 0-100 para cada foto
- Ver estatísticas (média, melhor, pior)

**Como usar:**
1. Selecionar MÚLTIPLAS fotos
2. `Culling Inteligente - Análise de Qualidade`
3. Aguardar análise
4. Revisar top 10 e estatísticas

### Marcar Melhores Fotos

**Para que serve:**
- Marcar automaticamente as melhores fotos com pick flag
- Escolher top X% ou melhores N fotos

**Como usar:**
1. Selecionar MÚLTIPLAS fotos
2. `Culling - Marcar Melhores Fotos`
3. Escolher critério:
   - **Percentagem**: Top 20% (exemplo)
   - **Absoluto**: Melhores 10 fotos (exemplo)
4. Confirmar
5. Fotos marcadas automaticamente

### Exportar Preset Atual

**Para que serve:**
- Criar preset personalizado a partir de edições
- Partilhar preset com outros utilizadores
- Guardar presets favoritos

**Como usar:**
1. Editar uma foto ao gosto
2. `Exportar Preset Atual`
3. Configurar:
   - Nome do preset
   - Autor
   - Categoria
   - Descrição
4. Escolher pasta de destino
5. Exportar
6. Ficheiro `.nsppreset` criado

---

## Resolução de Problemas Comuns

### Servidor não inicia

**Sintoma:** Mensagem "Servidor AI não está disponível"

**Solução:**
1. Verificar que porta 5678 está livre:
   ```bash
   lsof -i :5678  # macOS/Linux
   ```
2. Matar processo se necessário:
   ```bash
   kill -9 <PID>
   ```
3. Iniciar servidor manualmente via Terminal
4. Verificar logs em:
   ```
   ~/Library/Logs/Adobe/Lightroom Classic/
   ```

### Plugin não aparece no menu

**Solução:**
1. `File > Plug-in Manager`
2. Verificar que "NSP Plugin" está na lista
3. Se não está: clicar em `Add` e selecionar pasta do plugin
4. Se está mas inativo: clicar em checkbox para ativar
5. Clicar em `Reload` para recarregar

### Erro "Módulo JSON não disponível"

**Solução:**
1. Verificar que ficheiro `json.lua` existe em:
   ```
   NSP-Plugin.lrplugin/json.lua
   ```
2. Se não existe, copiar de backup ou re-instalar plugin
3. Recarregar plugin no Lightroom

### Culling retorna scores muito baixos

**Causa:** Modelo de culling não disponível, usando fallback EXIF

**Solução:**
1. Verificar que existe ficheiro:
   ```
   models/culling_model.pth
   ```
2. Se não existe, modelo será criado após treino
3. Por enquanto, scores são estimativas baseadas em ISO e abertura

### Export preset falha

**Sintomas:**
- "Erro ao escrever ficheiro"
- "Não foi possível criar ficheiro"

**Solução:**
1. Verificar permissões de escrita na pasta destino
2. Escolher outra pasta (ex: Desktop)
3. Verificar que foto tem develop settings aplicados
4. Tentar novamente

---

## Estrutura de Pastas

```
NSP Plugin_dev_full_package/
│
├── NSP-Plugin.lrplugin/          # Plugin Lightroom
│   ├── Info.lua                  # Configuração do plugin
│   ├── Common_V2.lua             # Funções auxiliares
│   ├── json.lua                  # Parser JSON
│   │
│   ├── PreviewBeforeAfter.lua    # NOVO: Preview antes/depois
│   ├── IntelligentCulling.lua    # NOVO: Análise de qualidade
│   ├── MarkBestPhotos.lua        # NOVO: Marcar melhores
│   ├── ExportCurrentPreset.lua   # NOVO: Exportar preset
│   │
│   └── [outros módulos...]
│
├── services/                     # Servidor FastAPI
│   ├── server.py                 # API principal
│   ├── preset_manager.py         # Gestor de presets
│   ├── culling.py               # Modelo de culling
│   └── [outros módulos...]
│
├── models/                       # Modelos AI
│   ├── best_preset_classifier.pth
│   ├── best_refinement_model.pth
│   ├── culling_model.pth         # Modelo de culling
│   └── [configurações...]
│
├── data/                         # Base de dados
│   └── feedback.db
│
├── presets/                      # Presets instalados
│   ├── default/                  # Preset default
│   └── installed/                # Presets customizados
│
└── venv/                         # Ambiente virtual Python
```

---

## Atalhos de Teclado (Sugeridos)

Podes criar atalhos personalizados no Lightroom para acesso rápido:

1. Ir a `Edit > Keyboard Shortcuts...`
2. Procurar por "NSP" ou "Plug-in"
3. Atribuir atalhos favoritos, por exemplo:
   - `Cmd+Shift+P`: Preview Antes/Depois
   - `Cmd+Shift+C`: Culling Inteligente
   - `Cmd+Shift+M`: Marcar Melhores Fotos

---

## Workflows Recomendados

### Workflow 1: Edição Rápida com Preview
1. Importar fotos
2. Fazer seleção inicial manual
3. Para cada foto:
   - `AI Preset - Preview Antes/Depois`
   - Comparar antes/depois
   - Aplicar ou ajustar

### Workflow 2: Culling + AI Batch
1. Importar sessão de fotos
2. `Culling - Marcar Melhores Fotos` (top 20%)
3. Filtrar por pick flag
4. `AI Preset V2 - Processamento em Lote`
5. Revisar e ajustar individualmente

### Workflow 3: Criar e Partilhar Preset
1. Editar uma foto manualmente (teu estilo)
2. `Exportar Preset Atual`
3. Partilhar ficheiro `.nsppreset` com equipa
4. Equipa instala via Dashboard ou diretamente

---

## Suporte e Documentação

### Logs
- **Lightroom:** `~/Library/Logs/Adobe/Lightroom Classic/`
- **Servidor:** Terminal onde servidor está a correr
- **Plugin:** Ficheiros `.log` na pasta do plugin

### Documentação Completa
- `CHANGELOG_V2_IMPROVEMENTS.md` - Lista detalhada de melhorias
- `README.md` - Documentação geral do projeto

### Reportar Bugs
Criar issue no repositório com:
- Descrição do problema
- Passos para reproduzir
- Logs relevantes
- Screenshots (se aplicável)

---

## Atualizações Futuras

Funcionalidades planeadas:
- Comparação lado-a-lado real no preview
- Histogramas antes/depois
- Export de múltiplos presets em lote
- Cloud sync de presets
- Modelo de culling melhorado com deep learning

---

**Versão:** 0.7.0
**Data:** 2025-11-15
**Instalação testada em:** macOS 15.6, Lightroom Classic 14.5
