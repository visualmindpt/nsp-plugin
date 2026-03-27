# 🔄 Workflow de Re-treino - NSP Plugin V2

**Versão:** 2.1 (58 Sliders)
**Data:** 13 de Novembro de 2025

---

## 📋 Visão Geral

O re-treino do NSP Plugin V2 segue um pipeline de **7 etapas principais**:

```
1. Extração      → 2. Identificação → 3. Features    → 4. Treino         → 5. Treino       → 6. Validação → 7. Deploy
   Lightroom        de Presets         Estatísticas    Classificador      Refinador         Modelos        Produção
   (XMP)            (Clustering)       + Deep          (4 presets)        (Deltas)          (Testes)       (Server)
```

---

## 🎯 Workflow Completo

### **FASE 1: Preparação do Dataset**

#### Passo 1.1: Configurar Catálogo Lightroom
```bash
# Localizar o teu catálogo Lightroom
# Exemplo: /Users/nelsonsilva/Pictures/Lightroom Catalog.lrcat
```

**Requisitos:**
- ✅ Catálogo com fotos editadas (develop settings aplicados)
- ✅ Pelo menos 100-200 fotos com rating >= 3
- ✅ Fotos representativas do teu estilo fotográfico
- ✅ Variedade de cenas (retratos, paisagens, etc.)

#### Passo 1.2: Editar Configurações de Treino
```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
nano train/train_models_v2.py  # ou usar editor de texto
```

**Configurar:**
```python
# Linha 30: Caminho do catálogo
_CATALOG_PATH = Path('/Users/SEU_NOME/Pictures/Lightroom Catalog.lrcat')

# Linha 37-38: Configurações
_NUM_PRESETS = 4      # Quantos "estilos base" tens?
_MIN_RATING = 3       # Apenas fotos com rating >= 3

# Linha 41-44: Parâmetros de treino
_CLASSIFIER_EPOCHS = 50    # Mais epochs = mais tempo, mais precisão
_REFINER_EPOCHS = 100
_BATCH_SIZE = 32           # Reduzir se tiveres pouca RAM
_PATIENCE = 7              # Early stopping
```

---

### **FASE 2: Extração de Dados do Lightroom**

#### Passo 2.1: Executar Extração
```bash
# Ativar ambiente virtual
source venv/bin/activate

# Opção A: Usar train_ui.py (interface interativa)
python train_ui.py

# Opção B: Script direto
python -c "
from train_models import extract_lightroom_data, set_training_configs
set_training_configs(
    catalog_path='/Users/SEU_NOME/Pictures/Lightroom Catalog.lrcat',
    num_presets=4,
    min_rating=3
)
dataset = extract_lightroom_data()
print(f'✅ Extraídas {len(dataset)} fotos')
"
```

**O Que Acontece:**
1. Conecta à base de dados SQLite do Lightroom
2. Extrai fotos com `rating >= 3`
3. Descomprime XMP (settings de edição)
4. Parseia **58 sliders** de cada foto:
   - Basic (6), Presence (5), WB (2)
   - Sharpening (4), NR (3), Effects (2)
   - Calibration (7), HSL (24), Split Toning (5)
5. Guarda em `data/lightroom_dataset.csv`

**Output Esperado:**
```
📊 Dataset extraído com 247 imagens.
Colunas: ['image_path', 'rating', 'exposure', 'contrast', ..., 'split_balance']
✅ Dataset guardado em: data/lightroom_dataset.csv
```

**Verificar Dataset:**
```bash
# Ver primeiras linhas
head -n 5 data/lightroom_dataset.csv

# Contar fotos
wc -l data/lightroom_dataset.csv

# Ver colunas (deve ser 58 sliders + image_path + rating = 60)
head -n 1 data/lightroom_dataset.csv | tr ',' '\n' | wc -l
```

---

### **FASE 3: Identificação de Presets Base (Clustering)**

#### Passo 3.1: Clustering K-Means

**O Que Acontece:**
1. Usa K-Means para agrupar fotos em **N presets** (default: 4)
2. Cada cluster = 1 "estilo fotográfico" base
3. Calcula centro de cada cluster (média dos 58 sliders)
4. Atribui cada foto ao preset mais próximo

