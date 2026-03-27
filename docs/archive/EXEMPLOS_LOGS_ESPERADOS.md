# Exemplos de Logs Esperados - NSP Plugin

## LOG COMPLETO: Execução Bem-Sucedida

Este é um exemplo de como os logs devem aparecer quando tudo funciona corretamente.

---

## 1. TESTE HARDCODED - SUCESSO

**Ficheiro:** `NSPPlugin.TestApplySettings.log`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 TESTE DE APLICAÇÃO DE SETTINGS HARDCODED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Foto: DSC_1234.NEF

A aplicar settings HARDCODED:
   Exposure2012 = 2.0
   Contrast2012 = 50
   Temperature = 8000
   Saturation = 50
   HueAdjustmentRed = 50
   SaturationAdjustmentRed = 50

🚀 A chamar photo:applyDevelopSettings()...
✅ photo:applyDevelopSettings() executado!

🔍 Verificação pós-aplicação:
   ✅ Exposure2012                | Esperado: 2.0      | Atual: 2.0
   ✅ Contrast2012                | Esperado: 50       | Atual: 50
   ✅ Temperature                 | Esperado: 8000     | Atual: 8000
   ✅ Saturation                  | Esperado: 50       | Atual: 50
   ✅ HueAdjustmentRed            | Esperado: 50       | Atual: 50
   ✅ SaturationAdjustmentRed     | Esperado: 50       | Atual: 50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ TESTE PASSOU: Todos os settings foram aplicados corretamente!
```

---

## 2. PREDIÇÃO AI V2 - SUCESSO COMPLETO

**Ficheiro:** `NSPPlugin.ApplyAIPresetV2.log`

### 2.1. Início e Verificação do Servidor

```
🚀 applyAIPresetV2: INÍCIO
🎨 A obter predição AI para: IMG_5678.CR2
```

### 2.2. Predição Recebida do Servidor

**Ficheiro:** `NSPPlugin.CommonV2.log`

```
🔮 A fazer predição V2 para: /Users/nelson/Photos/IMG_5678.CR2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPOSTA COMPLETA DO SERVIDOR /predict:
   → Tipo de response: table
   → Chaves presentes na resposta:
      • model (string)
      • sliders (table)
      • preset_id (number)
      • preset_confidence (number)
      • prediction_id (number)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Predição V2 recebida:
   → Model: V2_AI_Predictor
   → Preset ID: 2
   → Confiança: 0.87
   → Prediction DB ID: 456
   → Número de sliders: 38

   → Primeiros 5 sliders recebidos:
      • exposure = 1.2
      • contrast = 15
      • highlights = -30
      • shadows = 25
      • temp = 5800
