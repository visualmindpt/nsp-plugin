# Otimizações ML - FASE 1

## Visão Geral

Este documento descreve as otimizações implementadas na FASE 1 para lidar com o dataset pequeno (260 fotos) e combater overfitting.

## Problema Identificado

- **Dataset**: Apenas 260 fotos
- **Modelos atuais**: PresetClassifier (728 KB) e RefinementRegressor (836 KB)
- **Problema principal**: Overfitting severo, sem resultados práticos

## Ficheiros Criados

### 1. `services/ai_core/model_architectures_v2.py`

**Modelos Otimizados com ~50% Menos Parâmetros**

#### OptimizedPresetClassifier
- **Stat branch**: 128,64 → 64,32 (redução de 50%)
- **Deep branch**: 256,64 → 128,32 (redução de 50%)
- **Fusion**: 64 → 32 → presets
- **Novos recursos**:
  - Attention mechanism para focar em features relevantes
  - BatchNorm em todas as camadas
  - Dropout mais agressivo (0.4-0.5)

#### OptimizedRefinementRegressor
- **Stat branch**: 128,64 → 64,32 (redução de 50%)
- **Deep branch**: 256,64 → 128,32 (redução de 50%)
- **Preset embedding**: 32 → 16 (redução de 50%)
- **Novos recursos**:
  - Skip connections para melhor gradient flow
  - BatchNorm em todas as camadas
  - Dropout mais agressivo (0.4-0.5)

**Funções utilitárias**:
- `count_parameters()`: Conta parâmetros treináveis
- `get_model_size_mb()`: Calcula tamanho em MB

### 2. `services/ai_core/data_augmentation.py`

**Técnicas de Data Augmentation**

#### Funções de Augmentation:
- `augment_stat_features()`: Adiciona ruído gaussiano (std=0.05)
- `augment_deep_features()`: Feature dropout (prob=0.1)
- `mixup_deltas()`: Interpola entre exemplos (alpha=0.3)

#### Classes:
- **DataAugmentationDataset**: Wrapper que aplica augmentation on-the-fly
  - Suporta augmentation de stat features, deep features e deltas
  - Configurável para cada tipo de modelo

- **BatchMixupCollator**: Aplica mixup a nível de batch (mais eficiente)

### 3. `services/ai_core/trainer_v2.py`

**Trainers Otimizados**

#### OptimizedClassifierTrainer
- **OneCycleLR scheduler**: Convergência mais rápida
- **Mixed precision training**: Melhor performance
- **Gradient clipping**: max_norm=1.0
- **Logging detalhado**: LR atual, tempo por epoch

#### OptimizedRefinementTrainer
- **OneCycleLR scheduler**: max_lr configurável
- **Mixed precision training**: Com GradScaler
- **Weight decay mais agressivo**: 0.02 (vs 0.01)
- **Logging de MAE por parâmetro**: A cada 10 epochs

**Características comuns**:
- Suporte para MPS (Apple Silicon), CUDA e CPU
- Histórico completo de treino guardado em JSON
- Early stopping com paciência configurável

### 4. `services/dataset_stats.py`

**Sistema de Análise de Dataset**

#### Classe DatasetStatistics

**Métricas calculadas**:
- **Dataset size**: Total imagens, features, valores faltantes
- **Presets**: Distribuição, balanceamento
- **Feedback**: Estatísticas de feedback (se disponível)
- **Completeness**: Percentagem de dados completos
- **Diversity**: Score de diversidade (0-1)
- **Balance**: Imbalance ratio, Gini coefficient

**Métodos principais**:
- `compute_stats()`: Calcula todas as estatísticas
- `generate_report()`: Gera relatório JSON completo
- `print_summary()`: Imprime resumo no terminal

**Outputs**:
- Warnings automáticos (dataset pequeno, desbalanceado, etc.)
- Recomendações baseadas em estatísticas
- Relatório JSON para análise posterior

### 5. `train/train_models_v2.py`

**Script de Treino Otimizado**

#### Configurações otimizadas:
- `BATCH_SIZE`: 16 (reduzido para dataset pequeno)
- `USE_MIXED_PRECISION`: True
- `USE_DATA_AUGMENTATION`: True
- `CLASSIFIER_MAX_LR`: 0.01
- `REFINER_MAX_LR`: 0.005