**Exemplo de Presets Identificados:**
```
📋 Preset 1 (n=87 fotos): "Estilo Natural"
  exposure: +0.35
  contrast: +15
  highlights: -25
  shadows: +20
  hsl_orange_saturation: -10  # Tons de pele suaves
  split_highlight_hue: 50      # Warmth nas highlights

📋 Preset 2 (n=63 fotos): "Estilo Dramático"
  exposure: -0.15
  contrast: +40
  clarity: +30
  dehaze: +15
  vignette: -35
  hsl_blue_saturation: +20     # Céu intenso

📋 Preset 3 (n=54 fotos): "Estilo B&W"
  saturation: -100
  contrast: +25
  texture: +20
  ...

📋 Preset 4 (n=43 fotos): "Estilo Vintage"
  split_highlight_hue: 45
  split_shadow_hue: 220
  grain: +25
  ...
```

#### Passo 3.2: Cálculo de Deltas

**O Que Acontece:**
1. Para cada foto, calcula **Delta = Valor Final - Valor do Preset Base**
2. Deltas representam os ajustes finos que fazes DEPOIS do preset
3. Exemplo:
   ```
   Foto: IMG_1234.jpg
   Preset Base: "Estilo Natural" (exposure: +0.35)
   Valor Final na Foto: exposure: +0.80
   Delta calculado: +0.45  (o quanto ajustaste manualmente)
   ```

**Output:**
- `models/preset_centers.json` - Centros dos 4 presets
- `models/delta_columns.json` - Lista dos 58 parâmetros delta
- `data/lightroom_dataset.csv` (atualizado com colunas `preset_cluster` e `delta_*`)

---

### **FASE 4: Extração de Features das Imagens**

#### Passo 4.1: Features Estatísticas

**O Que Acontece:**
1. Para cada foto, calcula ~150 features estatísticas:
   - Histograma RGB (bins)
   - Média/Std de cada canal
   - Brightness, Contrast, Saturation
   - Edge density, Texture
2. Rápido: ~50ms por imagem

**Output:** `data/image_features.csv`

#### Passo 4.2: Deep Features (MobileNetV3)

**O Que Acontece:**
1. Passa cada foto pelo MobileNetV3 (pré-treinado ImageNet)
2. Extrai vetor de 512 dimensões (penúltima camada)
3. Features capturam conteúdo semântico (pessoas, paisagem, objetos, etc.)
4. Demorado: ~300-500ms por imagem
5. **Total estimado:** 200 fotos × 400ms = **~80 segundos**

**Output:** `data/deep_features.npy` (array NumPy)

**Monitorizar Progresso:**
```bash
# O script mostra progresso a cada 10 fotos:
Extraindo features estatísticas: 10/200
Extraindo features estatísticas: 20/200
...
Extraindo deep features: 10/200 (MobileNetV3)
Extraindo deep features: 20/200 (MobileNetV3)
...
✅ Features extraídas de 200/200 imagens
```

---

### **FASE 5: Treino do Classificador de Presets**

#### Passo 5.1: Preparar Dados

**Split Estratificado:**
```
Total: 200 fotos
├─ Train:      140 fotos (70%)
├─ Validation:  40 fotos (20%)
└─ Test:        20 fotos (10%)

(Stratified = proporção de presets mantida em cada split)
```

#### Passo 5.2: Arquitetura do Modelo

```
INPUT: Stat Features (150) + Deep Features (512)
       ↓                       ↓
  Stat Branch              Deep Branch
  (150→128→64)             (512→256→128)
       ↓                       ↓
       └───────────┬───────────┘
                   ↓
            Concatenate (192)
                   ↓
          Classification Head
            (192→128→4)
                   ↓
            Softmax → 4 Presets
```

#### Passo 5.3: Treino

**Configuração:**
- Loss: CrossEntropyLoss
- Optimizer: Adam (lr=0.001)
- Epochs: 50 (máximo)
- Early Stopping: Patience=7

