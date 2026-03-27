# Arquitectura Completa do Sistema de Feedback - NSP Plugin

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ADOBE LIGHTROOM CLASSIC                          │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Main.lua   │  │ Implicit     │  │ FeedbackUI   │             │
│  │              │  │ Feedback.lua │  │              │             │
│  │ 1. Captura   │→ │              │  │ 1. Diálogo   │             │
│  │    vector_   │  │ 2. Start     │  │    modal     │             │
│  │    before    │  │    session   │  │ 2. Rating    │             │
│  │              │  │              │  │    selection │             │
│  │ 2. Chama AI  │  │ 3. Schedule  │  │              │             │
│  │    /predict  │  │    check     │  │ 3. Send to   │             │
│  │              │  │              │  │    /feedback │             │
│  │ 3. Recebe    │  │ 4. Detect    │  │    /explicit │             │
│  │    vector_ai │  │    edits     │  │              │             │
│  │              │  │              │  │              │             │
│  │ 4. Aplica    │  │ 5. Send to   │  │              │             │
│  │    settings  │  │    /feedback │  │              │             │
│  │              │  │    /implicit │  │              │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                 │                      │
│         └─────────────────┴─────────────────┘                      │
│                           │                                         │
│                    ┌──────▼────────┐                               │
│                    │  Common.lua   │                               │
│                    │               │                               │
│                    │ - post_json() │                               │
│                    │ - UUID gen    │                               │
│                    │ - Photo hash  │                               │
│                    │ - Vector→Array│                               │
│                    └──────┬────────┘                               │
└───────────────────────────┼─────────────────────────────────────────┘
                            │ HTTP POST
                            │ JSON Payloads
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      FASTAPI SERVER                                 │
│                   (Python Backend)                                  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    API Endpoints                             │  │
│  │                                                              │  │
│  │  POST /predict          → Retorna edições AI                │  │
│  │  POST /feedback/implicit → Grava feedback automático        │  │
│  │  POST /feedback/explicit → Grava feedback manual            │  │
│  │  POST /feedback/granular → Grava feedback por slider        │  │
│  │  GET  /health            → Status do servidor               │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
│                         │                                           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │               FeedbackManager (Python)                       │  │
│  │                                                              │  │
│  │  - save_implicit_feedback()                                 │  │
│  │  - save_explicit_feedback()                                 │  │
│  │  - save_granular_feedback()                                 │  │
│  │  - get_feedback_stats()                                     │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
│                         │                                           │
└─────────────────────────┼───────────────────────────────────────────┘
                          │ SQL INSERT
                          │
┌─────────────────────────▼───────────────────────────────────────────┐
│                    SQLite Database                                  │
│                      (feedback.db)                                  │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ implicit_feedback│  │ explicit_feedback│  │granular_feedback│  │
│  │                  │  │                  │  │                 │  │
│  │ - session_uuid   │  │ - session_uuid   │  │ - session_uuid  │  │
│  │ - photo_hash     │  │ - photo_hash     │  │ - photo_hash    │  │
│  │ - vector_before  │  │ - vector_current │  │ - slider_name   │  │
│  │ - vector_ai      │  │ - rating         │  │ - value_before  │  │
│  │ - vector_final   │  │ - user_notes     │  │ - value_after   │  │
│  │ - model_version  │  │ - exif_data      │  │ - user_accepted │  │
│  │ - exif_data      │  │ - model_version  │  │ - model_version │  │
│  │ - created_at     │  │ - created_at     │  │ - created_at    │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Fluxo de Dados Detalhado

### Fluxo A: Feedback Implícito (Automático)

