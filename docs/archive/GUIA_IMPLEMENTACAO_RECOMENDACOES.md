# 📋 Guia de Implementação das Recomendações

**Data:** 15 Novembro 2025
**Status:** Production Ready

---

## ❓ Problema

Quando treinas com dataset pequeno (<500 fotos), aparecem estas recomendações:

```
RECOMENDAÇÕES (6):
   • Use data augmentation agressivo (noise, mixup, dropout)
   • Use regularização forte (dropout 0.4-0.5, weight decay)
   • Reduza complexidade dos modelos
   • Use OneCycleLR para melhor convergência
   • Adicione imagens mais diversas ao dataset
   • Considere diferentes cenários de iluminação e composição
```

**MAS não explicam COMO fazer!** Este guia resolve isso.

---

## ✅ O Que Já Está Automático?

Boas notícias! **Muitas coisas já funcionam automaticamente**:

| Recomendação | Status | Onde Está |
|--------------|--------|-----------|
| **OneCycleLR** | ✅ **AUTOMÁTICO** | `train/train_models_v2.py` linha 245 |
| **Weight Decay** | ✅ **AUTOMÁTICO** | `train/train_models_v2.py` linha 241 (0.01) |
| **Data Augmentation** | ✅ **AUTOMÁTICO** | `train/train_models_v2.py` linha 148-155 |
| **Dropout** | ⚠️ **PARCIAL** | Fixo em 0.3-0.4, pode aumentar |
| **Mixup** | ⚠️ **PARCIAL** | Apenas no refinador |
| **Noise Injection** | ❌ **NÃO IMPLEMENTADO** | - |
| **Reduzir Complexidade** | ❌ **MANUAL** | Requer editar arquitetura |

---

## 🎯 Recomendação 1: Data Augmentation Agressivo

### O Que Já Funciona Automaticamente

No arquivo `train/train_models_v2.py` (linhas 148-172):

```python
# JÁ ATIVADO AUTOMATICAMENTE!
augmentation = GaussianNoise(std=0.01)  # ✅ Noise básico
```

### Como Deixar Mais Agressivo

**Opção A: Via Linha de Comando** (RECOMENDADO)

```bash
# Ao treinar, NÃO é preciso fazer nada!
# Augmentation já está ativado automaticamente

python train_ui_v2.py
# Ou
python train/train_models_v2.py
```

**Opção B: Editar Código Para Augmentation Extremo** (se queres ainda mais)

Editar `train/train_models_v2.py` linha 148:

```python
# ANTES (padrão)
augmentation = GaussianNoise(std=0.01)

# DEPOIS (agressivo para datasets muito pequenos)
class AggressiveAugmentation(nn.Module):
    def __init__(self):
        super().__init__()
        self.noise = GaussianNoise(std=0.05)  # 5x mais noise
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        # Aplicar noise
        x = self.noise(x)
        # Aplicar dropout nas features
        x = self.dropout(x)
        return x

# Usar
augmentation = AggressiveAugmentation()
```

### Implementar Mixup (Misturar Imagens)

Mixup JÁ está implementado no refinador! Para ativar no classificador:

Editar `train/train_models_v2.py` linha 280 (dentro do loop de treino):

```python
# Adicionar ANTES de calcular loss
if np.random.rand() < 0.5:  # 50% chance de mixup
    # Mixup: misturar duas imagens
    indices = torch.randperm(features.size(0))
    lam = np.random.beta(0.2, 0.2)  # Alpha = Beta = 0.2 para mistura agressiva

    mixed_features = lam * features + (1 - lam) * features[indices]
    mixed_labels_a = labels
    mixed_labels_b = labels[indices]

    # Calcular loss para ambas as labels
    loss_a = F.cross_entropy(model(mixed_features), mixed_labels_a)
    loss_b = F.cross_entropy(model(mixed_features), mixed_labels_b)
    loss = lam * loss_a + (1 - lam) * loss_b
else:
    # Normal forward
    outputs = model(features)
    loss = F.cross_entropy(outputs, labels)
```

