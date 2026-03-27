# -*- coding: utf-8 -*-
import re

SLIDER_MAPPING_CONTENT = """
# Mapeamento de Sliders: Python (Backend) vs. Lightroom (Plugin Lua)

Este documento detalha o mapeamento dos nomes dos sliders utilizados no backend Python (modelo de inferência) e as suas chaves correspondentes no SDK do Lightroom, conforme implementado no plugin Lua. É crucial manter estas listas sincronizadas para garantir a correta comunicação e aplicação dos ajustes.

## Contexto

O sistema utiliza um conjunto de sliders para realizar ajustes assistidos em imagens. O backend Python, onde residem os modelos de inferência, prevê valores para estes sliders usando nomes em formato `snake_case`. O plugin Lua, que interage com o Lightroom, precisa de traduzir estes nomes para as chaves específicas (`lr_key`) que o SDK do Lightroom entende para aplicar os ajustes.

A lista `ALL_SLIDER_NAMES` no Python (`services/inference.py`) é a fonte de verdade para o conjunto de sliders que o modelo prevê. A tabela `Common.DEVELOP_MAPPING` e a lista `Common.ALL_SLIDER_NAMES` no Lua (`NSP-Plugin.lrplugin/Common.lua`) devem refletir esta lista Python em termos de conteúdo e ordem.

## Sliders Atualmente Suportados (Fase 1: 38 Sliders)

A seguinte tabela apresenta os 38 sliders atualmente suportados, incluindo os 22 originais e os 16 novos adicionados na Fase 1 (Calibração e HSL de Cores Primárias).

| Ordem | Nome Python (`snake_case`)        | Chave Lightroom SDK (`lr_key`)          | Categoria Lightroom           |
| :---- | :-------------------------------- | :-------------------------------------- | :---------------------------- |
| 1     | `exposure`                        | `Exposure2012`                          | Básico                        |
| 2     | `contrast`                        | `Contrast2012`                          | Básico                        |
| 3     | `highlights`                      | `Highlights2012`                        | Básico                        |
| 4     | `shadows`                         | `Shadows2012`                           | Básico                        |
| 5     | `whites`                          | `Whites2012`                            | Básico                        |
| 6     | `blacks`                          | `Blacks2012`                            | Básico                        |
| 7     | `texture`                         | `Texture`                               | Básico                        |
| 8     | `clarity`                         | `Clarity2012`                           | Básico                        |
| 9     | `dehaze`                          | `Dehaze`                                | Básico                        |
| 10    | `vibrance`                        | `Vibrance`                              | Básico                        |
| 11    | `saturation`                      | `Saturation`                            | Básico                        |
| 12    | `temp`                            | `Temperature`                           | Básico                        |
| 13    | `tint`                            | `Tint`                                  | Básico                        |
| 14    | `sharpen_amount`                  | `SharpenAmount`                         | Detalhe (Nitidez)             |
| 15    | `sharpen_radius`                  | `SharpenRadius`                         | Detalhe (Nitidez)             |
| 16    | `sharpen_detail`                  | `SharpenDetail`                         | Detalhe (Nitidez)             |
| 17    | `sharpen_masking`                 | `SharpenEdgeMasking`                    | Detalhe (Nitidez)             |
| 18    | `nr_luminance`                    | `LuminanceNoiseReduction`               | Detalhe (Redução de Ruído)    |
| 19    | `nr_detail`                       | `LuminanceNoiseReductionDetail`         | Detalhe (Redução de Ruído)    |
| 20    | `nr_color`                        | `ColorNoiseReduction`                   | Detalhe (Redução de Ruído)    |
| 21    | `vignette`                        | `PostCropVignetteAmount`                | Efeitos                       |
| 22    | `grain`                           | `GrainAmount`                           | Efeitos                       |
| **23**| `shadow_tint`                     | `ShadowTint`                            | **Calibração (NOVO)**         |
| **24**| `red_primary_hue`                 | `RedHue`                                | **Calibração (NOVO)**         |
| **25**| `red_primary_saturation`          | `RedSaturation`                         | **Calibração (NOVO)**         |
| **26**| `green_primary_hue`               | `GreenHue`                              | **Calibração (NOVO)**         |
| **27**| `green_primary_saturation`        | `GreenSaturation`                       | **Calibração (NOVO)**         |
| **28**| `blue_primary_hue`                | `BlueHue`                               | **Calibração (NOVO)**         |
| **29**| `blue_primary_saturation`         | `BlueSaturation`                        | **Calibração (NOVO)**         |
| **30**| `red_hue`                         | `HueAdjustmentRed`                      | **HSL (Cores Primárias - NOVO)**|
| **31**| `red_saturation`                  | `SaturationAdjustmentRed`               | **HSL (Cores Primárias - NOVO)**|
| **32**| `red_luminance`                   | `LuminanceAdjustmentRed`                | **HSL (Cores Primárias - NOVO)**|
| **33**| `green_hue`                       | `HueAdjustmentGreen`                      | **HSL (Cores Primárias - NOVO)**|
| **34**| `green_saturation`                | `SaturationAdjustmentGreen`               | **HSL (Cores Primárias - NOVO)**|
| **35**| `green_luminance`                 | `LuminanceAdjustmentGreen`              | **HSL (Cores Primárias - NOVO)**|
| **36**| `blue_hue`                        | `HueAdjustmentBlue`                     | **HSL (Cores Primárias - NOVO)**|
| **37**| `blue_saturation`                 | `SaturationAdjustmentBlue`              | **HSL (Cores Primárias - NOVO)**|
| **38**| `blue_luminance`                  | `LuminanceAdjustmentBlue`               | **HSL (Cores Primárias - NOVO)**|
| **59**| `upright_version`                 | `UprightVersion`                        | **Transform/Upright (NOVO)**    |
| **60**| `upright_mode`                    | `UprightTransform`                      | **Transform/Upright (NOVO)**    |
"""