```
╔════════════════════════════════════════════════════════════════════╗
║  TIMELINE: Feedback Implícito                                      ║
╚════════════════════════════════════════════════════════════════════╝

T=0s    │ Utilizador executa "NSP – Get AI Edit"
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ Main.lua:                               │
        │   vector_before = collect_vector(photo) │
        │   {exposure: 0.0, contrast: 10.0, ...}  │
        └─────────────────────────────────────────┘
        │
        ▼
T=1s    │ POST /predict
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ Servidor retorna:                       │
        │   vector_ai = {exposure: 2.5, ...}      │
        └─────────────────────────────────────────┘
        │
        ▼
T=2s    │ Main.lua aplica settings
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ ImplicitFeedback.start_session()        │
        │   - Gera session_uuid                   │
        │   - Calcula photo_hash                  │
        │   - Armazena session_data em memória    │
        │   - Agenda check após 30s               │
        └─────────────────────────────────────────┘
        │
        │ [Utilizador edita foto manualmente]
        │
        ▼
T=32s   │ ImplicitFeedback.check_and_send()
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ 1. Recolhe vector_final                 │
        │    {exposure: 15.0, ...}                │
        │                                         │
        │ 2. Calcula max_delta                    │
        │    delta = |15.0 - 2.5| = 12.5          │
        │                                         │
        │ 3. Compara com threshold (5.0)          │
        │    12.5 > 5.0 → Edição detectada!       │
        └─────────────────────────────────────────┘
        │
        ▼
T=33s   │ POST /feedback/implicit
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ Servidor grava em implicit_feedback:    │
        │   - session_uuid: "a1b2..."             │
        │   - photo_hash: "ph_123..."             │
        │   - vector_before: [0.0, 10.0, ...]     │
        │   - vector_ai: [2.5, 10.0, ...]         │
        │   - vector_final: [15.0, 10.0, ...]     │
        │   - model_version: "nn"                 │
        └─────────────────────────────────────────┘
        │
        ▼
T=34s   │ Sessão removida da memória
        │
        ✓ COMPLETO
```

### Fluxo B: Feedback Explícito (Manual)

```
╔════════════════════════════════════════════════════════════════════╗
║  TIMELINE: Feedback Explícito                                      ║
╚════════════════════════════════════════════════════════════════════╝

T=0s    │ Utilizador seleciona 3 fotos
        │ Executa "NSP – Enviar Feedback (Diálogo)"
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ FeedbackUI.show_feedback_dialog()       │
        │                                         │
        │ Mostra modal com:                       │
        │   ○ Boa                                 │
        │   ● Precisa correção  ← seleccionado    │
        │   ○ Má                                  │
        │                                         │
        │ Notas: "Exposição ainda muito alta"     │
        └─────────────────────────────────────────┘
        │
        ▼
T=5s    │ Utilizador clica "Enviar"
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ Para cada foto (3x):                    │
        │   1. Recolhe vector_current             │
        │   2. Gera session_uuid único            │
        │   3. Calcula photo_hash                 │
        │   4. Recolhe EXIF                       │
        └─────────────────────────────────────────┘
        │
        ▼
T=6s    │ POST /feedback/explicit (foto 1)
T=7s    │ POST /feedback/explicit (foto 2)
T=8s    │ POST /feedback/explicit (foto 3)
        │
        ▼
        ┌─────────────────────────────────────────┐
        │ Servidor grava 3 registos:              │
        │   rating: "needs_correction"            │
        │   user_notes: "Exposição ainda..."      │
        │   model_version: "nn"                   │
        └─────────────────────────────────────────┘
        │
        ▼
T=9s    │ Mostra diálogo de confirmação
        │ "✓ Feedback enviado para 3 foto(s)"
        │
        ✓ COMPLETO
```

## Componentes Lua - Responsabilidades

### Main.lua
**Papel**: Orquestrador principal do fluxo de edições AI

**Responsabilidades**:
- Capturar `vector_before` ANTES de chamar `/predict`
- Receber `vector_ai` do servidor
- Aplicar settings ao Lightroom
- Iniciar sessão de feedback implícito (se activo)
- Gerir batch processing de múltiplas fotos

**Integrações**:
- `Common.collect_develop_vector()` → Captura estado actual
- `Common.post_json("/predict", ...)` → Chama IA
- `ImplicitFeedback.start_session(...)` → Inicia tracking

### ImplicitFeedback.lua
**Papel**: Motor de detecção automática de edições

**Responsabilidades**:
- Criar e gerir sessões de tracking em memória
- Agendar verificações após delay configurável
- Detectar edições com delta > threshold
- Enviar feedback para `/feedback/implicit`
- Limpar sessões expiradas

