# Parâmetros Lightroom Suportados

**Versão:** 2.0
**Total de Parâmetros:** 60 (mapeados)
**Data:** 24 Novembro 2025

---

## Visão Geral

O NSP Plugin suporta atualmente **60 parâmetros do Adobe Lightroom Classic**, cobrindo as principais áreas de ajuste fotográfico.

---

## Parâmetros Mapeados

### 1. Basic (6 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Exposição | `Exposure2012` | `exposure` | -5.0 a +5.0 |
| Contraste | `Contrast2012` | `contrast` | -100 a +100 |
| Destaques | `Highlights2012` | `highlights` | -100 a +100 |
| Sombras | `Shadows2012` | `shadows` | -100 a +100 |
| Brancos | `Whites2012` | `whites` | -100 a +100 |
| Pretos | `Blacks2012` | `blacks` | -100 a +100 |

### 2. Presence (5 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Textura | `Texture` | `texture` | -100 a +100 |
| Claridade | `Clarity2012` | `clarity` | -100 a +100 |
| Desfazer Neblina | `Dehaze` | `dehaze` | -100 a +100 |
| Vibração | `Vibrance` | `vibrance` | -100 a +100 |
| Saturação | `Saturation` | `saturation` | -100 a +100 |

### 3. White Balance (2 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Temperatura | `Temperature` | `temp` | 2000 a 50000 |
| Matiz | `Tint` | `tint` | -150 a +150 |

### 4. Sharpening (4 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Nitidez | `SharpenAmount` | `sharpen_amount` | 0 a 150 |
| Raio | `SharpenRadius` | `sharpen_radius` | 0.5 a 3.0 |
| Detalhe | `SharpenDetail` | `sharpen_detail` | 0 a 100 |
| Máscara | `SharpenEdgeMasking` | `sharpen_masking` | 0 a 100 |

### 5. Noise Reduction (3 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Luminância | `LuminanceNoiseReduction` | `nr_luminance` | 0 a 100 |
| Detalhe | `LuminanceNoiseReductionDetail` | `nr_detail` | 0 a 100 |
| Cor | `ColorNoiseReduction` | `nr_color` | 0 a 100 |

### 6. Effects (2 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Vinheta | `PostCropVignetteAmount` | `vignette` | -100 a +100 |
| Grão | `GrainAmount` | `grain` | 0 a 100 |

### 7. Calibration (7 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Matiz Sombras | `ShadowTint` | `shadow_tint` | -100 a +100 |
| Matiz Vermelho | `RedHue` | `red_primary_hue` | -100 a +100 |
| Sat. Vermelho | `RedSaturation` | `red_primary_saturation` | -100 a +100 |
| Matiz Verde | `GreenHue` | `green_primary_hue` | -100 a +100 |
| Sat. Verde | `GreenSaturation` | `green_primary_saturation` | -100 a +100 |
| Matiz Azul | `BlueHue` | `blue_primary_hue` | -100 a +100 |
| Sat. Azul | `BlueSaturation` | `blue_primary_saturation` | -100 a +100 |

### 8. HSL Completo (24 parâmetros)

8 cores × 3 sliders (Hue, Saturation, Luminance) = 24 parâmetros

**Cores:** Red, Orange, Yellow, Green, Aqua, Blue, Purple, Magenta

| Cor | Hue Key | Saturation Key | Luminance Key |
|-----|---------|----------------|---------------|
| Red | `HueAdjustmentRed` | `SaturationAdjustmentRed` | `LuminanceAdjustmentRed` |
| Orange | `HueAdjustmentOrange` | `SaturationAdjustmentOrange` | `LuminanceAdjustmentOrange` |
| Yellow | `HueAdjustmentYellow` | `SaturationAdjustmentYellow` | `LuminanceAdjustmentYellow` |
| Green | `HueAdjustmentGreen` | `SaturationAdjustmentGreen` | `LuminanceAdjustmentGreen` |
| Aqua | `HueAdjustmentAqua` | `SaturationAdjustmentAqua` | `LuminanceAdjustmentAqua` |
| Blue | `HueAdjustmentBlue` | `SaturationAdjustmentBlue` | `LuminanceAdjustmentBlue` |
| Purple | `HueAdjustmentPurple` | `SaturationAdjustmentPurple` | `LuminanceAdjustmentPurple` |
| Magenta | `HueAdjustmentMagenta` | `SaturationAdjustmentMagenta` | `LuminanceAdjustmentMagenta` |