```

### 2.3. Mapeamento de Sliders

**Ficheiro:** `NSPPlugin.CommonV2.log`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
build_develop_settings: ENTRADA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   → Tipo de sliders_dict: table

━━━ SLIDERS RECEBIDOS DO SERVIDOR (ANTES DO MAPEAMENTO) ━━━
   [01] Python: exposure                   = 1.2
   [02] Python: contrast                   = 15
   [03] Python: highlights                 = -30
   [04] Python: shadows                    = 25
   [05] Python: whites                     = -10
   [06] Python: blacks                     = -15
   [07] Python: texture                    = 5
   [08] Python: clarity                    = 10
   [09] Python: dehaze                     = 0
   [10] Python: vibrance                   = 15
   [11] Python: saturation                 = 10
   [12] Python: temp                       = 5800
   [13] Python: tint                       = 5
   [14] Python: sharpen_amount             = 40
   [15] Python: sharpen_radius             = 1.0
   [16] Python: sharpen_detail             = 25
   [17] Python: sharpen_masking            = 0
   [18] Python: nr_luminance               = 20
   [19] Python: nr_detail                  = 50
   [20] Python: nr_color                   = 25
   [21] Python: vignette                   = -15
   [22] Python: grain                      = 0
   [23] Python: shadow_tint                = 0
   [24] Python: red_primary_hue            = 0
   [25] Python: red_primary_saturation     = 0
   [26] Python: green_primary_hue          = 0
   [27] Python: green_primary_saturation   = 0
   [28] Python: blue_primary_hue           = 0
   [29] Python: blue_primary_saturation    = 0
   [30] Python: red_hue                    = -10
   [31] Python: red_saturation             = 20
   [32] Python: red_luminance              = 5
   [33] Python: green_hue                  = 0
   [34] Python: green_saturation           = 0
   [35] Python: green_luminance            = 0
   [36] Python: blue_hue                   = 10
   [37] Python: blue_saturation            = -5
   [38] Python: blue_luminance             = 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ✅ Mapeado: exposure → Exposure2012 = 1.2
   ✅ Mapeado: contrast → Contrast2012 = 15
   ✅ Mapeado: highlights → Highlights2012 = -30
   ✅ Mapeado: shadows → Shadows2012 = 25
   ✅ Mapeado: whites → Whites2012 = -10
   ✅ Mapeado: blacks → Blacks2012 = -15
   ✅ Mapeado: texture → Texture = 5
   ✅ Mapeado: clarity → Clarity2012 = 10
   ✅ Mapeado: dehaze → Dehaze = 0
   ✅ Mapeado: vibrance → Vibrance = 15
   ✅ Mapeado: saturation → Saturation = 10
   ✅ Mapeado: temp → Temperature = 5800
   ✅ Mapeado: tint → Tint = 5
   ✅ Mapeado: sharpen_amount → SharpenAmount = 40
   ✅ Mapeado: sharpen_radius → SharpenRadius = 1.0
   ✅ Mapeado: sharpen_detail → SharpenDetail = 25
   ✅ Mapeado: sharpen_masking → SharpenEdgeMasking = 0
   ✅ Mapeado: nr_luminance → LuminanceNoiseReduction = 20
   ✅ Mapeado: nr_detail → LuminanceNoiseReductionDetail = 50
   ✅ Mapeado: nr_color → ColorNoiseReduction = 25
   ✅ Mapeado: vignette → PostCropVignetteAmount = -15
   ✅ Mapeado: grain → GrainAmount = 0
   ✅ Mapeado: shadow_tint → ShadowTint = 0
   ✅ Mapeado: red_primary_hue → RedHue = 0
   ✅ Mapeado: red_primary_saturation → RedSaturation = 0
   ✅ Mapeado: green_primary_hue → GreenHue = 0
   ✅ Mapeado: green_primary_saturation → GreenSaturation = 0
   ✅ Mapeado: blue_primary_hue → BlueHue = 0
   ✅ Mapeado: blue_primary_saturation → BlueSaturation = 0
   ✅ Mapeado: red_hue → HueAdjustmentRed = -10
   ✅ Mapeado: red_saturation → SaturationAdjustmentRed = 20
   ✅ Mapeado: red_luminance → LuminanceAdjustmentRed = 5
   ✅ Mapeado: green_hue → HueAdjustmentGreen = 0
   ✅ Mapeado: green_saturation → SaturationAdjustmentGreen = 0
   ✅ Mapeado: green_luminance → LuminanceAdjustmentGreen = 0
   ✅ Mapeado: blue_hue → HueAdjustmentBlue = 10
   ✅ Mapeado: blue_saturation → SaturationAdjustmentBlue = -5
   ✅ Mapeado: blue_luminance → LuminanceAdjustmentBlue = 0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
build_develop_settings: SAÍDA
   → Total sliders recebidos: 38
   → Total sliders mapeados: 38
   → Total sliders NÃO mapeados: 0
✅ Todos os sliders foram mapeados com sucesso!
   ✅ Settings construído com sucesso: 38 entradas

━━━ DEVELOP SETTINGS FINAIS (PARA APLICAR AO LIGHTROOM) ━━━
   [01] Lightroom: Exposure2012                           = 1.2
   [02] Lightroom: Contrast2012                           = 15
   [03] Lightroom: Highlights2012                         = -30
   [04] Lightroom: Shadows2012                            = 25
   [05] Lightroom: Whites2012                             = -10
   [06] Lightroom: Blacks2012                             = -15
   [07] Lightroom: Texture                                = 5
   [08] Lightroom: Clarity2012                            = 10
   [09] Lightroom: Dehaze                                 = 0
   [10] Lightroom: Vibrance                               = 15
   [11] Lightroom: Saturation                             = 10
   [12] Lightroom: Temperature                            = 5800
   [13] Lightroom: Tint                                   = 5
   [14] Lightroom: SharpenAmount                          = 40
   [15] Lightroom: SharpenRadius                          = 1.0
   [16] Lightroom: SharpenDetail                          = 25
   [17] Lightroom: SharpenEdgeMasking                     = 0
   [18] Lightroom: LuminanceNoiseReduction                = 20
   [19] Lightroom: LuminanceNoiseReductionDetail          = 50
   [20] Lightroom: ColorNoiseReduction                    = 25
   [21] Lightroom: PostCropVignetteAmount                 = -15
   [22] Lightroom: GrainAmount                            = 0
   [23] Lightroom: ShadowTint                             = 0
   [24] Lightroom: RedHue                                 = 0
   [25] Lightroom: RedSaturation                          = 0
   [26] Lightroom: GreenHue                               = 0
   [27] Lightroom: GreenSaturation                        = 0
   [28] Lightroom: BlueHue                                = 0
   [29] Lightroom: BlueSaturation                         = 0
   [30] Lightroom: HueAdjustmentRed                       = -10
   [31] Lightroom: SaturationAdjustmentRed                = 20
   [32] Lightroom: LuminanceAdjustmentRed                 = 5
   [33] Lightroom: HueAdjustmentGreen                     = 0
   [34] Lightroom: SaturationAdjustmentGreen              = 0
   [35] Lightroom: LuminanceAdjustmentGreen               = 0
   [36] Lightroom: HueAdjustmentBlue                      = 10
   [37] Lightroom: SaturationAdjustmentBlue               = -5
   [38] Lightroom: LuminanceAdjustmentBlue                = 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 2.4. Aplicação dos Settings

**Ficheiro:** `NSPPlugin.ApplyAIPresetV2.log`

```
🔧 A construir develop settings a partir dos sliders recebidos...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 PRESTES A APLICAR DEVELOP SETTINGS À FOTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Total de settings a aplicar: 38

