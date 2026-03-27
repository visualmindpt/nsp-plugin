# 🏗️ Arquitetura de Treino Incremental - NSP Plugin

## 📋 Visão Geral

Sistema de **aprendizagem incremental** que permite treinar o modelo ao longo do tempo com múltiplos catálogos, acumulando conhecimento sem perder aprendizagem anterior.

---

## 🎯 Objetivos

1. **Treino Incremental**: Adicionar conhecimento com cada novo catálogo
2. **Separação de Domínios**: Datasets públicos vs catálogos privados
3. **Acumulação de Conhecimento**: Sem "catastrophic forgetting"
4. **Estatísticas Agregadas**: Track total de imagens/catálogos treinados

---

## 🏛️ Arquitetura em 2 Fases

### **Fase 1: Base Model** (Datasets Públicos)

Aprende habilidades **genéricas** de fotografia:

```
┌─────────────────────────────────────────────┐
│         BASE MODEL (Generic Skills)         │
├─────────────────────────────────────────────┤
│                                             │
│  📊 Culling (AVA, Flickr-AES)              │
│  ├─ Boas vs más fotos                      │
│  ├─ Composição genérica                    │
│  └─ Qualidade estética geral               │
│                                             │
│  🔍 Qualidade Técnica (PAQ-2-PIQ)          │
│  ├─ Nitidez                                │
│  ├─ Exposição correta                      │
│  ├─ Ruído                                  │
│  └─ Aberrações cromáticas                  │
│                                             │
│  👤 Reconhecimento (COCO, Custom)          │
│  ├─ Detecção de rostos                     │
│  ├─ Objetos principais                     │
│  └─ Cenas (interior, exterior, etc.)       │
│                                             │
│  📐 Composição (Places365, COCO)           │
│  ├─ Regra dos terços                       │
│  ├─ Linhas guias                           │
│  └─ Pontos de interesse                    │
│                                             │
└─────────────────────────────────────────────┘
         ▼ Transfer Learning
┌─────────────────────────────────────────────┐
│       STYLE MODEL (Personal Style)          │
│         🔒 Catálogos Privados               │
└─────────────────────────────────────────────┘
```

**Características:**
- ✅ Treina **uma vez** com cada dataset público
- ✅ Conhecimento **geral** de fotografia
- ✅ **Não** inclui preferências pessoais
- ✅ Serve de **base** para todos os utilizadores

**Features aprendidas:**
- Culling (keep vs reject)
- Qualidade técnica objetiva
- Reconhecimento de objetos/rostos
- Composição genérica

**Datasets usados:**
- **AVA**: 250k fotos com ratings estéticos
- **Flickr-AES**: 40k fotos do Flickr
- **PAQ-2-PIQ**: 40k fotos com quality ratings
- **COCO**: 330k imagens anotadas
- **MIT Places365**: 1.8M cenas categorizadas

---

### **Fase 2: Style Model** (Catálogos Privados - **INCREMENTAL**)

Aprende **estilo pessoal** de edição:

```
┌─────────────────────────────────────────────┐
│     STYLE MODEL V1 (Catálogo 1)             │
│     32 fotos editadas                       │
│     ├─ Temperatura preferida                │
│     ├─ Tons de cor característicos          │
│     └─ Contraste/clareza típicos            │
└─────────────────────────────────────────────┘
         ▼ Fine-tuning incremental
┌─────────────────────────────────────────────┐
│     STYLE MODEL V2 (Catálogo 2)             │
│     +150 fotos → Total: 182 fotos          │
│     ├─ Refina padrões anteriores            │
│     ├─ Aprende novos estilos                │
│     └─ Mantém conhecimento V1               │
└─────────────────────────────────────────────┘
         ▼ Fine-tuning incremental
┌─────────────────────────────────────────────┐
│     STYLE MODEL V3 (Catálogo 3)             │
│     +420 fotos → Total: 602 fotos          │
│     ├─ Estilo cada vez mais refinado        │
│     ├─ Menos overfitting                    │
│     └─ Generalização melhorada              │
└─────────────────────────────────────────────┘
```

**Características:**
- ✅ **Incremental**: Cada treino adiciona ao anterior
- ✅ **Personalizado**: Aprende SEU estilo
- ✅ **Acumulativo**: Estatísticas somam-se
- ✅ **Versionado**: Cada treino = nova versão

**Features aprendidas** (apenas de catálogos privados):