Todos com range: -100 a +100

### 9. Split Toning (5 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Highlights Hue | `SplitToningHighlightHue` | `split_highlight_hue` | 0 a 360 |
| Highlights Sat. | `SplitToningHighlightSaturation` | `split_highlight_saturation` | 0 a 100 |
| Shadows Hue | `SplitToningShadowHue` | `split_shadow_hue` | 0 a 360 |
| Shadows Sat. | `SplitToningShadowSaturation` | `split_shadow_saturation` | 0 a 100 |
| Balance | `SplitToningBalance` | `split_balance` | -100 a +100 |

### 10. Transform/Upright (2 parâmetros)

| Parâmetro | Lightroom Key | Python Name | Range |
|-----------|---------------|-------------|-------|
| Upright Version | `UprightVersion` | `upright_version` | 1 a 6 |
| Upright Mode | `UprightTransform` | `upright_mode` | 0 a 5 |

**Upright Modes:**
- 0 = Off
- 1 = Auto
- 2 = Level
- 3 = Vertical
- 4 = Full
- 5 = Guided

---

## Total: 60 Parâmetros

| Categoria | Quantidade |
|-----------|------------|
| Basic | 6 |
| Presence | 5 |
| White Balance | 2 |
| Sharpening | 4 |
| Noise Reduction | 3 |
| Effects | 2 |
| Calibration | 7 |
| HSL | 24 |
| Split Toning | 5 |
| Transform | 2 |
| **TOTAL** | **60** |

---

## Parâmetros Ainda Não Suportados

### Tone Curve

O Lightroom tem uma curva de tom com múltiplos pontos de controle:
- `ToneCurvePV2012` (array de pontos)
- `ToneCurvePV2012Red` (curva vermelha)
- `ToneCurvePV2012Green` (curva verde)
- `ToneCurvePV2012Blue` (curva azul)
- `ParametricShadows`, `ParametricDarks`, `ParametricLights`, `ParametricHighlights`
- `ParametricShadowSplit`, `ParametricMidtoneSplit`, `ParametricHighlightSplit`

**Complexidade:** Alta (arrays, curvas não lineares)

### Lens Corrections

- `LensProfileEnable`
- `LensManualDistortionAmount`
- `PerspectiveVertical`, `PerspectiveHorizontal`
- `PerspectiveRotate`, `PerspectiveScale`
- `ChromaticAberrationR`, `ChromaticAberrationB`
- `VignetteAmount` (lens correction vignette)

**Total estimado:** ~15 parâmetros

### Effects Adicionais

- `PostCropVignetteStyle`
- `PostCropVignetteFeather`, `PostCropVignetteRoundness`
- `PostCropVignetteMidpoint`, `PostCropVignetteHighlightContrast`
- `GrainSize`, `GrainFrequency`

**Total estimado:** ~7 parâmetros

### Color Grading (LR 10+)

- `ColorGradeMidtoneHue`, `ColorGradeMidtoneSat`, `ColorGradeMidtoneLum`
- `ColorGradeShadowLum`, `ColorGradeHighlightLum`
- `ColorGradeBlending`, `ColorGradeGlobalHue`
- E mais ~20 parâmetros de color grading

**Total estimado:** ~25 parâmetros

### Outros

- `ProcessVersion` (2012, 2010, 2003)
- `WhiteBalance` (As Shot, Auto, Custom, etc.)
- `CropTop`, `CropLeft`, `CropBottom`, `CropRight`, `CropAngle`
- `HasCrop`, `HasSettings`
- E mais ~10 parâmetros menores

**Total estimado:** ~15 parâmetros

---

## Total de Parâmetros Lightroom

| Status | Quantidade |
|--------|------------|
| **Suportados atualmente** | **60** |
| Tone Curve | ~10 |
| Lens Corrections | ~15 |
| Effects Adicionais | ~7 |
| Color Grading | ~25 |
| Outros | ~15 |
| **TOTAL ESTIMADO LIGHTROOM** | **~130 parâmetros** |