📋 LISTA COMPLETA DE TODOS OS SETTINGS:
   [01] Exposure2012                        = 1.2
   [02] Contrast2012                        = 15
   [03] Highlights2012                      = -30
   [04] Shadows2012                         = 25
   [05] Whites2012                          = -10
   [06] Blacks2012                          = -15
   [07] Texture                             = 5
   [08] Clarity2012                         = 10
   [09] Dehaze                              = 0
   [10] Vibrance                            = 15
   [11] Saturation                          = 10
   [12] Temperature                         = 5800
   [13] Tint                                = 5
   [14] SharpenAmount                       = 40
   [15] SharpenRadius                       = 1.0
   [16] SharpenDetail                       = 25
   [17] SharpenEdgeMasking                  = 0
   [18] LuminanceNoiseReduction             = 20
   [19] LuminanceNoiseReductionDetail       = 50
   [20] ColorNoiseReduction                 = 25
   [21] PostCropVignetteAmount              = -15
   [22] GrainAmount                         = 0
   [23] ShadowTint                          = 0
   [24] RedHue                              = 0
   [25] RedSaturation                       = 0
   [26] GreenHue                            = 0
   [27] GreenSaturation                     = 0
   [28] BlueHue                             = 0
   [29] BlueSaturation                      = 0
   [30] HueAdjustmentRed                    = -10
   [31] SaturationAdjustmentRed             = 20
   [32] LuminanceAdjustmentRed              = 5
   [33] HueAdjustmentGreen                  = 0
   [34] SaturationAdjustmentGreen           = 0
   [35] LuminanceAdjustmentGreen            = 0
   [36] HueAdjustmentBlue                   = 10
   [37] SaturationAdjustmentBlue            = -5
   [38] LuminanceAdjustmentBlue             = 0