**Output Durante Treino:**
```
Epoch 1/50 | Train Loss: 1.2345, Acc: 0.45 | Val Loss: 1.1234, Acc: 0.52
Epoch 2/50 | Train Loss: 0.9876, Acc: 0.58 | Val Loss: 0.8765, Acc: 0.65
  ✅ Novo melhor modelo (val_loss: 0.8765)
Epoch 3/50 | Train Loss: 0.7654, Acc: 0.71 | Val Loss: 0.7123, Acc: 0.75
  ✅ Novo melhor modelo (val_loss: 0.7123)
...
Epoch 15/50 | Train Loss: 0.1234, Acc: 0.96 | Val Loss: 0.2345, Acc: 0.92
⏹️  Early stopping após 15 epochs
```

**Tempo Estimado:** 5-15 minutos (depende de GPU/CPU)

**Output:**
- `models/best_preset_classifier.pth`
- Métricas de validação impressas

---

### **FASE 6: Treino do Refinador de Ajustes**

#### Passo 6.1: Arquitetura do Modelo

```
INPUT: Stat (150) + Deep (512) + Preset ID (one-hot: 4)
       ↓           ↓               ↓
  [Stat Branch][Deep Branch][Preset Embedding]
       ↓           ↓               ↓
       └───────────┴───────────────┘
                   ↓
            Concatenate (192+64)
                   ↓
          Regression Head
            (256→256→128→58)
                   ↓
            Output: 58 Deltas
```

#### Passo 6.2: Treino com Pesos Customizados

**Loss Function: Weighted MSE**
```python
# Cada slider tem um peso de importância
weights = {
    'exposure': 2.0,        # CRÍTICO
    'highlights': 1.8,      # IMPORTANTE
    'hsl_orange_sat': 1.3,  # Tons de pele
    'grain': 0.6,           # MODERADO
    ...
}

# Loss final considera pesos
loss = weighted_mse(predicted_deltas, true_deltas, weights)
```

**Configuração:**
- Loss: Weighted MSE
- Optimizer: Adam (lr=0.0005)
- Epochs: 100 (máximo)
- Early Stopping: Patience=7

**Output Durante Treino:**
```
Epoch 1/100 | Train Loss: 245.67, Val Loss: 234.56
Epoch 2/100 | Train Loss: 189.34, Val Loss: 178.92
  ✅ Novo melhor modelo (val_loss: 178.92)
...
Epoch 35/100 | Train Loss: 12.34, Val Loss: 15.67
⏹️  Early stopping após 35 epochs

📊 Análise de Deltas por Parâmetro:
  exposure        - MAE: 0.12 (excelente)
  contrast        - MAE: 3.45 (bom)
  hsl_orange_sat  - MAE: 2.87 (bom)
  ...
```

**Tempo Estimado:** 15-45 minutos (depende de GPU/CPU)

**Output:**
- `models/best_refinement_model.pth`
- Métricas detalhadas por slider

---

### **FASE 7: Normalização e Artefactos**

#### Passo 7.1: Guardar Scalers

**O Que São:**
- StandardScaler do scikit-learn
- Normaliza features para média=0, std=1
- Necessários para inferência (mesma normalização)

**Output:**
- `models/scaler_stat.pkl` - Para features estatísticas
- `models/scaler_deep.pkl` - Para deep features
- `models/scaler_deltas.pkl` - Para deltas

#### Passo 7.2: Verificar Artefactos Finais

```bash
ls -lh models/
```

**Ficheiros Esperados (Todos Necessários):**
```
best_preset_classifier.pth    (~15 MB)  ✅
best_refinement_model.pth     (~45 MB)  ✅
preset_centers.json           (~5 KB)   ✅
delta_columns.json            (~2 KB)   ✅
scaler_stat.pkl               (~50 KB)  ✅
scaler_deep.pkl               (~50 KB)  ✅
scaler_deltas.pkl             (~50 KB)  ✅
```

**Total:** ~60 MB (modelo completo com 58 sliders)

---

### **FASE 8: Validação dos Modelos**

#### Passo 8.1: Testes Automáticos

**O script de treino já faz:**
1. Avalia Classificador no test set
2. Mostra matriz de confusão dos presets
3. Avalia Refinador (MAE por slider)
4. Identifica sliders problemáticos

