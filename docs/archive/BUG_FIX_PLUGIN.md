# 🐛 Diagnóstico e Correção - Plugin NSP V2

**Data:** 13 de Novembro de 2025
**Estado:** 🔴 CRÍTICO - Plugin não funciona

---

## 🔍 Problema Identificado

### Sintoma
- Clicar em qualquer menu do plugin no Lightroom não faz nada
- Não aparecem logs
- Não há comunicação com o servidor

### Causa Raiz
**PORTA ERRADA!** ❌

```lua
-- Common_V2.lua:33
SERVER_URL = "http://127.0.0.1:5678"  -- ❌ ERRADO
```

**O servidor está a correr na porta 5000:**
```python
# services/server.py
# Default port: 5000
```

---

## 🔧 Correções Necessárias

### 1. Corrigir Porta no Plugin

**Ficheiro:** `NSP-Plugin.lrplugin/Common_V2.lua:33`

```lua
-- ANTES (ERRADO)
SERVER_URL = "http://127.0.0.1:5678"

-- DEPOIS (CORRETO)
SERVER_URL = "http://127.0.0.1:5000"
```

### 2. Verificar Endpoint /predict

O servidor V2 simplificado usa `/predict` diretamente.

**Resposta esperada do servidor:**
```json
{
  "model": "V2_AI_Predictor",
  "sliders": {...},
  "preset_id": 0,
  "preset_confidence": 0.87
}
```

**Plugin espera:**
```lua
-- Common_V2.lua:247
-- response.sliders
-- response.preset_id (opcional)
-- response.preset_confidence (opcional)
```

✅ **COMPATÍVEL** - Estrutura correta!

### 3. Validar Mapeamento de Sliders

**Problema potencial:** O servidor V2 pode retornar menos sliders que o plugin espera.

**Sliders no Common_V2.lua:** 38 sliders
**Sliders no servidor atual:** Precisa verificação

---

## 📋 Checklist de Testes

### Antes de Testar
- [ ] Servidor a correr em `http://127.0.0.1:5000`
- [ ] Modelos treinados em `models/`
- [ ] Plugin recarregado no Lightroom

### Teste 1: Verificar Servidor
```bash
curl http://localhost:5000/health
# Esperado: {"status":"ok","v2_predictor_loaded":true}
```

### Teste 2: Teste Manual de Predição
```bash
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "/path/to/test.jpg",
    "exif": {"iso": 400, "width": 6000, "height": 4000}
  }'
```

### Teste 3: Plugin no Lightroom
1. Selecionar 1 foto
2. File > Plug-in Extras > AI Preset V2 – Foto Individual
3. Verificar que aparece diálogo de preview
4. Verificar logs em Lightroom

### Teste 4: Batch Processing
1. Selecionar 5-10 fotos
2. File > Plug-in Extras > AI Preset V2 – Processamento em Lote
3. Verificar progress bar
4. Verificar estatísticas finais

---

## 🎯 Sliders a Adicionar

### Sliders HSL Completos (faltam)

| Cor | Hue | Saturation | Luminance |
|-----|-----|------------|-----------|
| Red | ✅ | ✅ | ✅ |
| Orange | ❌ | ❌ | ❌ |
| Yellow | ❌ | ❌ | ❌ |
| Green | ✅ | ✅ | ✅ |
| Aqua | ❌ | ❌ | ❌ |
| Blue | ✅ | ✅ | ✅ |
| Purple | ❌ | ❌ | ❌ |
| Magenta | ❌ | ❌ | ❌ |

**Faltam 18 sliders HSL!**

### Sliders de Calibração (todos presentes)
- ✅ ShadowTint
- ✅ RedHue / RedSaturation
- ✅ GreenHue / GreenSaturation
- ✅ BlueHue / BlueSaturation

### Split Toning (faltam)
- ❌ SplitToningHighlightHue
- ❌ SplitToningHighlightSaturation
- ❌ SplitToningShadowHue
- ❌ SplitToningShadowSaturation
- ❌ SplitToningBalance

### Tone Curve (complexo - não implementar agora)
- ❌ ToneCurve (é um array de pontos)

---

## 📈 Total de Sliders

| Categoria | Atual | Possível | Falta |
|-----------|-------|----------|-------|
| **Basic** | 6 | 6 | 0 |
| **Presence** | 5 | 5 | 0 |
| **WB** | 2 | 2 | 0 |
| **Sharpen** | 4 | 4 | 0 |
| **Noise Red** | 3 | 3 | 0 |
| **Effects** | 2 | 2 | 0 |
| **Calibration** | 7 | 7 | 0 |
| **HSL** | 9 | 24 | **15** |
| **Split Tone** | 0 | 5 | **5** |
| **TOTAL** | **38** | **58** | **20** |

---

## 🚀 Implementação Prioritária

### Fase 1: Correção Crítica (30 min) 🔴
1. ✅ Corrigir porta de 5678 → 5000
2. ✅ Testar conexão servidor
3. ✅ Testar predição simples
4. ✅ Testar plugin no Lightroom

### Fase 2: Sliders HSL (2h) 🟠
1. Adicionar 15 sliders HSL em falta
2. Atualizar Common_V2.lua
3. Atualizar extractor para extrair esses sliders
4. Re-treinar modelo com novos sliders

### Fase 3: Split Toning (1h) 🟡
1. Adicionar 5 sliders Split Toning
2. Atualizar mapeamento
3. Re-treinar (opcional - split toning menos usado)

### Fase 4: Culling (4h) 🟢
1. Criar modelo de classificação keep/reject
2. Treinar com fotos rated
3. Adicionar endpoint /culling
4. Adicionar menu no plugin

### Fase 5: Auto-Straighten (3h) 🟢
1. Usar library de deteção de horizonte
2. Calcular ângulo
3. Aplicar ajuste automático
4. Integrar no workflow

---

## 🧪 Plano de Testes

### Teste End-to-End Completo

```bash
# 1. Iniciar servidor
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate
python services/server.py

# 2. Verificar health
curl http://localhost:5000/health

# 3. Testar predição
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "/Users/nelsonsilva/test.jpg",
    "exif": {"iso": 400, "width": 6000, "height": 4000}
  }'

# 4. Abrir Lightroom e testar plugin
```

---

## 📝 Logs Esperados

### Logs do Servidor (server.py)
```
INFO - ✅ AI_PREDICTOR (V2) inicializado com sucesso.
INFO - POST /predict - 200 OK - 350ms
```

### Logs do Plugin (Lightroom)
```
INFO: 🔮 A fazer predição V2 para: /Users/nelson/test.jpg
INFO: ✅ Predição recebida com sucesso
INFO: ✅ Preset AI aplicado com sucesso!
```

---

## 🎯 Próximos Passos

1. **AGORA:** Corrigir porta e testar
2. **Hoje:** Adicionar sliders HSL completos
3. **Amanhã:** Implementar culling
4. **Esta semana:** Auto-straighten e feedback

---

## 💡 Notas Importantes

### Servidor Simplificado V2
O `services/server.py` foi simplificado e agora:
- ✅ Usa apenas AI_PREDICTOR V2
- ✅ Não depende do ENGINE antigo
- ✅ Resposta mais simples e rápida
- ✅ Código mais limpo

### Compatibilidade
O plugin Common_V2.lua foi desenhado para ser compatível com o servidor V2, mas precisa da porta correta!

### Re-treino
Após adicionar novos sliders HSL:
- **Obrigatório:** Re-extrair dataset com novos sliders
- **Obrigatório:** Re-treinar modelos
- **Tempo estimado:** 2-3h (depending on dataset size)