🚀 A chamar photo:applyDevelopSettings() agora...
✅ photo:applyDevelopSettings() executado com sucesso!
```

### 2.5. Verificação Pós-Aplicação

```
🔍 VERIFICAÇÃO PÓS-APLICAÇÃO:
   ✅ Exposure2012                | Esperado: 1.2      | Atual: 1.2
   ✅ Contrast2012                | Esperado: 15       | Atual: 15
   ✅ Temperature                 | Esperado: 5800     | Atual: 5800
   ✅ Saturation                  | Esperado: 10       | Atual: 10
   ✅ HueAdjustmentRed            | Esperado: -10      | Atual: -10
   ✅ SaturationAdjustmentRed     | Esperado: 20       | Atual: 20
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Preset AI aplicado com sucesso!
```

---

## 3. EXEMPLO: Sliders Não Mapeados (PROBLEMA)

Se o servidor retornar sliders que não estão no `DEVELOP_MAPPING`:

**Ficheiro:** `NSPPlugin.CommonV2.log`

```
━━━ SLIDERS RECEBIDOS DO SERVIDOR (ANTES DO MAPEAMENTO) ━━━
   [01] Python: exposure                   = 1.2
   [02] Python: contrast                   = 15
   ...
   [36] Python: blue_luminance             = 0
   [37] Python: orange_hue                 = 15      ⚠️  NOVO!
   [38] Python: orange_saturation          = 20      ⚠️  NOVO!
   [39] Python: orange_luminance           = -5      ⚠️  NOVO!
   [40] Python: yellow_hue                 = 10      ⚠️  NOVO!
   [41] Python: yellow_saturation          = 15      ⚠️  NOVO!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ✅ Mapeado: exposure → Exposure2012 = 1.2
   ✅ Mapeado: contrast → Contrast2012 = 15
   ...
   ⚠️  Slider não mapeado: orange_hue = 15
   ⚠️  Slider não mapeado: orange_saturation = 20
   ⚠️  Slider não mapeado: orange_luminance = -5
   ⚠️  Slider não mapeado: yellow_hue = 10
   ⚠️  Slider não mapeado: yellow_saturation = 15

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
build_develop_settings: SAÍDA
   → Total sliders recebidos: 41
   → Total sliders mapeados: 36
   → Total sliders NÃO mapeados: 5

⚠️  ATENÇÃO: 5 sliders NÃO foram mapeados:
      [1] orange_hue
      [2] orange_saturation
      [3] orange_luminance
      [4] yellow_hue
      [5] yellow_saturation
   → Estes sliders foram IGNORADOS e NÃO serão aplicados!
```

**Ação necessária:** Adicionar estes sliders ao `DEVELOP_MAPPING` em `Common_V2.lua`:

```lua
-- Adicionar ao DEVELOP_MAPPING:
{lr_key = "HueAdjustmentOrange", python_name = "orange_hue", display_name = "HSL Laranja Matiz", min = -100, max = 100},
{lr_key = "SaturationAdjustmentOrange", python_name = "orange_saturation", display_name = "HSL Laranja Sat.", min = -100, max = 100},
{lr_key = "LuminanceAdjustmentOrange", python_name = "orange_luminance", display_name = "HSL Laranja Lum.", min = -100, max = 100},
{lr_key = "HueAdjustmentYellow", python_name = "yellow_hue", display_name = "HSL Amarelo Matiz", min = -100, max = 100},
{lr_key = "SaturationAdjustmentYellow", python_name = "yellow_saturation", display_name = "HSL Amarelo Sat.", min = -100, max = 100},
```

---

## 4. EXEMPLO: Valores Não Aplicados (PROBLEMA)

Se `applyDevelopSettings()` não aplicar os valores:

**Ficheiro:** `NSPPlugin.ApplyAIPresetV2.log`

```
🚀 A chamar photo:applyDevelopSettings() agora...
✅ photo:applyDevelopSettings() executado com sucesso!