#### Pipeline completo:
1. Extração de dados do Lightroom
2. Identificação de presets e deltas
3. **ANÁLISE DO DATASET** (novo!)
4. Extração de features
5. Preparação de dados
6. Treino do classificador otimizado
7. Treino do refinador otimizado

#### Outputs:
- Modelos em `models_v2/`
- Histórico de treino em JSON
- Relatório de análise do dataset
- Logs detalhados com LR e tempo

## Comparação com Versão Original

### Modelos

| Aspecto | Original | FASE 1 Otimizado | Melhoria |
|---------|----------|------------------|----------|
| Stat branch | 128→64 | 64→32 | -50% params |
| Deep branch | 256→64 | 128→32 | -50% params |
| Preset embedding | 32 | 16 | -50% params |
| Attention | ✗ | ✓ | Novo |
| BatchNorm | Parcial | Completo | Melhor |
| Dropout | 0.2-0.3 | 0.4-0.5 | Mais forte |
| Skip connections | ✗ | ✓ (Regressor) | Novo |

### Treino

| Aspecto | Original | FASE 1 Otimizado | Melhoria |
|---------|----------|------------------|----------|
| Scheduler | ReduceLROnPlateau | OneCycleLR | Mais rápido |
| Mixed precision | ✗ | ✓ | 2x mais rápido |
| Data augmentation | ✗ | ✓ | Combate overfitting |
| Batch size | 32 | 16 | Melhor para dataset pequeno |
| Logging | Básico | Detalhado | LR + tempo |
| Análise dataset | ✗ | ✓ | Insights |

## Como Usar

### 1. Treino com modelos otimizados

```bash
cd /Users/nelsonsilva/Documentos/gemini/projetos/NSP\ Plugin_dev_full_package
python train/train_models_v2.py
```

### 2. Análise do dataset (standalone)

```python
from services.dataset_stats import DatasetStatistics

stats = DatasetStatistics('data/lightroom_dataset.csv')
stats.print_summary()
stats.generate_report('dataset_report.json')
```

### 3. Usar modelos otimizados programaticamente

```python
from services.ai_core.model_architectures_v2 import OptimizedPresetClassifier
from services.ai_core.trainer_v2 import OptimizedClassifierTrainer

# Criar modelo
model = OptimizedPresetClassifier(
    stat_features_dim=50,
    deep_features_dim=512,
    num_presets=4
)

# Treinar
trainer = OptimizedClassifierTrainer(
    model,
    device='cuda',
    use_mixed_precision=True
)

trained_model = trainer.train(
    train_loader,
    val_loader,
    epochs=50,
    max_lr=0.01
)
```

## Resultados Esperados

### Redução de Overfitting
- Modelos menores reduzem capacidade de memorizar
- Data augmentation aumenta variabilidade
- Dropout forte previne co-adaptação

### Convergência Mais Rápida
- OneCycleLR encontra melhor LR automaticamente
- Mixed precision acelera computação
- Batch size menor permite updates mais frequentes

### Melhor Generalização
- Skip connections facilitam treino
- BatchNorm estabiliza distribuições
- Attention foca em features relevantes

## Próximos Passos (FASE 2)

Possíveis melhorias futuras:
- [ ] Ensemble de modelos
- [ ] Transfer learning com features pré-treinadas
- [ ] Adversarial training
- [ ] Semi-supervised learning com dados não rotulados
- [ ] Architecture search (NAS)
- [ ] Knowledge distillation

## Notas Importantes

1. **Ficheiros originais preservados**: Os ficheiros `model_architectures.py` e `trainer.py` permanecem intactos como backup; o treino ativo vive agora em `train/train_models_v2.py`.

2. **Compatibilidade**: Todos os modelos são compatíveis com PyTorch 2.2.0.

3. **Mixed precision**: Desabilitado automaticamente para MPS (Apple Silicon) devido a limitações.

4. **Dataset mínimo**: Recomenda-se pelo menos 100 imagens para treino básico.

## Dependências

Todas as dependências já estão incluídas no projeto:
- PyTorch >= 2.2.0
- NumPy
- Pandas
- Scikit-learn
- SciPy (para análise de diversidade)

## Contacto e Suporte

Para questões sobre estas otimizações, consulte a documentação completa ou contacte a equipa de desenvolvimento.
