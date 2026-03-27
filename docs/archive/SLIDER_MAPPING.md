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
| **33**| `green_hue`                       | `HueAdjustmentGreen`                    | **HSL (Cores Primárias - NOVO)**|
| **34**| `green_saturation`                | `SaturationAdjustmentGreen`             | **HSL (Cores Primárias - NOVO)**|
| **35**| `green_luminance`                 | `LuminanceAdjustmentGreen`              | **HSL (Cores Primárias - NOVO)**|
| **36**| `blue_hue`                        | `HueAdjustmentBlue`                     | **HSL (Cores Primárias - NOVO)**|
| **37**| `blue_saturation`                 | `SaturationAdjustmentBlue`              | **HSL (Cores Primárias - NOVO)**|
| **38**| `blue_luminance`                  | `LuminanceAdjustmentBlue`               | **HSL (Cores Primárias - NOVO)**|

## Importância da Sincronização

*   **Backend Python (`services/inference.py`):** A lista `ALL_SLIDER_NAMES` define a ordem e os nomes dos valores que o modelo de inferência irá prever.
*   **Plugin Lua (`NSP-Plugin.lrplugin/Common.lua`):**
    *   `Common.ALL_SLIDER_NAMES`: Usada para construir o vetor de entrada para o backend Python (na função `collect_develop_vector`). Deve conter os nomes `snake_case` na ordem exata do Python.
    *   `Common.DEVELOP_MAPPING`: Usada para mapear os nomes `snake_case` recebidos do Python para as `lr_key` do Lightroom ao aplicar os ajustes (na função `build_develop_settings`).

Qualquer alteração na lista `ALL_SLIDER_NAMES` no Python deve ser refletida de forma correspondente no ficheiro `Common.lua` para evitar erros de comunicação e aplicação de ajustes.

## Próximos Passos

1.  **Validação dos `lr_key`:** É fundamental testar exaustivamente se as `lr_key` assumidas para os novos sliders são de facto as corretas e funcionam como esperado no Lightroom.
2.  **Recolha de Dados de Treino:** Iniciar a recolha de dados de treino de alta qualidade para os 16 novos sliders, conforme a estratégia faseada.
3.  **Re-treino do Modelo:** Re-treinar o modelo de Rede Neural com a nova dimensão de saída (38 sliders).
4.  **Atualização da UI/UX:** Adaptar a interface do utilizador (Tauri/Gradio) e o plugin do Lightroom para exibir e permitir a interação com os novos sliders.