**Resultado Esperado:** Melhoria de 5-10% na accuracy com datasets pequenos.

---

## 🎯 Recomendação 2: Regularização Forte

### O Que Já Funciona Automaticamente

No arquivo `train/train_models_v2.py` linha 241:

```python
# JÁ ATIVADO AUTOMATICAMENTE!
optimizer = optim.AdamW(
    model.parameters(),
    lr=initial_lr,
    weight_decay=0.01  # ✅ Regularização L2 ativada
)
```

### Como Aumentar Regularização

**Aumentar Dropout** (Fácil, recomendado)

Editar `services/ai_core/model_architectures_v3.py`:

```python
# CLASSIFICADOR - Linha ~45
def create_preset_classifier_v3(...):
    return PresetClassifierV3(
        stat_features=stat_features,
        deep_features=deep_features,
        num_presets=num_presets,
        dropout=0.5,  # MUDAR de 0.3 para 0.5 (datasets muito pequenos)
        ...
    )

# REFINADOR - Linha ~120
def create_refinement_model_v3(...):
    return RefinementModelV3(
        stat_features=stat_features,
        deep_features=deep_features,
        num_deltas=num_deltas,
        dropout=0.5,  # MUDAR de 0.4 para 0.5
        ...
    )
```

**Aumentar Weight Decay** (Moderado)

Editar `train/train_models_v2.py` linha 241:

```python
# ANTES
optimizer = optim.AdamW(model.parameters(), lr=initial_lr, weight_decay=0.01)

# DEPOIS (para datasets muito pequenos)
optimizer = optim.AdamW(model.parameters(), lr=initial_lr, weight_decay=0.05)
# 5x mais forte!
```

**Adicionar L1 Regularization** (Avançado)

Editar `train/train_models_v2.py` linha 295 (dentro do loop):

```python
# ADICIONAR após calcular loss
l1_lambda = 0.001  # Fator de regularização L1
l1_norm = sum(p.abs().sum() for p in model.parameters())
loss = loss + l1_lambda * l1_norm
```

**Resultado Esperado:** Reduz overfitting em 10-20% com datasets pequenos.

---

## 🎯 Recomendação 3: Reduzir Complexidade dos Modelos

### Por Que É Necessário?

Com **32 fotos**, um modelo com **89,090 parâmetros** é MUITO grande! Rácio ideal:

- **Mínimo:** 10 fotos por parâmetro
- **Ideal:** 50 fotos por parâmetro

Com 32 fotos, deverias ter **no máximo 3,200 parâmetros** (10x menos!).

### Como Reduzir

**Opção A: Usar Modelos Smaller (Via UI Gradio)**

Na UI Gradio, escolher **"Tiny"** em vez de **"Medium"**:

```python
# Em train_ui_v2.py isso já está preparado!
# Basta selecionar no dropdown da UI
```

**Opção B: Editar Código Diretamente**

Editar `services/ai_core/model_architectures_v3.py`:

```python
# CLASSIFICADOR - ANTES (linha ~60)
self.fusion = nn.Sequential(
    nn.Linear(total_features, 512),  # Muito grande!
    nn.BatchNorm1d(512),
    nn.ReLU(),
    nn.Dropout(dropout),
    nn.Linear(512, 256),
    nn.ReLU(),
    nn.Dropout(dropout),
)

# DEPOIS (para datasets muito pequenos)
self.fusion = nn.Sequential(
    nn.Linear(total_features, 128),  # 4x menor
    nn.BatchNorm1d(128),
    nn.ReLU(),
    nn.Dropout(dropout),
    nn.Linear(128, 64),  # 4x menor
    nn.ReLU(),
    nn.Dropout(dropout),
)
```