**Output:**
```
📊 CLASSIFICADOR - Test Set
Accuracy: 0.92 (92%)

Confusion Matrix:
           Pred 0  Pred 1  Pred 2  Pred 3
Actual 0      23       1       0       1
Actual 1       0      18       2       0
Actual 2       1       0      15       1
Actual 3       0       1       0      19

📊 REFINADOR - Test Set
MAE Médio: 8.45
MAE por categoria:
  Basic:       4.32 ⭐⭐⭐⭐⭐
  HSL:         9.87 ⭐⭐⭐⭐
  Split Tone: 12.34 ⭐⭐⭐
```

#### Passo 8.2: Teste Manual (Recomendado)

```bash
# Testar uma foto específica
python -c "
from services.ai_core.predictor import LightroomAIPredictor
from pathlib import Path

predictor = LightroomAIPredictor(
    classifier_path=Path('models/best_preset_classifier.pth'),
    refinement_path=Path('models/best_refinement_model.pth'),
    preset_centers=Path('models/preset_centers.json'),
    scaler_stat=Path('models/scaler_stat.pkl'),
    scaler_deep=Path('models/scaler_deep.pkl'),
    scaler_deltas=Path('models/scaler_deltas.pkl'),
    delta_columns=Path('models/delta_columns.json')
)

result = predictor.predict('/caminho/para/foto_teste.jpg')
print(f'Preset: {result[\"preset_id\"]} (conf: {result[\"preset_confidence\"]:.2f})')
print(f'Sliders: {len(result[\"sliders\"])} ajustes')
"
```

---

### **FASE 9: Deploy para Produção**

#### Passo 9.1: Backup Modelos Antigos

```bash
# Criar backup antes de substituir
mkdir -p models/backup_$(date +%Y%m%d)
cp models/*.pth models/*.pkl models/*.json models/backup_$(date +%Y%m%d)/
```

#### Passo 9.2: Reiniciar Servidor

```bash
# Parar servidor (Ctrl+C se estiver a correr)
# Reiniciar
python services/server.py
```

**Verificar:**
```bash
# Health check
curl http://localhost:5000/health

# Deve retornar:
{
  "status": "healthy",
  "model": "v2",
  "sliders": 58
}
```

#### Passo 9.3: Testar no Lightroom

1. **Recarregar Plugin:**
   - File > Plug-in Manager
   - Selecionar NSP Plugin
   - Clicar "Reload"

2. **Testar Foto Individual:**
   - Selecionar 1 foto
   - File > Plug-in Extras > AI Preset V2 - Foto Individual
   - Verificar preview
   - **Novo:** Devem aparecer ajustes de HSL e Split Toning
   - Aplicar e verificar resultado

3. **Testar Batch:**
   - Selecionar 5-10 fotos
   - File > Plug-in Extras > AI Preset V2 - Batch
   - Aguardar processamento
   - Verificar consistência

---

## 🔄 Workflow Completo em Comandos

```bash
# 1. PREPARAÇÃO
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate

# 2. CONFIGURAR (editar manualmente)
nano train/train_models_v2.py
# Atualizar _CATALOG_PATH linha 30

# 3. EXECUTAR TREINO COMPLETO (interface)
python train_ui.py

# OU executar programaticamente:
python << 'EOF'
from train_models import run_full_training_pipeline, set_training_configs

# Configurar
set_training_configs(
    catalog_path='/Users/SEU_NOME/Pictures/Lightroom Catalog.lrcat',
    num_presets=4,
    min_rating=3,
    classifier_epochs=50,
    refiner_epochs=100,
    batch_size=32,
    patience=7
)

# Executar pipeline completo
print("🚀 Iniciando pipeline de treino...")
run_full_training_pipeline()
print("✅ Treino concluído!")
EOF

# 4. BACKUP
mkdir -p models/backup_$(date +%Y%m%d_%H%M%S)
cp models/*.pth models/*.pkl models/*.json models/backup_*/

# 5. TESTAR MODELO
python -c "
from services.ai_core.predictor import LightroomAIPredictor
from pathlib import Path
predictor = LightroomAIPredictor(
    classifier_path=Path('models/best_preset_classifier.pth'),
    refinement_path=Path('models/best_refinement_model.pth'),
    preset_centers=Path('models/preset_centers.json'),
    scaler_stat=Path('models/scaler_stat.pkl'),
    scaler_deep=Path('models/scaler_deep.pkl'),
    scaler_deltas=Path('models/scaler_deltas.pkl'),
    delta_columns=Path('models/delta_columns.json')
)
result = predictor.predict('/caminho/teste.jpg')
print(f'✅ Predição OK: Preset {result[\"preset_id\"]}, {len(result[\"sliders\"])} sliders')
"

# 6. REINICIAR SERVIDOR
python services/server.py
```

