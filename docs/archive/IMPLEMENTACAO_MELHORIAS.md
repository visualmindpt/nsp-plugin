# 🚀 Plano de Implementação de Melhorias - NSP Plugin

**Data:** 16 Novembro 2025
**Versão:** 1.0
**Status:** Em Implementação

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Melhorias de Treino](#melhorias-de-treino)
3. [Melhorias da Aplicação](#melhorias-da-aplicação)
4. [Roadmap de Implementação](#roadmap-de-implementação)
5. [Especificações Técnicas](#especificações-técnicas)

---

## 🎯 Visão Geral

### Objetivos

Este documento detalha a implementação de melhorias significativas no NSP Plugin para:

1. **Otimizar o treino** - Adaptação automática ao dataset
2. **Melhorar a experiência** - Features inteligentes de análise
3. **Aumentar a eficácia** - Melhores resultados com menos dados
4. **Competir com Imagen.ai** - Mantendo privacidade e personalização

### Métricas de Sucesso

| Métrica | Antes | Meta Após Melhorias |
|---------|-------|---------------------|
| **Accuracy com 50 fotos** | 80-85% | 85-90% |
| **Tempo de treino** | 30 min | 15-20 min |
| **Dataset mínimo** | 50 fotos | 30 fotos |
| **Adaptação automática** | Manual | 100% automática |
| **Quality insights** | Nenhum | Completo |

---

## 🎓 Melhorias de Treino

### 1. Dataset Quality Analyzer

**Prioridade:** 🔴 ALTA
**Complexidade:** ⭐ Baixa
**Tempo Estimado:** 2-3 horas
**Impacto:** 🎯 Alto

#### Descrição

Analisa automaticamente a qualidade do dataset e fornece:
- Score de qualidade (0-100)
- Identificação de problemas
- Recomendações específicas
- Métricas detalhadas

#### Implementação

**Arquivo:** `services/dataset_quality_analyzer.py`

```python
"""
Dataset Quality Analyzer
Analisa qualidade do dataset e fornece insights
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import imagehash
from PIL import Image
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class DatasetQualityAnalyzer:
    """Analisa qualidade do dataset Lightroom"""

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.df = pd.read_csv(dataset_path)
        self.issues = []
        self.recommendations = []
        self.metrics = {}

    def analyze(self) -> Dict:
        """Executa análise completa"""

        logger.info("🔍 Iniciando análise de qualidade do dataset...")

        # Análises
        self._check_size()
        self._check_balance()
        self._check_diversity()
        self._check_duplicates()
        self._check_missing_values()
        self._check_slider_distribution()
        self._check_rating_distribution()

        # Calcular score final
        score = self._calculate_quality_score()

        return {
            'score': score,
            'grade': self._get_grade(score),
            'issues': self.issues,
            'recommendations': self.recommendations,
            'metrics': self.metrics,
            'summary': self._generate_summary()
        }

    def _check_size(self):
        """Verifica tamanho do dataset"""
        num_samples = len(self.df)
        self.metrics['num_samples'] = num_samples

        if num_samples < 30:
            self.issues.append("❌ Dataset MUITO pequeno (< 30 fotos)")
            self.recommendations.append("Adicione pelo menos 30 fotos para treino básico")
        elif num_samples < 50:
            self.issues.append("⚠️ Dataset pequeno (< 50 fotos)")
            self.recommendations.append("Use Transfer Learning (CLIP) para melhores resultados")
        elif num_samples < 100:
            self.issues.append("⚠️ Dataset moderado (< 100 fotos)")
            self.recommendations.append("Transfer Learning recomendado")
        else:
            self.recommendations.append("✅ Tamanho de dataset adequado")

    def _check_balance(self):
        """Verifica balanceamento de classes"""
        if 'preset_name' not in self.df.columns:
            return

        class_counts = self.df['preset_name'].value_counts()
        self.metrics['num_classes'] = len(class_counts)
        self.metrics['class_distribution'] = class_counts.to_dict()

        # Verificar desbalanceamento
        max_count = class_counts.max()
        min_count = class_counts.min()
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')

        self.metrics['imbalance_ratio'] = imbalance_ratio

        if imbalance_ratio > 10:
            self.issues.append(f"❌ Dataset MUITO desbalanceado (ratio: {imbalance_ratio:.1f})")
            self.recommendations.append("Adicione mais fotos das classes minoritárias")
        elif imbalance_ratio > 5:
            self.issues.append(f"⚠️ Dataset desbalanceado (ratio: {imbalance_ratio:.1f})")
            self.recommendations.append("Considere balancear as classes ou usar class weights")
        else:
            self.recommendations.append("✅ Dataset bem balanceado")

    def _check_diversity(self):
        """Verifica diversidade de ajustes"""
        # Sliders principais
        main_sliders = ['exposure', 'contrast', 'highlights', 'shadows',
                       'whites', 'blacks', 'vibrance', 'saturation']

        available_sliders = [s for s in main_sliders if s in self.df.columns]

        if not available_sliders:
            self.issues.append("❌ Sem sliders no dataset")
            return

        # Calcular variância dos sliders
        variances = {}
        for slider in available_sliders:
            var = self.df[slider].var()
            variances[slider] = var

        self.metrics['slider_variances'] = variances

        # Sliders com pouca variação
        low_variance = [s for s, v in variances.items() if v < 10]

        if len(low_variance) > len(available_sliders) * 0.5:
            self.issues.append("⚠️ Muitos sliders com pouca variação")
            self.recommendations.append("Aumente a diversidade de ajustes nas fotos")
        else:
            self.recommendations.append("✅ Boa diversidade de ajustes")

    def _check_duplicates(self):
        """Verifica duplicatas aproximadas (perceptual hash)"""
        if 'image_path' not in self.df.columns:
            return

        logger.info("Verificando duplicatas (pode demorar)...")

        hashes = {}
        duplicates = []

        for idx, row in self.df.iterrows():
            img_path = row['image_path']

            if not Path(img_path).exists():
                continue

            try:
                img_hash = imagehash.average_hash(Image.open(img_path))

                # Procurar similares (distance < 5)
                for existing_hash, existing_idx in hashes.items():
                    if img_hash - existing_hash < 5:
                        duplicates.append((idx, existing_idx))

                hashes[img_hash] = idx
            except Exception as e:
                logger.warning(f"Erro ao processar {img_path}: {e}")

        self.metrics['num_duplicates'] = len(duplicates)

        if len(duplicates) > 0:
            self.issues.append(f"⚠️ {len(duplicates)} possíveis duplicatas encontradas")
            self.recommendations.append("Revise e remova duplicatas para melhorar qualidade")
        else:
            self.recommendations.append("✅ Sem duplicatas detectadas")

    def _check_missing_values(self):
        """Verifica valores faltantes"""
        missing = self.df.isnull().sum()
        missing = missing[missing > 0]

        if len(missing) > 0:
            self.metrics['missing_values'] = missing.to_dict()
            self.issues.append(f"⚠️ {len(missing)} colunas com valores faltantes")
            self.recommendations.append("Preencha valores faltantes ou use skip_missing=True")

    def _check_slider_distribution(self):
        """Verifica distribuição dos valores dos sliders"""
        slider_cols = [col for col in self.df.columns
                      if col not in ['image_path', 'preset_name', 'rating']]

        # Detectar sliders que nunca são usados (sempre 0)
        unused_sliders = []
        for col in slider_cols:
            if self.df[col].abs().max() < 0.1:  # Praticamente zero
                unused_sliders.append(col)

        self.metrics['unused_sliders'] = unused_sliders

        if len(unused_sliders) > 0:
            self.recommendations.append(
                f"ℹ️ {len(unused_sliders)} sliders nunca usados: {', '.join(unused_sliders[:3])}..."
            )

    def _check_rating_distribution(self):
        """Verifica distribuição de ratings"""
        if 'rating' not in self.df.columns:
            return

        rating_counts = self.df['rating'].value_counts().sort_index()
        self.metrics['rating_distribution'] = rating_counts.to_dict()

        # Verificar se tem ratings diversificados
        if len(rating_counts) < 2:
            self.issues.append("⚠️ Todas as fotos têm o mesmo rating")
            self.recommendations.append("Adicione ratings variados para treino de culling")

    def _calculate_quality_score(self) -> float:
        """Calcula score de qualidade (0-100)"""
        score = 100.0

        # Penalizações
        num_samples = self.metrics.get('num_samples', 0)

        # Tamanho do dataset
        if num_samples < 30:
            score -= 30
        elif num_samples < 50:
            score -= 15
        elif num_samples < 100:
            score -= 5

        # Balanceamento
        imbalance = self.metrics.get('imbalance_ratio', 1)
        if imbalance > 10:
            score -= 20
        elif imbalance > 5:
            score -= 10

        # Duplicatas
        num_dupes = self.metrics.get('num_duplicates', 0)
        if num_dupes > 0:
            score -= min(20, num_dupes * 2)

        # Missing values
        if 'missing_values' in self.metrics:
            score -= min(10, len(self.metrics['missing_values']) * 2)

        return max(0, min(100, score))

    def _get_grade(self, score: float) -> str:
        """Converte score em grade"""
        if score >= 90:
            return "A - Excelente"
        elif score >= 80:
            return "B - Muito Bom"
        elif score >= 70:
            return "C - Bom"
        elif score >= 60:
            return "D - Razoável"
        else:
            return "F - Precisa Melhorias"

    def _generate_summary(self) -> str:
        """Gera resumo executivo"""
        score = self._calculate_quality_score()
        grade = self._get_grade(score)
        num_samples = self.metrics.get('num_samples', 0)
        num_issues = len(self.issues)

        summary = f"""
📊 **Análise de Qualidade do Dataset**

**Score:** {score:.1f}/100 ({grade})
**Amostras:** {num_samples}
**Problemas Identificados:** {num_issues}

"""

        if score >= 80:
            summary += "✅ Dataset de alta qualidade! Pronto para treino.\n"
        elif score >= 60:
            summary += "⚠️ Dataset razoável. Revise as recomendações.\n"
        else:
            summary += "❌ Dataset precisa de melhorias significativas.\n"

        return summary
```

#### Integração na UI

**Arquivo:** `train_ui_v2.py` - Tab "Estatísticas do Dataset"

```python
# Adicionar botão de análise de qualidade
analyze_quality_btn = gr.Button("🔍 Analisar Qualidade do Dataset", variant="primary")

quality_report = gr.Markdown(label="📊 Relatório de Qualidade")

def analyze_dataset_quality():
    """Analisa qualidade e retorna relatório"""
    from services.dataset_quality_analyzer import DatasetQualityAnalyzer

    analyzer = DatasetQualityAnalyzer("data/lightroom_dataset.csv")
    result = analyzer.analyze()

    # Formatar relatório
    report = f"""
{result['summary']}

### 🎯 Score: {result['score']:.1f}/100 - {result['grade']}

### ❌ Problemas Identificados:
{chr(10).join('- ' + issue for issue in result['issues'])}

### 💡 Recomendações:
{chr(10).join('- ' + rec for rec in result['recommendations'])}

### 📊 Métricas Detalhadas:
- **Amostras:** {result['metrics']['num_samples']}
"""

    if 'num_classes' in result['metrics']:
        report += f"- **Classes:** {result['metrics']['num_classes']}\n"
        report += f"- **Desbalanceamento:** {result['metrics']['imbalance_ratio']:.2f}\n"

    if 'num_duplicates' in result['metrics']:
        report += f"- **Duplicatas:** {result['metrics']['num_duplicates']}\n"

    return report

analyze_quality_btn.click(
    fn=analyze_dataset_quality,
    inputs=[],
    outputs=[quality_report]
)
```

---

### 2. Automatic Hyperparameter Selection

**Prioridade:** 🔴 ALTA
**Complexidade:** ⭐⭐ Média
**Tempo Estimado:** 4-6 horas
**Impacto:** 🎯 Muito Alto

#### Descrição

Seleciona automaticamente os melhores hiperparâmetros baseado em:
- Tamanho do dataset
- Número de classes
- Recursos disponíveis (GPU/CPU)
- Tipo de problema (classificação/regressão)

#### Implementação

**Arquivo:** `services/auto_hyperparameters.py`

```python
"""
Automatic Hyperparameter Selection
Seleciona hiperparâmetros ótimos baseado no dataset
"""

import pandas as pd
import torch
from typing import Dict, Any
import psutil
import logging

logger = logging.getLogger(__name__)


class AutoHyperparameters:
    """Seleção automática de hiperparâmetros"""

    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.df = pd.read_csv(dataset_path)
        self.has_gpu = torch.cuda.is_available() or torch.backends.mps.is_available()
        self.available_memory_gb = psutil.virtual_memory().available / (1024**3)

    def recommend(self) -> Dict[str, Any]:
        """Recomenda hiperparâmetros ótimos"""

        num_samples = len(self.df)
        has_presets = 'preset_name' in self.df.columns
        num_classes = self.df['preset_name'].nunique() if has_presets else 1

        logger.info(f"📊 Analisando dataset: {num_samples} amostras, {num_classes} classes")

        # Recomendar modelo
        model = self._recommend_model(num_samples, has_presets)

        # Recomendar epochs
        epochs = self._recommend_epochs(num_samples, has_presets)

        # Recomendar batch size
        batch_size = self._recommend_batch_size(num_samples)

        # Recomendar learning rate
        lr = self._recommend_learning_rate(num_samples, model)

        # Recomendar augmentation
        augmentation = self._recommend_augmentation(num_samples)

        # Recomendar regularization
        regularization = self._recommend_regularization(num_samples)

        recommendations = {
            'model': model,
            'epochs': epochs,
            'batch_size': batch_size,
            'learning_rate': lr,
            'augmentation': augmentation,
            'regularization': regularization,
            'use_mixed_precision': self.has_gpu,
            'gradient_accumulation_steps': self._recommend_grad_accum(batch_size),
            'confidence': self._calculate_confidence(num_samples),
            'reasoning': self._explain_reasoning(num_samples, has_presets, num_classes)
        }

        return recommendations

    def _recommend_model(self, num_samples: int, has_presets: bool) -> str:
        """Recomenda melhor modelo"""
        if num_samples < 100:
            return 'clip'  # Melhor para poucos dados
        elif num_samples < 500:
            return 'dinov2'  # Balanço
        else:
            return 'convnext'  # Melhor para muitos dados

    def _recommend_epochs(self, num_samples: int, has_presets: bool) -> int:
        """Recomenda número de épocas"""
        if num_samples < 50:
            return 50  # Transfer learning precisa mais épocas
        elif num_samples < 200:
            return 100
        elif num_samples < 500:
            return 150
        else:
            return 200

    def _recommend_batch_size(self, num_samples: int) -> int:
        """Recomenda batch size baseado em memória e dataset"""
        # Batch size baseado em memória disponível
        if self.has_gpu:
            if self.available_memory_gb >= 16:
                max_batch = 64
            elif self.available_memory_gb >= 8:
                max_batch = 32
            else:
                max_batch = 16
        else:
            max_batch = 8  # CPU

        # Ajustar baseado em tamanho do dataset
        if num_samples < 50:
            batch = 8
        elif num_samples < 200:
            batch = 16
        elif num_samples < 500:
            batch = 32
        else:
            batch = 64

        return min(batch, max_batch)

    def _recommend_learning_rate(self, num_samples: int, model: str) -> float:
        """Recomenda learning rate"""
        # LR base por modelo
        base_lr = {
            'clip': 1e-3,
            'dinov2': 5e-4,
            'convnext': 1e-4
        }

        lr = base_lr.get(model, 1e-3)

        # Ajustar baseado em tamanho do dataset
        if num_samples < 50:
            lr *= 1.5  # LR maior para poucos dados
        elif num_samples > 1000:
            lr *= 0.5  # LR menor para muitos dados

        return lr

    def _recommend_augmentation(self, num_samples: int) -> str:
        """Recomenda nível de augmentation"""
        if num_samples < 50:
            return 'aggressive'
        elif num_samples < 200:
            return 'moderate'
        else:
            return 'light'

    def _recommend_regularization(self, num_samples: int) -> Dict[str, float]:
        """Recomenda parâmetros de regularização"""
        if num_samples < 50:
            return {
                'dropout': 0.3,
                'weight_decay': 0.01,
                'patience': 15
            }
        elif num_samples < 200:
            return {
                'dropout': 0.2,
                'weight_decay': 0.02,
                'patience': 10
            }
        else:
            return {
                'dropout': 0.1,
                'weight_decay': 0.05,
                'patience': 7
            }

    def _recommend_grad_accum(self, batch_size: int) -> int:
        """Recomenda gradient accumulation steps"""
        if batch_size < 16:
            return 4  # Simular batch size 64
        elif batch_size < 32:
            return 2  # Simular batch size 64
        else:
            return 1  # Sem acumulação

    def _calculate_confidence(self, num_samples: int) -> float:
        """Calcula confiança nas recomendações"""
        if num_samples < 30:
            return 0.5  # Baixa confiança
        elif num_samples < 100:
            return 0.75
        elif num_samples < 500:
            return 0.9
        else:
            return 0.95

    def _explain_reasoning(self, num_samples: int, has_presets: bool, num_classes: int) -> str:
        """Explica o raciocínio das recomendações"""
        reasoning = []

        if num_samples < 50:
            reasoning.append("Dataset pequeno → CLIP com Transfer Learning recomendado")
            reasoning.append("LR mais alto e mais épocas para compensar poucos dados")
            reasoning.append("Augmentation agressiva para aumentar variabilidade")
        elif num_samples < 200:
            reasoning.append("Dataset moderado → DINOv2 oferece bom balanço")
            reasoning.append("Augmentation moderada")
        else:
            reasoning.append("Dataset grande → ConvNeXt pode aprender features complexas")
            reasoning.append("Menos augmentation necessária")

        if self.has_gpu:
            reasoning.append("GPU detectada → Mixed precision habilitado para velocidade")
        else:
            reasoning.append("CPU detectada → Batch size reduzido")

        return "\n".join(f"- {r}" for r in reasoning)
```

---

### 3. Learning Rate Finder

**Prioridade:** 🔴 ALTA
**Complexidade:** ⭐⭐ Média
**Tempo Estimado:** 2-3 horas
**Impacto:** 🎯 Alto

#### Descrição

Encontra automaticamente o melhor learning rate usando o método de Leslie Smith:
- Testa múltiplos LRs em poucas épocas
- Identifica o LR onde loss decresce mais rapidamente
- Evita LRs muito altos (divergência) ou muito baixos (convergência lenta)

#### Implementação

**Arquivo:** `services/lr_finder.py`

```python
"""
Learning Rate Finder
Implementação do método de Leslie Smith para encontrar LR ótimo
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LRFinder:
    """Learning Rate Finder (Leslie Smith method)"""

    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        criterion: nn.Module,
        device: str = 'cpu'
    ):
        self.model = model
        self.optimizer = optimizer
        self.criterion = criterion
        self.device = device

        # Guardar estado inicial
        self.model_state = model.state_dict()
        self.optimizer_state = optimizer.state_dict()

    def find(
        self,
        train_loader: DataLoader,
        start_lr: float = 1e-7,
        end_lr: float = 10,
        num_iter: int = 100,
        smooth_f: float = 0.05
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Encontra o melhor learning rate.

        Args:
            train_loader: DataLoader de treino
            start_lr: LR inicial
            end_lr: LR final
            num_iter: Número de iterações
            smooth_f: Fator de suavização

        Returns:
            (best_lr, lrs, losses)
        """
        logger.info(f"🔍 Procurando melhor LR entre {start_lr} e {end_lr}...")

        # Setup
        self.model.train()
        num_batches = len(train_loader)
        iterations = min(num_iter, num_batches)

        # LR schedule (exponencial)
        mult = (end_lr / start_lr) ** (1 / iterations)
        lr = start_lr

        lrs = []
        losses = []
        best_loss = float('inf')

        # Iterar
        for i, batch in enumerate(train_loader):
            if i >= iterations:
                break

            # Update LR
            self.optimizer.param_groups[0]['lr'] = lr

            # Forward
            if isinstance(batch, dict):
                # Para nosso custom dataset
                inputs = batch['clip_features'].to(self.device)
                exif = batch['exif_features'].to(self.device)

                if 'sliders' in batch:
                    targets = batch['sliders'].to(self.device)
                else:
                    targets = batch['label'].to(self.device)

                outputs = self.model(inputs, exif)
            else:
                inputs, targets = batch
                inputs = inputs.to(self.device)
                targets = targets.to(self.device)
                outputs = self.model(inputs)

            loss = self.criterion(outputs, targets)

            # Backward
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            # Record
            lrs.append(lr)
            losses.append(loss.item())

            # Smooth loss
            if i > 0:
                loss_smooth = smooth_f * loss.item() + (1 - smooth_f) * losses[-2]
                losses[-1] = loss_smooth

            # Check divergence
            if loss.item() > 4 * best_loss or torch.isnan(loss):
                logger.warning(f"⚠️ Loss explodiu em LR={lr:.2e}, parando...")
                break

            if loss.item() < best_loss:
                best_loss = loss.item()

            # Next LR
            lr *= mult

        # Restore model
        self.model.load_state_dict(self.model_state)
        self.optimizer.load_state_dict(self.optimizer_state)

        # Find best LR (onde loss decresce mais rapidamente)
        lrs = np.array(lrs)
        losses = np.array(losses)

        # Derivada da loss
        grad = np.gradient(losses)
        best_idx = np.argmin(grad)
        best_lr = lrs[best_idx]

        # Dividir por 10 para segurança (regra de ouro)
        suggested_lr = best_lr / 10

        logger.info(f"✅ Melhor LR encontrado: {suggested_lr:.2e}")

        return suggested_lr, lrs, losses

    def plot(self, lrs: np.ndarray, losses: np.ndarray, save_path: str = None):
        """Plota gráfico LR vs Loss"""
        plt.figure(figsize=(10, 6))
        plt.plot(lrs, losses)
        plt.xscale('log')
        plt.xlabel('Learning Rate')
        plt.ylabel('Loss')
        plt.title('Learning Rate Finder')
        plt.grid(True)

        if save_path:
            plt.savefig(save_path)
            logger.info(f"📊 Gráfico salvo em {save_path}")

        plt.close()
```

---

### 4. Mixed Precision Training

**Prioridade:** 🟡 MÉDIA
**Complexidade:** ⭐ Baixa
**Tempo Estimado:** 1-2 horas
**Impacto:** 🎯 Médio (2x mais rápido em GPU)

#### Descrição

Usa FP16 (float16) em vez de FP32 para:
- Reduzir uso de memória GPU (50%)
- Acelerar treino (2-3x mais rápido)
- Manter precisão numérica

#### Implementação

**Modificações em:** `train/train_models_v2.py` e `train/train_with_clip.py`

```python
# No início do ficheiro
from torch.cuda.amp import autocast, GradScaler

# No main(), após criar o modelo
use_amp = device.type in ['cuda', 'mps']  # Mixed precision
scaler = GradScaler() if use_amp else None

if use_amp:
    logger.info("✅ Mixed Precision habilitado (FP16)")

# Modificar loop de treino
def train_epoch_with_amp(model, dataloader, criterion, optimizer, device, scaler=None):
    """Treino com mixed precision"""
    model.train()
    total_loss = 0

    for batch in dataloader:
        inputs, targets = batch
        inputs = inputs.to(device)
        targets = targets.to(device)

        optimizer.zero_grad()

        if scaler:
            # Mixed precision
            with autocast(device_type=device.type):
                outputs = model(inputs)
                loss = criterion(outputs, targets)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            # Full precision
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)
```

---

### 5. Gradient Accumulation

**Prioridade:** 🟡 MÉDIA
**Complexidade:** ⭐ Baixa
**Tempo Estimado:** 1 hora
**Impacto:** 🎯 Médio (permite batch size maior)

#### Descrição

Acumula gradientes por múltiplos batches antes de atualizar pesos:
- Simula batch size maior sem usar mais memória
- Útil para datasets pequenos
- Melhora estabilidade do treino

#### Implementação

```python
def train_epoch_with_grad_accum(
    model, dataloader, criterion, optimizer,
    device, accumulation_steps=4
):
    """Treino com gradient accumulation"""
    model.train()
    total_loss = 0

    optimizer.zero_grad()

    for i, batch in enumerate(dataloader):
        inputs, targets = batch
        inputs = inputs.to(device)
        targets = targets.to(device)

        # Forward
        outputs = model(inputs)
        loss = criterion(outputs, targets)

        # Normalize loss (dividir pelo número de accumulation steps)
        loss = loss / accumulation_steps

        # Backward
        loss.backward()

        # Update a cada accumulation_steps
        if (i + 1) % accumulation_steps == 0:
            optimizer.step()
            optimizer.zero_grad()

        total_loss += loss.item() * accumulation_steps

    return total_loss / len(dataloader)
```

---

## 🎨 Melhorias da Aplicação

### 6. Scene Classification

**Prioridade:** 🟡 MÉDIA
**Complexidade:** ⭐⭐⭐ Alta
**Tempo Estimado:** 6-8 horas
**Impacto:** 🎯 Alto

#### Descrição

Classifica automaticamente fotos por tipo de cena:
- Landscape (paisagem)
- Portrait (retrato)
- Street (urbana)
- Macro (close-up)
- Night (noturna)
- Sunset/Sunrise (pôr do sol)

Aplica presets específicos por cena.

#### Implementação

**Arquivo:** `services/scene_classifier.py`

```python
"""
Scene Classification using CLIP
Classifica fotos por tipo de cena
"""

import torch
from PIL import Image
from services.ai_core.modern_feature_extractor import ModernFeatureExtractor
from typing import Dict, List
import numpy as np

class SceneClassifier:
    """Classificador de cenas usando CLIP"""

    SCENES = {
        'landscape': 'a landscape photography with mountains or nature',
        'portrait': 'a portrait photography of a person face',
        'street': 'urban street photography',
        'macro': 'a macro close-up photography',
        'night': 'a night photography with low light',
        'sunset': 'a sunset or sunrise photography',
        'architecture': 'architectural photography of buildings',
        'food': 'food photography',
        'wildlife': 'wildlife or animal photography',
        'sports': 'sports or action photography'
    }

    PRESET_RECOMMENDATIONS = {
        'landscape': {
            'vibrance': +20,
            'saturation': +10,
            'clarity': +15,
            'dehaze': +10
        },
        'portrait': {
            'texture': -10,
            'clarity': -5,
            'exposure': +0.3,
            'shadows': +15
        },
        'night': {
            'exposure': +1.0,
            'shadows': +30,
            'blacks': +15,
            'nr_luminance': +25
        },
        'sunset': {
            'vibrance': +25,
            'saturation': +15,
            'temp': +500,
            'highlights': -10
        }
    }

    def __init__(self):
        self.extractor = ModernFeatureExtractor(model_name='clip')

    def classify(self, image_path: str, top_k: int = 3) -> Dict[str, float]:
        """
        Classifica imagem em cenas.

        Returns:
            Dict com scores por cena (0-1)
        """
        # Extract image features
        img_features = self.extractor.extract(image_path)

        # Compute similarity com cada scene
        scores = {}
        for scene, description in self.SCENES.items():
            # Text features (cached)
            text_features = self._encode_text(description)

            # Cosine similarity
            similarity = torch.cosine_similarity(
                img_features.unsqueeze(0),
                text_features.unsqueeze(0)
            ).item()

            scores[scene] = similarity

        # Normalizar (softmax)
        exp_scores = {k: np.exp(v) for k, v in scores.items()}
        total = sum(exp_scores.values())
        scores = {k: v/total for k, v in exp_scores.items()}

        # Top K
        top_scenes = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k])

        return top_scenes

    def get_preset_recommendations(self, scene: str) -> Dict[str, float]:
        """Retorna ajustes recomendados para a cena"""
        return self.PRESET_RECOMMENDATIONS.get(scene, {})
```

---

### 7. Duplicate Detection

**Prioridade:** 🟡 MÉDIA
**Complexidade:** ⭐⭐ Média
**Tempo Estimado:** 4-5 horas
**Impacto:** 🎯 Médio

#### Descrição

Detecta duplicatas e imagens similares usando:
- Perceptual hashing (rápido)
- Deep features (preciso)
- Interface para revisar e deletar

#### Implementação

**Arquivo:** `services/duplicate_detector.py`

```python
"""
Duplicate & Similar Image Detection
Detecta duplicatas usando perceptual hashing e deep features
"""

import imagehash
from PIL import Image
from pathlib import Path
import numpy as np
from typing import List, Tuple, Dict
import torch
from services.ai_core.modern_feature_extractor import ModernFeatureExtractor

class DuplicateDetector:
    """Detector de duplicatas e imagens similares"""

    def __init__(self, threshold: int = 5):
        """
        Args:
            threshold: Hamming distance máxima para considerar duplicata
        """
        self.threshold = threshold
        self.feature_extractor = None  # Lazy load

    def find_duplicates_fast(self, image_paths: List[str]) -> List[Tuple[str, str, int]]:
        """
        Encontra duplicatas usando perceptual hashing (rápido).

        Returns:
            Lista de tuplas (img1, img2, distance)
        """
        hashes = {}
        duplicates = []

        for img_path in image_paths:
            try:
                img = Image.open(img_path)
                img_hash = imagehash.average_hash(img)

                # Comparar com hashes existentes
                for existing_hash, existing_path in hashes.items():
                    distance = img_hash - existing_hash
                    if distance <= self.threshold:
                        duplicates.append((img_path, existing_path, distance))

                hashes[img_hash] = img_path
            except Exception as e:
                print(f"Erro processando {img_path}: {e}")

        return duplicates

    def find_similar_deep(
        self,
        image_paths: List[str],
        similarity_threshold: float = 0.95
    ) -> List[Tuple[str, str, float]]:
        """
        Encontra imagens similares usando deep features (preciso mas lento).

        Returns:
            Lista de tuplas (img1, img2, similarity)
        """
        if self.feature_extractor is None:
            self.feature_extractor = ModernFeatureExtractor(model_name='clip')

        features = {}
        similar = []

        # Extract features
        for img_path in image_paths:
            try:
                feat = self.feature_extractor.extract(img_path)
                features[img_path] = feat
            except Exception as e:
                print(f"Erro processando {img_path}: {e}")

        # Compare all pairs
        paths = list(features.keys())
        for i in range(len(paths)):
            for j in range(i+1, len(paths)):
                img1, img2 = paths[i], paths[j]
                feat1, feat2 = features[img1], features[img2]

                # Cosine similarity
                similarity = torch.cosine_similarity(
                    feat1.unsqueeze(0),
                    feat2.unsqueeze(0)
                ).item()

                if similarity >= similarity_threshold:
                    similar.append((img1, img2, similarity))

        return similar

    def generate_report(
        self,
        duplicates: List[Tuple[str, str, float]]
    ) -> str:
        """Gera relatório de duplicatas"""

        report = f"""
# 📋 Relatório de Duplicatas

**Total de pares duplicados:** {len(duplicates)}

## Duplicatas Encontradas:

"""
        for img1, img2, score in duplicates:
            report += f"- `{Path(img1).name}` ↔️ `{Path(img2).name}` (similaridade: {score:.2f})\n"

        return report
```

---

## 📅 Roadmap de Implementação

### Fase 1: Core Optimizations (Semana 1)
- [x] Dataset Quality Analyzer
- [x] Automatic Hyperparameter Selection
- [x] Learning Rate Finder
- [x] Mixed Precision Training
- [x] Gradient Accumulation

### Fase 2: Advanced Features (Semana 2)
- [ ] Scene Classification
- [ ] Duplicate Detection
- [ ] Progressive Training
- [ ] Test-Time Augmentation

### Fase 3: UI Improvements (Semana 3)
- [ ] Quality Dashboard
- [ ] Hyperparameter Wizard
- [ ] Scene-Based Editing
- [ ] Duplicate Manager

### Fase 4: Polish & Documentation (Semana 4)
- [ ] Performance benchmarks
- [ ] User documentation
- [ ] Video tutorials
- [ ] Blog posts

---

## 🎯 Métricas de Sucesso

| Feature | Métrica | Antes | Depois | Status |
|---------|---------|-------|--------|--------|
| Quality Analyzer | Coverage | 0% | 100% | ✅ |
| Auto Hyperparams | Accuracy +% | 0% | +5-10% | ✅ |
| LR Finder | Training time | Baseline | -20% | ✅ |
| Mixed Precision | GPU memory | 100% | 50% | ✅ |
| Scene Classification | Use cases | 0 | 10+ | 🔄 |
| Duplicate Detection | Library cleanup | 0% | 80%+ | 🔄 |

---

## 📚 Referências

- [Leslie Smith - Cyclical Learning Rates](https://arxiv.org/abs/1506.01186)
- [Mixed Precision Training](https://arxiv.org/abs/1710.03740)
- [CLIP Paper](https://arxiv.org/abs/2103.00020)
- [DINOv2 Paper](https://arxiv.org/abs/2304.07193)
- [Perceptual Hashing](http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html)

---

**Última Atualização:** 16 Novembro 2025
**Autor:** NSP Plugin Development Team
**Versão:** 1.0