```python
# REFINADOR - ANTES (linha ~150)
self.shared_network = nn.Sequential(
    nn.Linear(total_features, 512),
    nn.ReLU(),
    nn.Dropout(dropout),
    nn.Linear(512, 256),
    nn.ReLU(),
)

# DEPOIS
self.shared_network = nn.Sequential(
    nn.Linear(total_features, 128),  # 4x menor
    nn.ReLU(),
    nn.Dropout(dropout),
    nn.Linear(128, 64),  # 4x menor
    nn.ReLU(),
)
```

**Resultado Esperado:**
- Parâmetros: ~89K → ~5-10K (10x menos!)
- Overfitting: Reduz drasticamente
- Accuracy: Pode baixar 5-10% inicialmente, mas generaliza MUITO melhor

---

## 🎯 Recomendação 4: OneCycleLR

### ✅ JÁ ESTÁ AUTOMÁTICO!

Implementado em `train/train_models_v2.py` linha 245:

```python
# JÁ FUNCIONA! Nada a fazer
scheduler = optim.lr_scheduler.OneCycleLR(
    optimizer,
    max_lr=max_lr,
    total_steps=total_steps,
    pct_start=0.3,
    anneal_strategy='cos',
    div_factor=25.0,
    final_div_factor=10000.0
)
```

**Nenhuma ação necessária!** 🎉

---

## 🎯 Recomendação 5: Adicionar Imagens Mais Diversas

### Como Fazer

**Passo 1: Analisar Diversidade Atual**

```bash
# Ver relatório de diversidade
cat models/dataset_analysis.json | grep diversity_score
# Se < 0.4, dataset é pouco diverso
```

**Passo 2: Identificar O Que Falta**

```python
# Criar script para analisar
import pandas as pd

df = pd.read_csv('data/lightroom_dataset.csv')

# Ver distribuição de ISO
print(df['iso'].value_counts())
# Todas as fotos são ISO 100? Adiciona fotos com ISO 400, 1600, 3200

# Ver distribuição de temperatura de cor
print(df['temp'].describe())
# Todas entre 5000-5500K? Adiciona fotos com 3000K (tungsten) e 7000K (sombra)

# Ver distribuição de abertura
print(df['aperture'].value_counts())
# Todas são f/2.8? Adiciona f/1.4 e f/11
```

**Passo 3: Exportar Mais Fotos Diversas do Lightroom**

No Lightroom Classic:

1. **Filtrar por ISO variado:**
   - Selecionar fotos com ISO 100, 400, 1600, 3200

2. **Filtrar por iluminação:**
   - Dia ensolarado
   - Dia nublado
   - Golden hour
   - Blue hour
   - Interior/flash

3. **Filtrar por abertura:**
   - f/1.4-2.8 (baixa profundidade de campo)
   - f/5.6-8 (normal)
   - f/11-16 (grande profundidade de campo)

4. **Exportar novamente:**
   ```bash
   python tools/export_lightroom_dataset.py --min-photos 100
   ```

**Resultado Esperado:** Diversity score sobe de 0.3 para 0.6+

---

## 🎯 Recomendação 6: Diferentes Cenários de Iluminação

### Checklist de Cenários

Certifica-te que tens fotos de **TODOS** estes cenários:

```
☐ Luz natural direta (sol direto)
☐ Luz natural difusa (nublado)
☐ Golden hour (pôr do sol)
☐ Blue hour (crepúsculo)
☐ Interior natural (janela)
☐ Interior artificial (tungsten ~3000K)
☐ Interior artificial (LED ~4500K)
☐ Flash direto
☐ Flash bounced (refletido)
☐ Misto (natural + artificial)
```

### Como Adicionar

**No Lightroom Classic:**

1. **Criar Smart Collections por temperatura de cor:**
   - `Temp < 3500K` (tungsten)
   - `Temp 3500-5000K` (warm)
   - `Temp 5000-6500K` (daylight)
   - `Temp > 6500K` (shade/flash)

2. **Selecionar 5-10 fotos de cada coleção**

