# 🚀 Análise de Otimizações de Performance - NSP Plugin V2

**Data:** 13 de Novembro de 2025
**Versão:** 0.6.0

---

## 📊 Otimizações Já Implementadas

### ✅ Treino

| Otimização | Estado | Localização | Impacto |
|------------|--------|-------------|---------|
| **Batch Processing** | ✅ Implementado | `train_models.py:44` | Alto - Reduz tempo de treino |
| **Early Stopping** | ✅ Implementado | `train_models.py:44` (patience=7) | Médio - Evita overfitting |
| **GPU/MPS Support** | ✅ Implementado | `trainer.py` | Alto - 10-50x mais rápido |
| **Data Normalization** | ✅ Implementado | `StandardScaler` | Alto - Melhora convergência |
| **Train/Val Split** | ✅ Implementado | `train_test_split` | Alto - Validação correcta |
| **Weighted Loss** | ✅ Implementado | `WeightedMSELoss` | Médio - Foco em parâmetros importantes |
| **DataLoader Workers** | ✅ Implementado | `num_workers` configurável | Médio - I/O paralelo |

### ✅ Inferência

| Otimização | Estado | Localização | Impacto |
|------------|--------|-------------|---------|
| **Batch Processing Plugin** | ✅ Implementado | `ApplyAIPresetBatchV2.lua:97` (20 fotos/batch) | Alto |
| **Model Caching** | ✅ Implementado | Modelo carregado 1x no startup | Alto |
| **Rate Limiting** | ✅ Implementado | `server.py:1210` (10/min) | Médio - Protege servidor |
| **Async Processing** | ✅ Implementado | `LrTasks.startAsyncTask` | Alto - UI não bloqueia |

---

## ⚠️ Otimizações Pendentes (Alto Impacto)

### 1. Mixed Precision Training (AMP)
**Impacto:** 🟢 **2-3x mais rápido, 40% menos memória**

```python
# services/ai_core/trainer.py
from torch.cuda.amp import autocast, GradScaler

class ClassifierTrainer:
    def __init__(self, ...):
        self.scaler = GradScaler()

    def train_epoch(self, ...):
        for batch in dataloader:
            with autocast():  # Mixed precision
                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)

            self.scaler.scale(loss).backward()
            self.scaler.step(self.optimizer)
            self.scaler.update()
```

**Benefício:** Treino 2-3x mais rápido em GPUs modernas

---

### 2. Model Quantization (INT8)
**Impacto:** 🟢 **4x menor tamanho, 2-4x mais rápido**

```python
# Após treino
import torch.quantization

model_quantized = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)
torch.save(model_quantized.state_dict(), 'model_quantized.pth')
```

**Benefício:** Inferência 2-4x mais rápida, modelo 75% mais pequeno

---

### 3. ONNX Export
**Impacto:** 🟢 **Cross-platform, otimizações automáticas**

```python
# services/ai_core/export_onnx.py
import torch.onnx

def export_to_onnx(model, input_shape, output_path):
    dummy_input = torch.randn(*input_shape)
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,  # Otimizações
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size'}}
    )
```

**Benefício:** Inferência otimizada, portable para C++/C#

---

### 4. Feature Extraction Caching
**Impacto:** 🟡 **Evita recomputação de features**

```python
# services/ai_core/feature_cache.py
import hashlib
import pickle
from pathlib import Path

class FeatureCache:
    def __init__(self, cache_dir='cache/features'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, image_path):
        # Hash do caminho + timestamp de modificação
        stat = Path(image_path).stat()
        key = f"{image_path}_{stat.st_mtime}"
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, image_path):
        key = self.get_cache_key(image_path)
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        return None

    def set(self, image_path, features):
        key = self.get_cache_key(image_path)
        cache_file = self.cache_dir / f"{key}.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump(features, f)
```

**Benefício:** 5-10x mais rápido em re-predições

---

### 5. Gradient Checkpointing
**Impacto:** 🟡 **50% menos memória no treino**

```python
# services/ai_core/model_architectures.py
import torch.utils.checkpoint as checkpoint

class PresetClassifier(nn.Module):
    def forward(self, x_stat, x_deep):
        # Usar checkpointing em blocos grandes
        x = checkpoint.checkpoint(self.heavy_block, x_stat, x_deep)
        return self.output(x)
```

**Benefício:** Permite treinar com batch sizes maiores

---

### 6. Knowledge Distillation
**Impacto:** 🟢 **Modelo 5x menor, 90% da precisão**

```python
# services/ai_core/distillation.py
class DistillationTrainer:
    def __init__(self, teacher_model, student_model):
        self.teacher = teacher_model
        self.student = student_model
        self.temperature = 3.0

    def distillation_loss(self, student_logits, teacher_logits, labels):
        # Soft targets do teacher
        soft_loss = F.kl_div(
            F.log_softmax(student_logits / self.temperature, dim=1),
            F.softmax(teacher_logits / self.temperature, dim=1),
            reduction='batchmean'
        ) * (self.temperature ** 2)

        # Hard targets reais
        hard_loss = F.cross_entropy(student_logits, labels)

        return 0.7 * soft_loss + 0.3 * hard_loss
```

**Benefício:** Criar versões "lite" para dispositivos móveis

---

### 7. Model Pruning
**Impacto:** 🟡 **30-50% menos parâmetros**