---

## Como Adicionar Novos Parâmetros

### 1. Identificar o Parâmetro no Lightroom SDK

Consultar a documentação oficial do Lightroom SDK:
- [Lightroom SDK Documentation](https://helpx.adobe.com/lightroom/sdk.html)
- Verificar `LrDevelopPreset` e `LrPhoto:getDevelopSettings()`

### 2. Adicionar ao Mapeamento

Editar `NSP-Plugin.lrplugin/Common_V2.lua`:

```lua
CommonV2.DEVELOP_MAPPING = {
    -- ... parâmetros existentes ...

    -- Novo parâmetro
    {
        lr_key = "NovoParametroLightroom",
        python_name = "novo_parametro_python",
        display_name = "Nome Amigável",
        min = valor_minimo,
        max = valor_maximo
    },
}
```

### 3. Atualizar Modelo ML

O modelo de refinamento precisa ser re-treinado com o novo número de outputs:

```python
# Em train/train_models_v2.py
NUM_OUTPUTS = 61  # Era 60, agora 61

# Retreinar modelo
python train/train_models_v2.py
```

### 4. Atualizar Dataset

Extrair novos parâmetros dos catálogos Lightroom:

```python
# Em tools/extract_dataset.py
# Adicionar novo parâmetro à lista de features
```

### 5. Testar

```lua
-- No Lightroom
File > Plug-in Extras > 🧪 TESTE APPLY SETTINGS
```

---

## Roadmap de Expansão

### Curto Prazo (v2.1)

- [ ] Adicionar Tone Curve parametric (~7 parâmetros)
- [ ] Adicionar Lens Corrections básicas (~5 parâmetros)
- [ ] **Total:** 72 parâmetros

### Médio Prazo (v2.5)

- [ ] Adicionar Color Grading completo (~25 parâmetros)
- [ ] Adicionar Effects adicionais (~7 parâmetros)
- [ ] **Total:** 104 parâmetros

### Longo Prazo (v3.0)

- [ ] Suporte completo a Tone Curve (arrays)
- [ ] Lens Corrections avançadas
- [ ] Todos os parâmetros restantes
- [ ] **Total:** ~130 parâmetros (100% cobertura)

---

## Priorização de Novos Parâmetros

### Alta Prioridade

1. **Tone Curve Parametric** - Muito usado por fotógrafos
2. **Color Grading** - Feature moderna do Lightroom
3. **Lens Corrections básicas** - Importante para qualidade

### Média Prioridade

4. **Effects adicionais** - Vignette styles, Grain size
5. **Crop** - Útil mas complexo de implementar
6. **Lens Corrections avançadas** - Menos usado

### Baixa Prioridade

7. **Process Version** - Raramente mudado manualmente
8. **Metadados técnicos** - Não afetam visual
9. **Parâmetros deprecated** - Versões antigas do Lightroom

---

## Limitações Conhecidas

### 1. Tone Curve

**Problema:** Tone Curve é representada como array de pontos (x, y), não como valores lineares.

**Solução Possível:**
- Usar pontos paramétricos (`ParametricShadows`, etc.) em vez da curva completa
- Treinar modelo para prever 7 pontos paramétricos
- Mais simples e suficiente para 90% dos casos

### 2. Crop

**Problema:** Crop depende de dimensões da imagem original.

**Solução Possível:**
- Usar valores relativos (percentagem) em vez de absolutos
- Treinar modelo com aspect ratio como input

### 3. Lens Corrections

**Problema:** Lens profiles são específicos para câmara/lente.

**Solução Possível:**
- Focar em distortion/vignette manual
- Usar metadata EXIF para identificar lens profile automaticamente

---

## Referências

- **Código Fonte:** `NSP-Plugin.lrplugin/Common_V2.lua` (linha 82-170)
- **Lightroom SDK:** https://helpx.adobe.com/lightroom/sdk.html
- **Develop Settings:** https://helpx.adobe.com/lightroom/sdk/develop-settings.html

---

**Última atualização:** 24 Novembro 2025