---

## ⏱️ Tempo Estimado Total

| Fase | Tempo | GPU/CPU |
|------|-------|---------|
| **1. Extração Lightroom** | 1-3 min | CPU |
| **2. Clustering** | 10-30 seg | CPU |
| **3. Features Estatísticas** | 1-2 min | CPU |
| **4. Deep Features** | 5-15 min | GPU recomendado |
| **5. Treino Classificador** | 5-15 min | GPU recomendado |
| **6. Treino Refinador** | 15-45 min | GPU recomendado |
| **7. Validação** | 1-2 min | GPU/CPU |
| **TOTAL** | **30 min - 2 horas** | |

**Com GPU (MPS/CUDA):** ~30-60 minutos
**Sem GPU (CPU only):** ~1.5-2.5 horas

---

## 🐛 Troubleshooting Comum

### Erro: "Dataset vazio"
```bash
# Verificar:
python -c "
from services.ai_core.lightroom_extractor import LightroomCatalogExtractor
from pathlib import Path
extractor = LightroomCatalogExtractor(Path('/seu/catalogo.lrcat'))
df = extractor.extract_edits(min_rating=3)
print(f'Fotos encontradas: {len(df)}')
"
```
**Solução:** Reduzir `min_rating` ou editar mais fotos no Lightroom

### Erro: "CUDA out of memory" / "MPS out of memory"
**Solução:** Reduzir `batch_size` de 32 → 16 ou 8

### Erro: "Clusters com apenas 1 imagem"
**Solução:** Aumentar dataset (mais fotos) ou reduzir `num_presets`

### Aviso: "Val loss não diminui"
**Sintomas:** Early stopping após 7-10 epochs, loss alto
**Solução:**
- Dataset muito pequeno (adicionar mais fotos)
- Ou aumentar `patience` para 10-15

---

## 📊 Métricas de Sucesso

### Classificador (Bom)
- ✅ Accuracy > 85%
- ✅ Cada preset com recall > 75%
- ✅ Confusion matrix sem muitos erros cruzados

### Refinador (Bom)
- ✅ MAE médio < 15
- ✅ MAE dos sliders críticos (exposure, contrast) < 5
- ✅ MAE HSL < 10

### Qualidade Visual (Teste Manual)
- ✅ Presets identificados fazem sentido
- ✅ Ajustes aplicados são naturais
- ✅ Tons de pele preservados
- ✅ Consistência entre fotos similares

---

## 🎓 Conceitos-Chave

### Preset Base vs Deltas
- **Preset Base:** Ajustes gerais do teu "estilo" (ex: +0.5 exposure, +15 contrast)
- **Deltas:** Ajustes finos específicos de cada foto (ex: +0.2 shadows porque estava escura)

### Por Que 2 Modelos?
1. **Classificador:** "Que estilo fotográfico é esta imagem?" (4 opções)
2. **Refinador:** "Que ajustes finos específicos precisa?" (58 sliders)

### Por Que Deep Features?
- Capturam **conteúdo** (pessoas, paisagens, objetos)
- Exemplo: Retratos precisam de HSL Orange diferente de paisagens

---

## 🚀 Workflow Otimizado (Para Re-treinos Frequentes)

```bash
# Criar script de treino rápido
cat > retrain.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python << 'PYTHON'
from train_models import run_full_training_pipeline, set_training_configs
set_training_configs(
    catalog_path='/Users/SEU_NOME/Pictures/Lightroom Catalog.lrcat',
    num_presets=4,
    min_rating=3
)
run_full_training_pipeline()
PYTHON
EOF

chmod +x retrain.sh

# Usar:
./retrain.sh
```

---

**Desenvolvido por:** Nelson Silva
**Data:** 13 de Novembro de 2025
**Versão:** NSP Plugin V2.1 (58 Sliders)