#### 1. **Estilo de Edição**
```python
[
    "Temperature",      # Temperatura de cor preferida
    "Tint",            # Matiz preferido
    "Vibrance",        # Intensidade de cor
    "Saturation",      # Saturação geral
    "Contrast",        # Contraste preferido
    "Highlights",      # Como tratar altas luzes
    "Shadows",         # Como tratar sombras
    "Whites",          # Ponto branco
    "Blacks",          # Ponto preto
    "Clarity",         # Claridade/micro-contraste
    "Dehaze",          # Remoção de neblina
    "Exposure"         # Exposição geral
]
```

#### 2. **Color Grading** (Tom & Cor)
```python
[
    "SplitToningShadowHue",           # Cor nas sombras
    "SplitToningShadowSaturation",    # Saturação sombras
    "SplitToningHighlightHue",        # Cor nas altas luzes
    "SplitToningHighlightSaturation", # Saturação altas luzes
    "ColorGradeBlending",             # Blending de grades
    "ColorGradeMidtoneHue"            # Cor nos meios-tons
]
```

#### 3. **Curvas Tonais**
```python
[
    "ToneCurvePV2012",        # Curva de tons
    "ParametricShadows",      # Sombras paramétricas
    "ParametricDarks",        # Tons escuros
    "ParametricLights",       # Tons claros
    "ParametricHighlights"    # Altas luzes paramétricas
]
```

---

## 🔄 Fluxo de Treino Incremental

### 1. **Primeira Vez** (Setup Inicial)

```
Utilizador → Treina Base Model (OPCIONAL)
          ↓
     AVA Dataset (250k fotos)
          ↓
  Base Model Treinado ✅
          ↓
  Guarda: base_model.pth
```

**Nota:** Base model pode ser:
- ✅ Treinado localmente (se tiver recursos)
- ✅ Download de modelo pré-treinado (recomendado)
- ⏭️ Saltado (treina só style model)

---

### 2. **Catálogo 1** (Primeira Coleção)

```
Utilizador → Seleciona Catálogo 1 (32 fotos)
          ↓
   Extrai edições do Lightroom
          ↓
   Fine-tune Style Model V1
          ↓
   Guarda: style_model.pth (v1)
          ↓
   Atualiza: training_history.json
          {
            "total_images": 32,
            "total_catalogs": 1,
            "style_model_version": 1
          }
```

---

### 3. **Catálogo 2** (Adiciona Mais)

```
Utilizador → Seleciona Catálogo 2 (150 fotos)
          ↓
   Carrega Style Model V1 ✅
          ↓
   Fine-tune com 150 novas fotos
          ↓
   Guarda: style_model.pth (v2)
          ↓
   Atualiza: training_history.json
          {
            "total_images": 182,      ← Acumula!
            "total_catalogs": 2,       ← Incrementa!
            "style_model_version": 2   ← Nova versão!
          }
```

---

### 4. **Catálogo N** (Continua Crescendo)

```
Utilizador → Seleciona Catálogo N (420 fotos)
          ↓
   Carrega Style Model V(N-1) ✅
          ↓
   Fine-tune com 420 novas fotos
          ↓
   Guarda: style_model.pth (vN)
          ↓
   Atualiza: training_history.json
          {
            "total_images": 602,
            "total_catalogs": 3,
            "style_model_version": 3
          }
```

---

## 📊 Sistema de Histórico

### Estrutura `training_history.json`

```json
{
  "training_sessions": [
    {
      "type": "base_model",
      "task": "culling",
      "dataset": "datasets/ava",
      "epochs": 50,
      "num_images": 250000,
      "accuracy": 0.87,
      "timestamp": "2025-11-22T10:30:00"
    },
    {
      "type": "style_incremental",
      "catalog": "/path/to/catalog1.lrcat",
      "epochs": 30,
      "learning_rate": 0.0001,
      "model_version": 1,
      "num_images": 32,
      "accuracy": 0.75,
      "previous_total_images": 0,
      "timestamp": "2025-11-22T14:20:00"
    },
    {
      "type": "style_incremental",
      "catalog": "/path/to/catalog2.lrcat",
      "epochs": 30,
      "learning_rate": 0.0001,
      "model_version": 2,
      "num_images": 150,
      "accuracy": 0.82,
      "previous_total_images": 32,
      "timestamp": "2025-11-22T16:45:00"
    }
  ],
  "total_images": 182,
  "total_catalogs": 2,
  "base_model_trained": true,
  "style_model_version": 2,
  "created_at": "2025-11-22T10:00:00"
}
```

---

## 🎨 Separação: Público vs Privado

### ❌ **NÃO** Usar Datasets Públicos Para:

- ❌ Estilo de edição pessoal
- ❌ Preferências de cor
- ❌ Tom/mood característico
- ❌ Temperatura de cor preferida
- ❌ Ajustes finos (Temperature, Tint, Vibrance)

**Razão:** Cada fotógrafo tem seu estilo único!

---

### ✅ **SIM** Usar Datasets Públicos Para:

- ✅ Culling (boa vs má foto)
- ✅ Qualidade técnica (nitidez, exposição)
- ✅ Reconhecimento facial
- ✅ Detecção de objetos
- ✅ Composição genérica
- ✅ Identificação de cenas

**Razão:** Princípios objetivos de fotografia!

---

## 🔧 Técnicas Anti-Forgetting

Para evitar "catastrophic forgetting" (esquecer treino anterior):

### 1. **Freeze Base Layers**
```python
# Congela camadas do base model durante fine-tuning
for param in base_model.parameters():
    param.requires_grad = False

# Só treina camadas de estilo
for param in style_head.parameters():
    param.requires_grad = True
```

### 2. **Lower Learning Rate**
```python
# Fine-tuning usa LR muito menor
base_training_lr = 0.001       # Treino inicial
fine_tuning_lr = 0.0001        # 10x menor!
```

### 3. **Replay Buffer** (Futuro)
```python
# Guardar exemplos de catálogos anteriores
# Misturar com novos exemplos durante treino
replay_ratio = 0.2  # 20% de dados antigos
```

### 4. **Regularização**
```python
# Penalizar mudanças muito grandes nos pesos
weight_decay = 0.01
l2_regularization = True
```

---

## 📈 Estatísticas na UI

### Antes (Errado):
```
📊 Dataset Statistics:
   Photos with rating ≥ 3: 32
```

### Depois (Correto):
```
📊 Current Catalog:
   Photos with rating ≥ 3: 32

📈 ACCUMULATED TRAINING:
   Total images trained: 602
   Total catalogs: 3
   Style model version: 3
   Last training: 2025-11-22 16:45
```

---

## 🚀 Workflow Recomendado

### Setup Inicial (Uma Vez)

1. **Download Base Model Pré-Treinado** (Recomendado)
   ```bash
   # Download modelo já treinado com AVA + PAQ-2-PIQ
   curl -O https://models.nsp-plugin.com/base_model_v1.pth
   ```

   OU

2. **Treina Base Model Localmente** (Se tiver GPU potente)
   - Tab "Dataset Manager" → Download AVA
   - Tab "Advanced Training" → Train Base Model

---

### Treino Contínuo (Sempre Que Editares Fotos)

```
Workflow Semanal/Mensal:

1. Edita fotos no Lightroom normalmente
   ├─ Aplica presets
   ├─ Ajusta manualmente
   └─ Dá ratings (3+ estrelas)

2. Quando tiveres 30-50 fotos editadas:
   ├─ Abre NSP Training UI
   ├─ Tab "Quick Start"
   ├─ Seleciona catálogo
   └─ Click "Train"

3. Modelo aprende teu estilo:
   ├─ Carrega versão anterior ✅
   ├─ Fine-tune com novas fotos
   ├─ Guarda versão atualizada
   └─ Estatísticas acumulam

4. Usa no Lightroom Plugin:
   ├─ Modelo mais inteligente
   ├─ Sugestões mais precisas
   └─ Adapta-se ao teu estilo evolutivo
```

---

## 🎯 Vantagens da Arquitetura

### ✅ Treino Incremental
- Não precisa de milhares de fotos logo no início
- Começa com 30-50 fotos
- Vai melhorando com cada catálogo

### ✅ Separação de Domínios
- Habilidades genéricas (público) ≠ Estilo pessoal (privado)
- Base model partilhável entre utilizadores
- Style model 100% personalizado

### ✅ Sem Catastrophic Forgetting
- Não esquece treino anterior
- Conhecimento acumula-se
- Cada catálogo melhora o modelo

### ✅ Estatísticas Reais
- Track total de imagens
- Histórico completo
- Versioning do modelo

### ✅ Flexibilidade
- 32 fotos OK ✅
- 3200 fotos OK ✅
- Qualquer tamanho funciona!

---

## 🔜 Próximos Passos

1. ✅ Sistema de treino incremental criado
2. ⬜ Integrar com `train_ui_clean.py`
3. ⬜ Download de base model pré-treinado
4. ⬜ Replay buffer para evitar forgetting
5. ⬜ Validação cruzada com holdout set
6. ⬜ Métricas de performance por versão

---

**Autor:** NSP Plugin Team
**Data:** 2025-11-22
**Versão:** 1.0