**Estado Global**:
```lua
private.active_sessions = {
    ["photo_id_1"] = session_data,
    ["photo_id_2"] = session_data,
    ...
}
```

**Configuração**:
```lua
CHECK_DELAY_SECONDS = 30      -- Tempo antes de verificar
DELTA_THRESHOLD = 5.0         -- Mínimo para considerar edição
MAX_SESSION_AGE_SECONDS = 3600 -- Expirar após 1 hora
```

### FeedbackUI.lua
**Papel**: Interface de utilizador para feedback manual

**Responsabilidades**:
- Mostrar diálogo modal com opções de rating
- Recolher notas opcionais do utilizador
- Processar múltiplas fotos em batch
- Fornecer atalhos rápidos (mark_as_good, mark_as_needs_correction)
- Mostrar confirmações e resultados

**UI Components**:
- Radio buttons para rating
- Edit field para notas
- Botão "Enviar" / "Cancelar"
- Diálogo de confirmação

### Common.lua
**Papel**: Biblioteca de utilitários partilhados

**Novas Funções (Fase 3)**:

```lua
generate_uuid() → string
  -- Gera UUID v4 para session_uuid
  -- Exemplo: "a1b2c3d4-e5f6-4789-yxyz-1234567890ab"

calculate_photo_hash(photo) → string
  -- Hash baseado em path + file_size
  -- Exemplo: "ph_1a2b3c4d"

vector_to_array(vector_dict) → array[38]
  -- Converte {exposure: 2.5, ...} → [2.5, ...]
  -- Ordem: match exacto com ALL_SLIDER_NAMES

array_to_vector(array) → vector_dict
  -- Operação inversa (debug/testes)
```

**Funções Existentes**:
- `post_json(endpoint, payload)` → HTTP POST
- `collect_develop_vector(photo)` → Captura sliders
- `validate_exif(photo)` → Valida metadados

## Estrutura de Payloads

### 1. Implicit Feedback Payload

```json
{
  "session_uuid": "a1b2c3d4-e5f6-4789-yxyz-1234567890ab",
  "photo_hash": "ph_1a2b3c4d",
  "vector_before": [
    0.0,    // exposure
    10.0,   // contrast
    -5.0,   // highlights
    // ... 35 mais valores (total: 38)
  ],
  "vector_ai": [
    2.5,    // exposure (sugerido pela AI)
    15.0,   // contrast
    -10.0,  // highlights
    // ... 35 mais valores
  ],
  "vector_final": [
    15.0,   // exposure (editado pelo user)
    20.0,   // contrast
    -15.0,  // highlights
    // ... 35 mais valores
  ],
  "model_version": "nn",
  "exif_data": {
    "iso": 400,
    "width": 6000,
    "height": 4000
  },
  "photo_category": null
}
```

**Campos Críticos**:
- `vector_*`: Arrays de EXACTAMENTE 38 floats
- Ordem: `Common.ALL_SLIDER_NAMES`
- `session_uuid`: Único por sessão
- `photo_hash`: Único por foto

### 2. Explicit Feedback Payload

```json
{
  "session_uuid": "x9y8z7w6-v5u4-4321-abcd-ef0123456789",
  "photo_hash": "ph_9z8y7x6w",
  "vector_current": [
    15.0,   // exposure (estado actual)
    20.0,   // contrast
    // ... 36 mais valores (total: 38)
  ],
  "rating": "good",  // ou "needs_correction" ou "bad"
  "user_notes": "Excelente correção automática de exposição",
  "exif_data": {
    "iso": 800,
    "width": 4000,
    "height": 6000
  },
  "model_version": "nn"
}
```

**Validações (Pydantic)**:
- `rating`: Enum com 3 valores permitidos
- `user_notes`: Opcional, string
- `vector_current`: Lista de 38 floats

## Ordem dos 38 Sliders (CRÍTICO!)

