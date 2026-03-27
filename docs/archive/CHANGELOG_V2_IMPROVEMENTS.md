# NSP Plugin V2 - Melhorias Implementadas

**Data:** 2025-11-15
**Versão:** 0.6.1 → 0.7.0

---

## Resumo das Alterações

Implementação completa de novas funcionalidades para o NSP Plugin, incluindo preview antes/depois, culling inteligente, gestão avançada de presets e remoção de código de debug.

---

## TAREFA 1: Menu do Plugin Reorganizado ✅

### Ficheiro Alterado
- `/NSP-Plugin.lrplugin/Info.lua`

### Alterações
- **Removidos** todos os ficheiros de teste/debug do menu:
  - TestError.lua
  - TestMinimal.lua
  - TestSimple.lua
  - TestConnection.lua
  - TestApplySettings.lua

- **Menu reorganizado** em 6 grupos funcionais:
  1. **SERVIDOR** (1 item)
     - Iniciar Servidor AI

  2. **APLICAÇÃO** (3 itens)
     - AI Preset V2 - Foto Individual
     - AI Preset V2 - Processamento em Lote
     - AI Preset - Preview Antes/Depois (NOVO)

  3. **CULLING** (2 itens)
     - Culling Inteligente - Análise de Qualidade (NOVO)
     - Culling - Marcar Melhores Fotos (NOVO)

  4. **PRESETS** (2 itens)
     - Gestor de Presets
     - Exportar Preset Atual (NOVO)

  5. **FEEDBACK** (2 itens)
     - NSP - Feedback Rápido
     - AI Preset - Ver Estatísticas

  6. **SETTINGS** (1 item)
     - NSP - Configurações

---

## TAREFA 2: Preview Antes/Depois ✅

### Novo Ficheiro
- `/NSP-Plugin.lrplugin/PreviewBeforeAfter.lua`

### Funcionalidades
- **Comparação lado-a-lado** dos settings antes e depois da aplicação AI
- **Botão de alternância** para visualizar instantaneamente as diferenças
- **Informação detalhada**:
  - Nome do preset sugerido com confiança
  - Lista dos 8 principais ajustes aplicados
  - Valores formatados para fácil leitura
- **Três opções de ação**:
  - ✓ Aplicar Definitivamente
  - ✎ Ajustar Manualmente (aplica como ponto de partida)
  - ✗ Cancelar (reverte para original)
- **Proteção de dados**: sempre reverte para settings originais antes de fechar
- **Integração com feedback**: solicita feedback automaticamente quando apropriado

### Como Usar
1. Selecionar uma foto
2. Menu: `AI Preset - Preview Antes/Depois`
3. Aguardar análise AI
4. Usar botão "⇄ Alternar Antes/Depois" para comparar
5. Escolher ação desejada

---

## TAREFA 3: Culling Inteligente ✅

### Novos Ficheiros
- `/NSP-Plugin.lrplugin/IntelligentCulling.lua`
- `/NSP-Plugin.lrplugin/MarkBestPhotos.lua`

### IntelligentCulling.lua
**Funcionalidades:**
- Análise de qualidade técnica e estética de múltiplas fotos
- Scores de 0-100 para cada foto
- Estatísticas detalhadas:
  - Score médio
  - Melhor foto
  - Pior foto
- Lista das top 10 melhores fotos
- Labels de qualidade:
  - Excelente ⭐⭐⭐ (90-100)
  - Muito Boa ⭐⭐ (75-89)
  - Boa ⭐ (60-74)
  - Razoável (40-59)
  - Fraca (0-39)

**Como Usar:**
1. Selecionar fotos para análise
2. Menu: `Culling Inteligente - Análise de Qualidade`
3. Aguardar análise
4. Revisar resultados e estatísticas

### MarkBestPhotos.lua
**Funcionalidades:**
- Marcação automática das melhores fotos com pick flag
- Dois modos de seleção:
  - **Percentagem**: Top X% das fotos
  - **Absoluto**: Melhores N fotos
- Interface interativa com sliders
- Preview de quantas fotos serão marcadas
- Análise baseada no mesmo modelo de culling