```python
import torch.nn.utils.prune as prune

def prune_model(model, amount=0.3):
    for name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            prune.l1_unstructured(module, name='weight', amount=amount)
            prune.remove(module, 'weight')  # Make permanent
```

**Benefício:** Modelo mais leve sem perda significativa de qualidade

---

### 8. Async Inference no Servidor
**Impacto:** 🟢 **10x mais throughput**

```python
# services/server.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

@app.post("/predict")
async def predict(request: PredictRequest):
    loop = asyncio.get_event_loop()

    # Executar predição em thread separada
    result = await loop.run_in_executor(
        executor,
        AI_PREDICTOR.predict,
        request.image_path
    )

    return result
```

**Benefício:** Servidor pode processar múltiplos pedidos simultaneamente

---

### 9. TensorRT Optimization (NVIDIA GPUs)
**Impacto:** 🟢 **5-10x mais rápido**

```python
import tensorrt as trt

def optimize_with_tensorrt(onnx_path, output_path):
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network()
    parser = trt.OnnxParser(network, logger)

    with open(onnx_path, 'rb') as model:
        parser.parse(model.read())

    config = builder.create_builder_config()
    config.max_workspace_size = 1 << 30  # 1GB
    config.set_flag(trt.BuilderFlag.FP16)  # FP16 precision

    engine = builder.build_engine(network, config)

    with open(output_path, 'wb') as f:
        f.write(engine.serialize())
```

**Benefício:** Inferência extremamente rápida em GPUs NVIDIA

---

### 10. Data Augmentation On-the-Fly
**Impacto:** 🟡 **Melhor generalização**

```python
# services/ai_core/training_utils.py
from torchvision import transforms

class LightroomDataset(Dataset):
    def __init__(self, ..., augment=True):
        self.augment = augment
        self.transform = transforms.Compose([
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.1, contrast=0.1),
            transforms.RandomRotation(5)
        ])

    def __getitem__(self, idx):
        image = self.load_image(idx)
        if self.augment:
            image = self.transform(image)
        return image, label
```

**Benefício:** Modelo mais robusto a variações

---

## 📊 Priorização de Implementação

### 🔴 Prioridade Máxima (Implementar Já)
1. **Mixed Precision Training** - 2-3x speedup, fácil de implementar
2. **Model Quantization** - 4x menor, deploy mais fácil
3. **Async Inference** - Escala melhor em produção

### 🟠 Prioridade Alta (Próxima Iteração)
4. **Feature Caching** - Melhora UX em re-predições
5. **ONNX Export** - Portabilidade
6. **Knowledge Distillation** - Versões lite

### 🟡 Prioridade Média (Futuro)
7. **Gradient Checkpointing** - Útil para datasets grandes
8. **Model Pruning** - Otimização final
9. **Data Augmentation** - Melhora qualidade
10. **TensorRT** - Apenas se GPU NVIDIA disponível

---

## 🎯 Roadmap de Otimização

### Fase 1: Quick Wins (1 semana)
- [ ] Mixed Precision Training
- [ ] Model Quantization
- [ ] Async Inference

**Resultado Esperado:** Treino 2x mais rápido, inferência 3x mais rápida

### Fase 2: Escalabilidade (2 semanas)
- [ ] Feature Caching
- [ ] ONNX Export
- [ ] Batch Inference API

**Resultado Esperado:** Sistema pronto para produção em escala

### Fase 3: Avançado (1 mês)
- [ ] Knowledge Distillation
- [ ] Model Pruning
- [ ] TensorRT (se aplicável)

**Resultado Esperado:** Versões lite para mobile/edge

---

## 📈 Benchmarks Estimados

### Treino (4 Presets, 1000 imagens, RTX 3080)

| Configuração | Tempo | Memória GPU |
|--------------|-------|-------------|
| **Atual** | 45 min | 6 GB |
| **+ Mixed Precision** | 20 min | 3.6 GB |
| **+ Gradient Checkpoint** | 25 min | 2 GB |

### Inferência (1 imagem, CPU M1)

| Configuração | Tempo |
|--------------|-------|
| **Atual (PyTorch)** | 350 ms |
| **+ Quantization** | 120 ms |
| **+ ONNX** | 80 ms |
| **+ Feature Cache** | 15 ms (hit) |

---

## 🔧 Implementação Recomendada

Criar módulo `services/ai_core/optimizations.py`:

```python
class ModelOptimizer:
    @staticmethod
    def apply_mixed_precision(model, optimizer):
        """Aplica AMP ao modelo"""
        pass

    @staticmethod
    def quantize_model(model, calibration_data):
        """Quantiza modelo para INT8"""
        pass

    @staticmethod
    def export_onnx(model, input_shape, output_path):
        """Exporta para ONNX"""
        pass

    @staticmethod
    def prune_model(model, amount=0.3):
        """Remove pesos menos importantes"""
        pass

    @staticmethod
    def distill_model(teacher, student, train_loader):
        """Cria versão lite do modelo"""
        pass
```

---

**Conclusão:** Implementando as otimizações de Prioridade Máxima, consegues:
- **Treino 2-3x mais rápido**
- **Inferência 3-5x mais rápida**
- **Modelos 75% mais pequenos**
- **Sistema pronto para escala comercial**