```python
# Python (feedback_manager.py)
ALL_SLIDER_NAMES = [
    "exposure", "contrast", "highlights", "shadows", "whites", "blacks",
    "texture", "clarity", "dehaze", "vibrance", "saturation",
    "temp", "tint",
    "sharpen_amount", "sharpen_radius", "sharpen_detail", "sharpen_masking",
    "nr_luminance", "nr_detail", "nr_color",
    "vignette", "grain", "shadow_tint",
    "red_primary_hue", "red_primary_saturation",
    "green_primary_hue", "green_primary_saturation",
    "blue_primary_hue", "blue_primary_saturation",
    "red_hue", "red_saturation", "red_luminance",
    "green_hue", "green_saturation", "green_luminance",
    "blue_hue", "blue_saturation", "blue_luminance"
]
```

```lua
-- Lua (Common.lua)
Common.ALL_SLIDER_NAMES = {
    "exposure", "contrast", "highlights", "shadows", "whites", "blacks",
    "texture", "clarity", "dehaze", "vibrance", "saturation",
    "temp", "tint",
    "sharpen_amount", "sharpen_radius", "sharpen_detail", "sharpen_masking",
    "nr_luminance", "nr_detail", "nr_color",
    "vignette", "grain", "shadow_tint",
    "red_primary_hue", "red_primary_saturation",
    "green_primary_hue", "green_primary_saturation",
    "blue_primary_hue", "blue_primary_saturation",
    "red_hue", "red_saturation", "red_luminance",
    "green_hue", "green_saturation", "green_luminance",
    "blue_hue", "blue_saturation", "blue_luminance"
}
```

**IMPORTANTE**: Estas listas DEVEM ser idênticas. Qualquer discrepância causa erros de mapeamento.

## Gestão de Estado

### Sessões Activas (ImplicitFeedback.lua)

```lua
-- Estrutura de uma sessão
{
    session_uuid = "uuid-here",
    photo_hash = "ph_hash",
    photo_id = "12345",           -- localIdentifier
    vector_before = {...},        -- Dict com 38 sliders
    vector_ai = {...},
    model_version = "nn",
    exif_data = {...},
    timestamp = 1699876543,       -- os.time()
    photo = <LrPhoto>             -- Referência (pode expirar)
}

-- Armazenamento global
private.active_sessions = {
    ["12345"] = session_data_1,
    ["67890"] = session_data_2,
    ...
}
```

**Ciclo de Vida**:
1. **Criação**: `start_session()` após aplicar edições AI
2. **Scheduling**: Verificação agendada após 30s
3. **Verificação**: `check_and_send()` detecta edições
4. **Envio**: POST para `/feedback/implicit`
5. **Remoção**: Sessão eliminada após sucesso ou expiração

**Limpeza**:
- Automática em `check_and_send()` (remove expiradas)
- Manual com `clear_all_sessions()` (debug/reset)

## Tratamento de Erros

### Níveis de Resiliência

```
┌─────────────────────────────────────────────────────────────┐
│ Nível 1: Rede/Servidor                                      │
│   - Timeout em HTTP requests (120s)                         │
│   - Retry logic em Common.post_json()                       │
│   - Log de erro, mas não crashar                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Nível 2: Validação de Dados                                 │
│   - Verificar photo válida antes de processar               │
│   - Validar EXIF antes de enviar                            │
│   - Pydantic valida payloads no servidor                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Nível 3: Isolamento de Falhas                              │
│   - pcall() envolve start_session() no Main.lua            │
│   - Falha de feedback não impede edição AI                  │
│   - Sessões inválidas removidas silenciosamente             │
└─────────────────────────────────────────────────────────────┘
```

### Exemplo de Error Handling

```lua
-- Em Main.lua (linha 174-182)
local feedback_enabled = prefs.enable_implicit_feedback
if feedback_enabled == nil then
    feedback_enabled = true
end

if feedback_enabled then
    local feedback_success = pcall(function()
        ImplicitFeedback.start_session(photo, vector_before, sliders, modelToUse)
    end)

    if not feedback_success then
        logger:warn("Falha ao iniciar sessão de feedback")
        -- Continua normalmente, edição AI já foi aplicada
    end
end
```

## Performance e Optimizações

### Operações Assíncronas