3. **Exportar dataset atualizado:**
   ```bash
   python tools/export_lightroom_dataset.py --min-photos 200
   ```

**Resultado Esperado:** Modelo aprende a lidar com qualquer iluminação.

---

## 📊 Tabela Resumo: O Que Fazer?

| Recomendação | Já Automático? | Ação Necessária | Dificuldade | Impacto |
|--------------|----------------|-----------------|-------------|---------|
| **Data Augmentation** | ✅ Sim (básico) | Opcional: tornar agressivo | Média | +5-10% accuracy |
| **Weight Decay** | ✅ Sim (0.01) | Opcional: aumentar para 0.05 | Fácil | -10-20% overfitting |
| **Dropout** | ⚠️ Parcial (0.3-0.4) | Aumentar para 0.5 | Fácil | -10% overfitting |
| **OneCycleLR** | ✅ Sim | Nada! | N/A | Já otimizado |
| **Reduzir Complexidade** | ❌ Não | Editar arquiteturas | Difícil | -50% overfitting |
| **Mais Imagens** | ❌ Não | Exportar mais fotos | Fácil | +20-40% generalização |
| **Cenários Diversos** | ❌ Não | Exportar fotos variadas | Fácil | +15-30% robustez |

---

## 🚀 Quick Start: O Mínimo a Fazer AGORA

Com apenas **32 fotos**, faz isto URGENTEMENTE:

### 1. Aumentar Dropout (2 minutos)

```bash
# Editar services/ai_core/model_architectures_v3.py
# Linha 45: dropout=0.5
# Linha 120: dropout=0.5
```

### 2. Exportar Mais Fotos (5 minutos)

```bash
# No Lightroom, selecionar pelo menos 100 fotos editadas diversas
python tools/export_lightroom_dataset.py --min-photos 100
```

### 3. Retreinar (5 minutos)

```bash
python train_ui_v2.py
# Selecionar configurações
# Clicar "Iniciar Treino"
```

**Resultado Esperado:**
- Overfitting: 100% val accuracy → 75-85% (MUITO MELHOR!)
- Generalização: Modelo funciona em fotos novas
- Confidence: Predições mais confiáveis

---

## 🔧 Debugging: Como Saber Se Funcionou?

### Antes vs Depois

**ANTES (com 32 fotos, sem melhorias):**
```
Train Accuracy: 100%
Val Accuracy: 100%  ← Overfitting total!
Test (fotos novas): 40-50%  ← Falha em produção
```

**DEPOIS (com melhorias):**
```
Train Accuracy: 85-90%
Val Accuracy: 75-85%  ← Mais realista
Test (fotos novas): 70-80%  ← Funciona em produção!
```

### Métricas a Observar

No log de treino, procurar:

```
✅ BOM: Val Acc sobe gradualmente (27→100% como no teu log)
❌ MAU: Val Acc = 100% desde epoch 1

✅ BOM: Train Loss > Val Loss (leve overfitting é OK)
❌ MAU: Train Loss << Val Loss (overfitting severo)

✅ BOM: Early stopping entre epochs 15-30
❌ MAU: Early stopping epoch 50 (modelo não aprendeu)
```

---

## 📚 Leitura Adicional

- **Data Augmentation:** `ML_OPTIMIZATIONS_GUIDE.md` secção 3.2
- **Regularização:** `OTIMIZACOES_ML.md` linha 245
- **Transfer Learning:** `TRANSFER_LEARNING_GUIDE.md` (solução definitiva!)

---

## 💡 Solução Definitiva: Transfer Learning

**EM VEZ DE** implementar todas estas recomendações manualmente, **USA TRANSFER LEARNING**:

```bash
# Com CLIP, precisas apenas 50 fotos e consegues 80-85% accuracy!
python train/train_with_clip.py --epochs 30
```

Ver `TRANSFER_LEARNING_QUICKSTART.md` para detalhes.

---

**Criado:** 15 Novembro 2025
**Última Atualização:** 15 Novembro 2025