🔍 VERIFICAÇÃO PÓS-APLICAÇÃO:
   ❌ Exposure2012                | Esperado: 1.2      | Atual: 0.0
   ❌ Contrast2012                | Esperado: 15       | Atual: 0
   ❌ Temperature                 | Esperado: 5800     | Atual: 5500
   ❌ Saturation                  | Esperado: 10       | Atual: 0
   ❌ HueAdjustmentRed            | Esperado: -10      | Atual: 0
   ❌ SaturationAdjustmentRed     | Esperado: 20       | Atual: 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Diagnóstico:** Settings NÃO foram aplicados!

**Possíveis causas:**
1. Foto é virtual copy
2. Foto está read-only
3. Tipo de ficheiro não suportado
4. Bug no Lightroom SDK
5. Permissões do plugin

**Solução:**
1. Executar teste hardcoded para isolar problema
2. Tentar com outra foto
3. Verificar tipo de ficheiro
4. Recarregar plugin

---

## 5. EXEMPLO: Settings Vazios (PROBLEMA CRÍTICO)

Se `build_develop_settings()` retornar vazio:

**Ficheiro:** `NSPPlugin.CommonV2.log`

```
━━━ SLIDERS RECEBIDOS DO SERVIDOR (ANTES DO MAPEAMENTO) ━━━
   [01] Python: exp                        = 1.2      ⚠️  NOME ERRADO!
   [02] Python: cont                       = 15       ⚠️  NOME ERRADO!
   [03] Python: high                       = -30      ⚠️  NOME ERRADO!
   ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ⚠️  Slider não mapeado: exp = 1.2
   ⚠️  Slider não mapeado: cont = 15
   ⚠️  Slider não mapeado: high = -30
   ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
build_develop_settings: SAÍDA
   → Total sliders recebidos: 38
   → Total sliders mapeados: 0
   → Total sliders NÃO mapeados: 38

❌ CRÍTICO: Nenhum slider foi mapeado! settings está VAZIO!

⚠️  ATENÇÃO: 38 sliders NÃO foram mapeados:
      [1] exp
      [2] cont
      [3] high
      ...
   → Estes sliders foram IGNORADOS e NÃO serão aplicados!
```

**Diagnóstico:** Servidor está a retornar nomes de sliders ERRADOS!

**Solução:** Verificar servidor Python:
- Nomes corretos: `exposure`, `contrast`, `highlights`
- Nomes errados: `exp`, `cont`, `high`

---

## RESUMO: O que procurar nos logs

### ✅ Logs de SUCESSO (tudo a funcionar):

```
✅ Predição recebida com sucesso
✅ Número de sliders recebidos: 38
✅ Total sliders mapeados: 38
✅ Total sliders NÃO mapeados: 0
✅ Todos os sliders foram mapeados com sucesso!
✅ Settings construído com sucesso: 38 entradas
✅ photo:applyDevelopSettings() executado com sucesso!
✅ [verificação] Todos os settings com ✅
```

### ⚠️ Logs de AVISO (alguns sliders não mapeados):

```
⚠️  ATENÇÃO: 5 sliders NÃO foram mapeados:
      [1] orange_hue
      [2] orange_saturation
      ...
   → Estes sliders foram IGNORADOS e NÃO serão aplicados!
```

**Ação:** Adicionar mapeamentos em `Common_V2.lua`

### ❌ Logs de ERRO (nada aplicado):

```
❌ CRÍTICO: Nenhum slider foi mapeado! settings está VAZIO!
❌ [verificação] Todos os settings com ❌
❌ TESTE FALHOU: Alguns settings NÃO foram aplicados!
```

**Ação:** Investigar causa (servidor, nomes, SDK, permissões)

---

**Com estes exemplos, consegue facilmente comparar os seus logs e identificar problemas!**