```lua
-- Verificação de edições não bloqueia UI
LrTasks.startAsyncTask(function()
    LrTasks.sleep(delay)
    ImplicitFeedback.check_and_send(photo_id)
end)

-- Envio de feedback em background
LrTasks.startAsyncTask(function()
    private.send_feedback_to_server(session_data, vector_final)
end)
```

### Batch Processing

- Main.lua processa fotos em lotes de 50 (`BATCH_SIZE`)
- FeedbackUI.lua processa sequencialmente (evitar sobrecarga)
- Timeout de 120s por POST request

### Uso de Memória

**Estimativa por Sessão**:
- `session_uuid`: ~36 bytes
- `photo_hash`: ~15 bytes
- `vector_before/ai`: ~38 × 8 bytes = 304 bytes cada
- `exif_data`: ~100 bytes
- **Total**: ~1 KB por sessão

**Capacidade**:
- 100 sessões activas = ~100 KB
- Limpeza automática após 1 hora
- Impacto negligenciável no Lightroom

## Debugging e Logging

### Activar Logs

```lua
-- Em cada módulo
local logger = LrLogger('NSPPlugin.ModuleName')
logger:enable("logfile")
```

### Mensagens Importantes

**ImplicitFeedback.lua**:
```
[INFO] Sessão de feedback iniciada - session_uuid: xxx
[TRACE] A agendar verificação para photo_id: xxx em 30 segundos
[TRACE] Verificação de edições - max_delta: 12.50
[INFO] Edições detectadas (delta: 12.50) - A enviar feedback
[INFO] Feedback implícito enviado com sucesso
[INFO] Limpeza de sessões: 3 sessões expiradas removidas
```

**FeedbackUI.lua**:
```
[TRACE] A enviar feedback explícito: good
[INFO] Feedback explícito enviado com sucesso - rating: good
[ERROR] Falha ao enviar feedback: Erro de comunicação...
```

**Common.lua**:
```
[TRACE] POST /feedback/implicit com payload: {...}
[TRACE] Response status: 200
[ERROR] Resposta não-OK do servidor: 500
```

### Localização de Logs

- **macOS**: `~/Library/Logs/LrClassicLogs/`
- **Windows**: `%APPDATA%\Adobe\Lightroom\Logs\`

### Comandos de Debug

```bash
# Monitorizar logs em tempo real (macOS)
tail -f ~/Library/Logs/LrClassicLogs/*.log | grep -i feedback

# Ver últimas 100 linhas com feedback
grep -i feedback ~/Library/Logs/LrClassicLogs/*.log | tail -100

# Contar sessões iniciadas hoje
grep "Sessão de feedback iniciada" ~/Library/Logs/LrClassicLogs/*.log | grep "$(date +%Y-%m-%d)" | wc -l
```

## Roadmap e Extensões Futuras

### Fase 4: Analytics Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ Dashboard Web (Flask/Streamlit)                             │
│                                                             │
│ - Métricas de aceitação (% good vs needs_correction)       │
│ - Sliders mais editados                                    │
│ - Heatmap de edições (por categoria de foto)               │
│ - Timeline de feedback                                     │
└─────────────────────────────────────────────────────────────┘
```

### Fase 5: Fine-tuning Automático

```
┌─────────────────────────────────────────────────────────────┐
│ Training Pipeline                                           │
│                                                             │
│ 1. Exportar dados de implicit_feedback                     │
│ 2. Preparar dataset (vector_ai → vector_final)             │
│ 3. Retreinar modelo com novos dados                        │
│ 4. Validar melhorias em test set                           │
│ 5. Deploy novo modelo (model_version++)                    │
└─────────────────────────────────────────────────────────────┘
```

### Fase 6: Categorização Inteligente

```
┌─────────────────────────────────────────────────────────────┐
│ Photo Category Inference                                    │
│                                                             │
│ - Analisar EXIF (focal_length, aperture) → portrait?       │
│ - Analisar histograma → landscape?                         │
│ - Detectar faces → portrait                                │
│ - Usar modelo pré-treinado (ResNet50) → classify           │
└─────────────────────────────────────────────────────────────┘
```

---

**Arquitectura Completa Documentada** ✓

Sistema de feedback totalmente integrado, escalável e pronto para produção.