def parse_slider_mapping(markdown_content: str):
    sliders = []
    lines = markdown_content.splitlines()
    
    in_table_data_section = False
    
    for line in lines:
        stripped_line = line.strip()
        
        # Detect the start of the table data section (after the header separator)
        if stripped_line.startswith("| :----"):
            in_table_data_section = True
            continue
        
        # If we are in the table data section and the line starts with '|'
        if in_table_data_section and stripped_line.startswith("|"):
            # Split the line by '|' and remove empty strings from the ends
            columns = [col.strip() for col in stripped_line.split('|') if col.strip()]
            
            # A valid data row should have 4 columns (Order, Python Name, LR Key, Category)
            if len(columns) == 4:
                # Extract Python Name and LR Key from backticks
                python_name_match = re.search(r"`([^`]+)`", columns[1])
                lr_key_match = re.search(r"`([^`]+)`", columns[2])
                
                if python_name_match and lr_key_match:
                    python_name = python_name_match.group(1).strip()
                    lr_key = lr_key_match.group(1).strip()
                    
                    raw_category = columns[3].strip()
                    category = raw_category.replace(" (NOVO)", "").replace("**", "").strip()
                    
                    # Infer min/max/step based on common Lightroom ranges
                    min_val, max_val, step_val = -100, 100, 1 # Default for most sliders
                    
                    if python_name == "exposure":
                        min_val, max_val, step_val = -5.0, 5.0, 0.05
                    elif python_name in ["contrast", "highlights", "shadows", "whites", "blacks", "texture", "clarity", "dehaze", "vibrance", "saturation", "shadow_tint"]:
                        min_val, max_val, step_val = -100, 100, 1
                    elif python_name == "temp":
                        min_val, max_val, step_val = 2000, 50000, 50
                    elif python_name == "tint":
                        min_val, max_val, step_val = -150, 150, 1
                    elif "sharpen" in python_name:
                        min_val, max_val, step_val = 0, 150, 1
                    elif "nr_" in python_name:
                        min_val, max_val, step_val = 0, 100, 1
                    elif python_name == "vignette":
                        min_val, max_val, step_val = -100, 100, 1
                    elif python_name == "grain":
                        min_val, max_val, step_val = 0, 100, 1
                    elif "hue" in python_name:
                        min_val, max_val, step_val = -180, 180, 1
                    elif "saturation" in python_name or "luminance" in python_name:
                        min_val, max_val, step_val = -100, 100, 1
                    elif python_name == "upright_version":
                        min_val, max_val, step_val = 1, 6, 1  # Versão do Upright
                    elif python_name == "upright_mode":
                        min_val, max_val, step_val = 0, 5, 1  # Modos: 0=Off, 1=Auto, 2=Level, 3=Vertical, 4=Full, 5=Guided

                    sliders.append({
                        "python_name": python_name,
                        "lr_key": lr_key,
                        "category": category,
                        "min": min_val,
                        "max": max_val,
                        "step": step_val
                    })
            # If we are in the table data section but the line doesn't match the expected column count,
            # it might be the end of the table data or a malformed line.
            # For now, we'll just ignore it and continue.
        elif in_table_data_section and not stripped_line.startswith("|"):
            # If we were in the table data section and now encounter a line not starting with '|',
            # it means we've exited the table.
            in_table_data_section = False
                
    return sliders

ALL_SLIDERS = parse_slider_mapping(SLIDER_MAPPING_CONTENT)

# Lista ordenada de todos os nomes de sliders (38 sliders)
# Esta é a ordem canónica usada pelo modelo e sistema de feedback
ALL_SLIDER_NAMES = [slider['python_name'] for slider in ALL_SLIDERS]

# Dicionário de ranges para validação
SLIDER_RANGES = {
    slider['python_name']: {
        'min': slider['min'],
        'max': slider['max'],
        'step': slider['step']
    }
    for slider in ALL_SLIDERS
}

# Mapeamento de índice para nome (para lookup rápido)
SLIDER_INDEX_TO_NAME = {i: name for i, name in enumerate(ALL_SLIDER_NAMES)}

# Mapeamento de nome para índice (para lookup rápido)
SLIDER_NAME_TO_INDEX = {name: i for i, name in enumerate(ALL_SLIDER_NAMES)}