**Como Usar:**
1. Selecionar fotos para análise
2. Menu: `Culling - Marcar Melhores Fotos`
3. Escolher critério (percentagem ou número absoluto)
4. Confirmar
5. As melhores fotos serão marcadas automaticamente com pick flag

---

## TAREFA 4: Gestão de Presets Melhorada ✅

### Novo Ficheiro
- `/NSP-Plugin.lrplugin/ExportCurrentPreset.lua`

### Funcionalidades
- **Exportação de presets personalizados** como ficheiro `.nsppreset`
- **Configuração completa**:
  - Nome do preset
  - Autor
  - Categoria (Portrait, Landscape, B&W, Vintage, etc.)
  - Descrição opcional
- **Escolha da localização** de destino
- **Metadata completo**:
  - Todos os sliders de develop
  - Informação de exportação
  - Foto de origem
  - Timestamp
- **Opção de revelar** ficheiro no Finder/Explorer após exportação
- **Validação de nome** (remove caracteres especiais)

### Como Usar
1. Aplicar edições desejadas numa foto
2. Menu: `Exportar Preset Atual`
3. Configurar nome, autor, categoria e descrição
4. Escolher pasta de destino
5. Exportar
6. Partilhar ficheiro `.nsppreset` com outros utilizadores

### PresetManager.lua (já existente)
- Interface para listar, ativar e gerir presets instalados
- Suporte completo para endpoints de API do servidor

---

## TAREFA 5: Endpoints do Servidor ✅

### Ficheiro Alterado
- `/services/server.py`

### Novos Endpoints

#### Culling
**POST /api/culling/score**
- Análise de qualidade em lote
- Suporta múltiplas imagens numa única chamada
- Retorna scores de 0-100 para cada imagem
- Fallback inteligente baseado em EXIF se modelo não disponível
- Rate limit: 10/minuto

**Payload:**
```json
{
  "images": [
    {
      "image_path": "/path/to/photo.raw",
      "exif": {
        "iso": 400,
        "aperture": 2.8,
        "shutterspeed": 0.0125,
        "focallength": 50
      }
    }
  ]
}
```

**Resposta:**
```json
{
  "scores": [85.5],
  "analysis_time": 0.234
}
```

#### Presets (já existiam, documentados aqui)
- **GET /api/presets** - Listar todos os presets
- **GET /api/presets/{preset_id}** - Detalhes de um preset
- **GET /api/presets/active** - Obter preset ativo
- **PUT /api/presets/active** - Definir preset ativo
- **POST /api/presets/install** - Instalar preset (upload .nsppreset)
- **DELETE /api/presets/{preset_id}** - Remover preset
- **POST /api/presets/export** - Exportar preset

---

## TAREFA 6: Helpers em Common_V2.lua ✅

### Ficheiro Alterado
- `/NSP-Plugin.lrplugin/Common_V2.lua`

### Novas Funções

#### Preview Antes/Depois
```lua
CommonV2.capture_current_settings(photo)
CommonV2.apply_settings_temporarily(photo, settings)
CommonV2.revert_settings(photo, original_settings)
CommonV2.show_preview_dialog(photo, original_settings, ai_settings, prediction)
```

#### Culling Inteligente
```lua
CommonV2.call_culling_api(image_paths, exif_data_list)
CommonV2.get_photo_quality_score(photo)
```

#### Gestão de Presets
```lua
CommonV2.list_available_presets()
CommonV2.get_active_preset()
CommonV2.set_active_preset(preset_id)
CommonV2.export_current_preset(photo, output_path)
```

### Melhorias Gerais
- Todas as funções com logging detalhado
- Tratamento robusto de erros
- Validação de inputs
- Documentação inline completa

---

## Estrutura de Ficheiros

