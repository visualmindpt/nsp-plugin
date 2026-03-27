# Quick Start - FASE 1 Otimizações

## Comandos Rápidos

### 1. Validar Instalação (1 minuto)
```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate
python test_fase1_imports.py
```

**Output esperado:**
- Todos os 5 testes passam
- Modelos otimizados: ~82K e ~87K parâmetros
- PyTorch 2.2.0, MPS disponível

---

### 2. Comparar Modelos (30 segundos)
```bash
source venv/bin/activate
python compare_models.py
```

**Verá:**
- Redução de 52-55% nos parâmetros
- Comparação lado a lado
- Lista de melhorias

---

### 3. Analisar Dataset (Python)
```python
from services.dataset_stats import DatasetStatistics

# Carregar e analisar
stats = DatasetStatistics('data/lightroom_dataset.csv')
stats.print_summary()

# Guardar relatório
stats.generate_report('models_v2/dataset_analysis.json')
```

**Métricas calculadas:**
- Tamanho do dataset
- Distribuição de presets
- Balanceamento de classes
- Diversidade das imagens
- Warnings e recomendações

---

### 4. Treinar Modelos Otimizados

**Passo 1: Configurar**
```bash
# Editar train/train_models_v2.py
# Linha 33: CATALOG_PATH = Path('SEU_CAMINHO/Lightroom Catalog.lrcat')
```

**Passo 2: Executar**
```bash
source venv/bin/activate
python train/train_models_v2.py
```

**Output:**
- Análise automática do dataset
- Treino do classificador otimizado
- Treino do regressor otimizado
- Modelos guardados em `models_v2/`

---

## Estrutura de Outputs

### Após Treino Completo

```
models_v2/
├── best_preset_classifier_v2.pth      # Modelo classificador
├── best_refinement_model_v2.pth       # Modelo regressor
├── preset_centers.json                # Centros dos presets
├── delta_columns.json                 # Colunas de deltas
├── scaler_stat.pkl                    # Scaler para stat features
├── scaler_deep.pkl                    # Scaler para deep features
├── scaler_deltas.pkl                  # Scaler para deltas
├── classifier_training_history.json   # Histórico do classificador
├── refiner_training_history.json      # Histórico do regressor
└── dataset_analysis.json              # Análise do dataset
```

---

## Configurações Importantes

### Dataset Pequeno (< 500 fotos)
```python
# Em train/train_models_v2.py
BATCH_SIZE = 16                # Menor batch = mais updates
USE_DATA_AUGMENTATION = True   # Aumenta variedade
STAT_NOISE_STD = 0.05          # Ruído gaussiano
DEEP_DROPOUT_PROB = 0.1        # Feature dropout
MIXUP_ALPHA = 0.3              # Interpolação
```

### Learning Rates (OneCycleLR)
```python
CLASSIFIER_MAX_LR = 0.01   # LR máximo para classificador
REFINER_MAX_LR = 0.005     # LR máximo para regressor
```

### Early Stopping
```python
PATIENCE = 10  # Parar após 10 epochs sem melhoria
```

---

## Exemplo Completo: Treino Custom

```python
import torch
from torch.utils.data import DataLoader
from services.ai_core.model_architectures_v2 import OptimizedPresetClassifier
from services.ai_core.trainer_v2 import OptimizedClassifierTrainer
from services.ai_core.training_utils import LightroomDataset
from services.ai_core.data_augmentation import DataAugmentationDataset

# 1. Criar modelo otimizado
model = OptimizedPresetClassifier(
    stat_features_dim=50,
    deep_features_dim=512,
    num_presets=4
)

# 2. Preparar dados (assumindo X_train, y_train já existem)
train_dataset = LightroomDataset(
    X_stat_train,
    X_deep_train,
    y_train_labels
)

# 3. Aplicar augmentation
aug_dataset = DataAugmentationDataset(
    train_dataset,
    augment_stat=True,
    augment_deep=True,
    stat_noise_std=0.05,
    deep_dropout_prob=0.1
)

# 4. DataLoader
train_loader = DataLoader(aug_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)

# 5. Configurar trainer
device = 'mps' if torch.backends.mps.is_available() else 'cpu'
trainer = OptimizedClassifierTrainer(
    model,
    device=device,
    use_mixed_precision=True
)

# 6. Treinar
trained_model = trainer.train(
    train_loader,
    val_loader,
    epochs=50,
    patience=10,
    num_presets=4,
    max_lr=0.01
)

# 7. Guardar
torch.save(trained_model.state_dict(), 'my_model.pth')
```

---

## Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'torch'"
```bash
# Ativar venv
source venv/bin/activate
```

### Erro: Dataset vazio
```python
# Verificar caminho do catálogo
CATALOG_PATH = Path('caminho_correto/Lightroom Catalog.lrcat')

# Reduzir min_rating
MIN_RATING = 2  # ou 1
```

### Erro: Out of Memory
```python
# Reduzir batch size
BATCH_SIZE = 8  # ou menor

# Desabilitar mixed precision
USE_MIXED_PRECISION = False
```

### Warning: Dataset muito pequeno
```python
# Aumentar augmentation
STAT_NOISE_STD = 0.1      # Mais ruído
DEEP_DROPOUT_PROB = 0.2   # Mais dropout
MIXUP_ALPHA = 0.5         # Mais mixup

# Reduzir complexidade
# (já otimizado na FASE 1)
```

---

## Comparação: Antes vs Depois

### Antes (Original)
```
PresetClassifier: 171,076 params, 0.65 MB
RefinementRegressor: 196,346 params, 0.75 MB
Scheduler: ReduceLROnPlateau
Mixed Precision: Não
Data Augmentation: Não
Batch Size: 32
```

### Depois (FASE 1)
```
OptimizedPresetClassifier: 82,116 params, 0.32 MB (-52%)
OptimizedRefinementRegressor: 87,674 params, 0.34 MB (-55%)
Scheduler: OneCycleLR (2-3x mais rápido)
Mixed Precision: Sim (2x speedup)
Data Augmentation: Sim (noise, dropout, mixup)
Batch Size: 16 (melhor para dataset pequeno)
```

---

## Verificar Resultados

### Durante o Treino
```
Epoch 1/50 (12.3s)
  Train Loss: 1.3421
  Val Loss: 1.2156 | Val Acc: 0.4500
  LR: 0.003456
  Melhor modelo guardado!
```

### Após o Treino
```python
import json

# Ler histórico
with open('models_v2/classifier_training_history.json') as f:
    history = json.load(f)

print("Melhor val_loss:", min(history['val_losses']))
print("Melhor val_acc:", max(history['val_accuracies']))

# Plotar
import matplotlib.pyplot as plt
plt.plot(history['train_losses'], label='Train')
plt.plot(history['val_losses'], label='Val')
plt.legend()
plt.show()
```

---

## Próximo Passo

Depois de treinar os modelos otimizados:

1. **Comparar resultados** com modelos originais
2. **Avaliar métricas** (accuracy, MAE)
3. **Testar inferência** em imagens novas
4. **Ajustar hyperparameters** se necessário
5. **Considerar FASE 2** para melhorias avançadas

---

## Suporte

- **Documentação completa**: `FASE1_OPTIMIZATIONS.md`
- **Resumo de implementação**: `IMPLEMENTACAO_FASE1_RESUMO.md`
- **Testes**: `python test_fase1_imports.py`
- **Comparação**: `python compare_models.py`

---

**Bom treino! 🚀**