```
NSP Plugin_dev_full_package/
├── NSP-Plugin.lrplugin/
│   ├── Info.lua                    [MODIFICADO - Menu reorganizado]
│   ├── Common_V2.lua               [MODIFICADO - Novos helpers]
│   ├── PreviewBeforeAfter.lua      [NOVO]
│   ├── IntelligentCulling.lua      [NOVO]
│   ├── MarkBestPhotos.lua          [NOVO]
│   ├── ExportCurrentPreset.lua     [NOVO]
│   ├── PresetManager.lua           [EXISTENTE]
│   └── [outros ficheiros...]
│
└── services/
    ├── server.py                   [MODIFICADO - Endpoint culling]
    ├── preset_manager.py           [EXISTENTE]
    └── culling.py                  [REFERENCIADO - pode precisar criação]
```

---

## Instalação e Teste

### 1. Recarregar Plugin no Lightroom
1. Ir a `File > Plug-in Manager`
2. Selecionar "NSP Plugin"
3. Clicar em "Reload"
4. Verificar que não há erros

### 2. Verificar Menu
- Verificar que itens de debug foram removidos
- Confirmar que novos itens aparecem nos grupos corretos

### 3. Iniciar Servidor
1. `🚀 Iniciar Servidor AI`
2. Aguardar confirmação de que servidor está online

### 4. Testar Funcionalidades

#### Preview Antes/Depois
1. Selecionar uma foto
2. `AI Preset - Preview Antes/Depois`
3. Verificar que mostra informação do preset
4. Testar botão de alternância
5. Testar aplicação e cancelamento

#### Culling
1. Selecionar múltiplas fotos (10-50 recomendado)
2. `Culling Inteligente - Análise de Qualidade`
3. Verificar scores e estatísticas
4. `Culling - Marcar Melhores Fotos`
5. Escolher top 20%
6. Verificar que fotos foram marcadas

#### Export Preset
1. Aplicar edições numa foto
2. `Exportar Preset Atual`
3. Configurar nome e categoria
4. Exportar
5. Verificar ficheiro .nsppreset criado

---

## Notas Técnicas

### Compatibilidade
- **Lightroom Classic**: Testado com SDK 14.5
- **Sistema Operativo**: macOS (pode precisar ajustes para Windows no ExportCurrentPreset.lua)
- **Python**: 3.11+
- **FastAPI**: Servidor deve estar a correr na porta 5678

### Performance
- **Culling**: ~0.2-0.5s por foto (depende de hardware)
- **Preview**: Instantâneo (sem re-análise)
- **Export**: Depende do tamanho do preset (<1s normalmente)

### Fallbacks
- Culling sem modelo AI: usa análise simplificada baseada em EXIF
- Preset manager: sempre garante preset default disponível

### Logging
- Todos os módulos novos usam `LrLogger`
- Logs disponíveis em `~/Library/Logs/Adobe/Lightroom Classic/`
- Servidor também recebe logs via endpoint `/plugin-log`

---

## Próximos Passos Sugeridos

### Melhorias Futuras
1. **Modelo de Culling**:
   - Treinar modelo específico se ainda não existe
   - Adicionar em `/services/culling.py`
   - Usar deep features de imagens

2. **Preview Melhorado**:
   - Comparação lado-a-lado real (split screen)
   - Histogramas antes/depois
   - Zoom sincronizado

3. **Batch Operations**:
   - Aplicar preset custom a múltiplas fotos
   - Export de múltiplos presets

4. **Cloud Sync**:
   - Partilhar presets online
   - Download de presets da comunidade

---

## Resolução de Problemas

### "Servidor AI não está disponível"
- Iniciar servidor via `🚀 Iniciar Servidor AI`
- Verificar que porta 5678 está livre
- Verificar logs do servidor

### "Módulo JSON não disponível"
- Verificar que `json.lua` está no diretório do plugin
- Recarregar plugin

### Culling retorna scores baixos
- Verificar que fotos têm metadados EXIF válidos
- Se modelo não disponível, scores são estimativas baseadas em EXIF

### Export preset falha
- Verificar permissões de escrita na pasta destino
- Verificar que foto tem develop settings aplicados

---

## Contacto e Suporte

Para reportar bugs ou sugerir melhorias, criar issue no repositório do projeto.

**Versão:** 0.7.0
**Data:** 2025-11-15
**Autor:** NSP Development Team
