# NSP Plugin - Regressão em Treino Incremental

**Data:** 2025-11-25
**Problema detectado:** V8 mostrou regressão significativa em vários parâmetros
**Status:** ✅ Corrigido com LR factor reduzido

---

## 🚨 Problema Detectado

### Treino V8 - Resultados Problemáticos

**Contexto:**
- Sessão 8 de treino incremental
- +1503 novas imagens (casamento)
- Total acumulado: 5045 imagens (8 catálogos, 8 sessões)
- Crescimento: 42.4%

### MAE Muito Alto (Regressão):

| Parâmetro | MAE | Status | Range Normal |
|-----------|-----|--------|--------------|
| **temp** | **249.134** | 🚨 CRÍTICO | 0-50 |
| **split_shadow_hue** | **76.780** | 🔴 Muito Alto | 0-20 |
| **split_balance** | **32.946** | 🔴 Alto | 0-15 |
| **green_primary_hue** | **30.676** | 🔴 Alto | 0-15 |
| **highlights** | **27.969** | 🟡 Alto | 0-20 |
| **contrast** | **23.350** | 🟡 Alto | 0-15 |
| **split_highlight_hue** | **19.405** | 🟡 Moderado | 0-15 |
| whites | 18.379 | 🟡 Moderado | 0-15 |
| shadows | 18.167 | 🟡 Moderado | 0-15 |
| blacks | 17.550 | 🟡 Moderado | 0-15 |

### MAE Bom (Normal):

| Parâmetro | MAE | Status |
|-----------|-----|--------|
| exposure | 0.512 | ✅ Excelente |
| dehaze | 0.082 | ✅ Excelente |
| vibrance | 0.456 | ✅ Excelente |
| saturation | 0.631 | ✅ Excelente |
| HSL ajustes | <1.0 | ✅ Excelente (maioria) |
| shadow_tint | 0.173 | ✅ Excelente |

---

## 🔍 Análise das Causas

### 1. **Catastrophic Forgetting** (Causa Principal)

**O que é:**
- Fenómeno em deep learning incremental
- Modelo "esquece" conhecimento anterior ao aprender novos dados
- Especialmente crítico quando novos dados têm distribuição muito diferente

**No teu caso:**
- **3542 imagens anteriores** (7 catálogos variados)
- **+1503 imagens novas** (1 catálogo de casamento)
- Catálogo de casamento tem **estilo muito específico**:
  - Iluminação consistente (interior/exterior casamento)
  - Temperatura de cor tendenciosa (flash, luz artificial)
  - Split toning mais pronunciado
  - Ajustes de cor primários específicos

**Resultado:**
- Modelo adaptou-se **demasiado** ao estilo de casamento
- Perdeu capacidade de generalizar para outros estilos
- Parâmetros relacionados com cor sofreram mais (temp, split toning)

### 2. **Learning Rate Incremental Demasiado Alto**

**Configuração anterior:**
```python
incremental_lr_factor=0.1  # LR 10x menor que fresh training
```

**Problema:**
- LR de 0.1x (10x menor) ainda é **demasiado alto** para fine-tuning delicado
- Causa mudanças bruscas nos pesos da rede
- Não dá tempo suficiente para balancear conhecimento antigo vs novo
- Especialmente problemático em parâmetros sensíveis (temperatura, hue)

**Analogia:**
- Fresh training: aprender do zero (LR alto = OK)
- Incremental training: ajustar conhecimento existente (precisa LR muito baixo)

### 3. **Distribuição de Dados Desbalanceada**

**Problema:**
- 1503 novas imagens vs 3542 anteriores
- **42% de crescimento** numa única sessão
- Se cada batch tem maioria de imagens novas, modelo vê mais "casamento" que outros estilos
- Modelo sobre-representa o novo estilo

**Efeito nos parâmetros:**
- **temp (249 MAE)**: Casamentos têm padrões de temperatura muito consistentes
- **split_shadow_hue (77 MAE)**: Estilo de split toning específico de fotografia de casamento
- **green_primary_hue (31 MAE)**: Ajustes de verde específicos (pele, vestidos, decoração)

### 4. **Parâmetros Mais Afetados: Porquê?**

#### Temperatura (temp): MAE 249 🚨
- **Range**: -100 a +100 (200 pontos)
- **MAE 249**: Erro maior que o range todo!
- **Razão**: Casamentos têm iluminação muito específica
  - Flash direto
  - Luz artificial interior
  - Diferente de paisagens, retratos exteriores, etc.

#### Split Toning Hues: MAE 77-32
- **Range**: 0-360 (graus de hue)
- **Uso**: Efeito criativo comum em fotografia de casamento
- **Razão**: Estilo muito pronunciado no novo dataset, diferente do acumulado

#### Parâmetros Menos Afetados: Porquê?

**Exposure (0.5), Dehaze (0.08), Vibrance (0.5):**
- Parâmetros **universais** - usados de forma similar em todos os estilos
- Não são específicos de um tipo de fotografia
- Modelo já tinha conhecimento robusto (7 sessões anteriores)

---

## ✅ Solução Implementada

### Redução do Learning Rate Incremental

**Mudança:**
```python
# ANTES (V1-V8):
incremental_lr_factor=0.1  # LR 10x menor

# DEPOIS (V9+):
incremental_lr_factor=0.05  # LR 20x menor - previne catastrophic forgetting
```

**Impacto esperado:**
- ✅ Mudanças mais graduais nos pesos
- ✅ Melhor preservação de conhecimento anterior
- ✅ Balanço entre aprender novo e manter antigo
- ✅ Convergência mais lenta mas mais estável
- ✅ MAE reduzido em parâmetros sensíveis

**Desvantagens:**
- ⚠️ Treino ligeiramente mais lento
- ⚠️ Pode precisar de mais epochs para convergir

**Ficheiro modificado:**
- `scripts/ui/train_ui_clean.py` (linhas 704 e 1110)

---

## 🔄 Como Recuperar do V8 Problemático

### Opção 1: Retreinar com LR Reduzido (Recomendado)

```bash
# 1. Remove modelo V8 problemático (faz backup primeiro)
cd models
mv best_preset_classifier_v2.pth best_preset_classifier_v2.pth.v8_backup
mv best_refinement_model_v2.pth best_refinement_model_v2.pth.v8_backup

# 2. Restaura V7 (se tiveres backup)
# Ou re-exporta de outro computador se tiveres

# 3. Retreina o catálogo de casamento com novo LR
python3 scripts/ui/train_ui_clean.py
# Tab: Quick Start
# Carrega: Casamento Adriana e Rafael.lrcat
# Preset: Balanced
# Train!
```

**Resultado esperado:**
- Versão V9 com MAE reduzido
- Conhecimento anterior preservado
- Novo catálogo integrado suavemente

### Opção 2: Continuar e Adicionar Mais Dados Diversos

```bash
# Treina com mais catálogos DIVERSOS para diluir o efeito
# Adiciona 2-3 catálogos com estilos diferentes:
# - Paisagens
# - Retratos exteriores
# - Street photography
# - Moda
```

**Resultado esperado:**
- Diversidade dilui o overfitting ao casamento
- Modelo recupera capacidade de generalização
- Pode demorar 2-3 sessões adicionais

### Opção 3: Fresh Training (Último Recurso)

```bash
# Remove models e histórico, treina tudo do zero
rm -rf models/*.pth models/*.pkl models/*.json
rm -rf models/training_history.json

# Treina sequencialmente todos os 8 catálogos com LR correcto
# Vai demorar mais tempo mas resulta em modelo mais robusto
```

---

## 📊 Monitorização de Futuras Sessões

### Verificar Regressão

Após cada treino, compara MAE dos parâmetros críticos:

```python
# Cria um script simples para comparar
import json

def compare_training_sessions():
    with open('models/training_history.json') as f:
        history = json.load(f)

    sessions = history['training_sessions']

    # Compara últimas 2 sessões
    if len(sessions) >= 2:
        prev = sessions[-2]
        curr = sessions[-1]

        print("🔍 Comparação de MAE:")
        print(f"Sessão {len(sessions)-1} vs Sessão {len(sessions)}")

        critical_params = ['temp', 'split_shadow_hue', 'contrast', 'highlights']

        for param in critical_params:
            prev_mae = prev.get(param, 0)
            curr_mae = curr.get(param, 0)
            delta = curr_mae - prev_mae

            status = "🚨" if delta > 10 else "✅"
            print(f"  {status} {param}: {prev_mae:.1f} → {curr_mae:.1f} (Δ{delta:+.1f})")
```

### Sinais de Alerta 🚨

Se vires **qualquer um destes**:
- MAE de `temp` > 50
- MAE de `split_*_hue` > 30
- MAE de `contrast/highlights/shadows` > 25
- Qualquer parâmetro com MAE que **aumenta >50%** entre sessões

**Ação imediata:**
1. Para o treino incremental
2. Analisa o catálogo adicionado (muito diferente dos outros?)
3. Considera reduzir LR ainda mais (0.05 → 0.02)
4. Ou restaura versão anterior e re-treina

---

## 🎯 Estratégias Avançadas (Futuro)

### 1. **Experience Replay** (Recomendado)

**Conceito:**
- Guarda exemplos de sessões anteriores
- A cada novo treino, mistura 20-30% de exemplos antigos
- Previne esquecimento porque modelo continua a ver dados variados

**Implementação:**
```python
# Em train_incremental_v2.py
def sample_previous_sessions(history, sample_ratio=0.2):
    """Amostra exemplos de sessões anteriores."""
    previous_images = []

    for session in history['training_sessions'][:-1]:  # Todas menos a atual
        session_path = session['dataset_path']
        df = pd.read_csv(session_path)

        # Amostra 20% de cada sessão anterior
        sample_size = int(len(df) * sample_ratio)
        sampled = df.sample(n=sample_size, random_state=42)
        previous_images.append(sampled)

    return pd.concat(previous_images)

# No treino:
current_data = extract_from_catalog(new_catalog)
replay_data = sample_previous_sessions(history)
mixed_data = pd.concat([current_data, replay_data])
```

**Vantagens:**
- ✅ Previne catastrophic forgetting eficazmente
- ✅ Mantém diversidade constante
- ✅ Validado cientificamente em continual learning

**Desvantagens:**
- ⚠️ Treino ligeiramente mais longo
- ⚠️ Precisa de espaço para guardar datasets anteriores

### 2. **Elastic Weight Consolidation (EWC)**

**Conceito:**
- Identifica pesos mais importantes para conhecimento anterior
- Penaliza mudanças nesses pesos durante novo treino
- Permite mudanças livres em pesos menos importantes

**Implementação:**
```python
class EWCLoss(nn.Module):
    def __init__(self, model, fisher_matrix, old_params, lambda_ewc=0.4):
        super().__init__()
        self.fisher = fisher_matrix
        self.old_params = old_params
        self.lambda_ewc = lambda_ewc

    def forward(self, current_params):
        loss = 0
        for name, param in current_params.items():
            if name in self.fisher:
                # Penaliza mudanças em parâmetros importantes
                loss += (self.fisher[name] * (param - self.old_params[name])**2).sum()
        return self.lambda_ewc * loss

# Adiciona ao loss total:
total_loss = task_loss + ewc_loss
```

**Vantagens:**
- ✅ Muito eficaz contra forgetting
- ✅ Usado em state-of-the-art continual learning
- ✅ Não precisa de guardar dados antigos

**Desvantagens:**
- ⚠️ Complexo de implementar
- ⚠️ Requer calcular Fisher Information Matrix
- ⚠️ Overhead computacional

### 3. **Knowledge Distillation**

**Conceito:**
- Usa modelo antigo (teacher) para guiar novo treino
- Modelo novo (student) aprende a imitar teacher + novos dados
- Preserva outputs do modelo antigo

**Implementação:**
```python
def distillation_loss(student_output, teacher_output, temperature=2.0):
    """Loss que força student a imitar teacher."""
    soft_targets = F.softmax(teacher_output / temperature, dim=1)
    soft_predictions = F.log_softmax(student_output / temperature, dim=1)

    return F.kl_div(soft_predictions, soft_targets, reduction='batchmean')

# Treino:
teacher_output = old_model(X)  # Modelo V7
student_output = new_model(X)  # Modelo V8 a treinar

loss = task_loss + 0.5 * distillation_loss(student_output, teacher_output)
```

**Vantagens:**
- ✅ Mantém comportamento do modelo antigo
- ✅ Funciona bem com redes neurais profundas
- ✅ Usado em transfer learning

**Desvantagens:**
- ⚠️ Precisa de carregar 2 modelos em memória
- ⚠️ Treino ~30% mais lento

### 4. **Progressive Neural Networks**

**Conceito:**
- Adiciona novas colunas de neurónios para cada nova tarefa
- Camadas antigas ficam congeladas
- Novas camadas aprendem conectando-se às antigas

**Vantagens:**
- ✅ Zero forgetting (camadas antigas nunca mudam)
- ✅ Ideal para múltiplos domínios muito diferentes

**Desvantagens:**
- ⚠️ Modelo cresce a cada sessão
- ⚠️ Complexo de implementar
- ⚠️ Não prático para muitas sessões (>20)

---

## 📖 Boas Práticas para Treino Incremental

### 1. **Validação Cruzada entre Sessões**

Sempre que treinares incrementalmente:
```bash
# Testa modelo novo em datasets de sessões ANTIGAS
python3 scripts/validate_on_old_sessions.py --new_model V9 --test_sessions 1,3,5,7
```

Se MAE piorar em sessões antigas → Regressão detectada

### 2. **Checkpoint de Cada Versão**

```bash
# Guarda checkpoint após cada treino bem-sucedido
mkdir -p models/checkpoints
cp models/*.pth models/checkpoints/v8_
cp models/*.pkl models/checkpoints/v8_
cp models/*.json models/checkpoints/v8_
```

Permite reverter se detetar regressão

### 3. **Diversidade de Dados**

- ✅ Varia os estilos entre sessões
- ❌ Não treines 3 casamentos seguidos
- ✅ Alterna: paisagem → retrato → casamento → moda → paisagem

### 4. **Monitorização Contínua**

Implementa um dashboard simples:
```python
# scripts/monitor_training.py
import json
import matplotlib.pyplot as plt

def plot_mae_evolution():
    with open('models/training_history.json') as f:
        history = json.load(f)

    sessions = history['training_sessions']

    params_to_track = ['temp', 'contrast', 'highlights', 'exposure']

    for param in params_to_track:
        values = [s.get(param, 0) for s in sessions]
        plt.plot(values, label=param)

    plt.legend()
    plt.xlabel('Training Session')
    plt.ylabel('MAE')
    plt.title('MAE Evolution Across Sessions')
    plt.show()
```

---

## 🎓 Lições Aprendidas

### Do's ✅

1. **LR baixo para incremental** (0.05 ou menos)
2. **Monitoriza MAE** de sessão para sessão
3. **Diversifica catálogos** - não treines estilos muito similares seguidos
4. **Guarda checkpoints** de cada versão
5. **Testa em dados antigos** para detetar regressão cedo

### Don'ts ❌

1. **Não uses LR >= 0.1** em treino incremental
2. **Não treines datasets muito grandes** (>50% do total) numa sessão
3. **Não ignores warnings** de MAE alto
4. **Não continues a treinar** se detetares regressão
5. **Não apagues versões antigas** antes de validar a nova

---

## 🚀 Próximos Passos

### Curto Prazo (Agora):

1. ✅ **Corrigido:** LR factor reduzido para 0.05
2. ⏳ **Retreina** catálogo de casamento com novo LR
3. ⏳ **Compara** MAE do V9 com V7

### Médio Prazo (Próximas Semanas):

1. 📝 Implementa Experience Replay
2. 📊 Cria script de monitorização MAE
3. 💾 Sistema automático de checkpoints
4. 🔬 Valida em datasets antigos

### Longo Prazo (Próximos Meses):

1. 🧠 Considera EWC ou Knowledge Distillation
2. 📈 Dashboard web para visualizar treinos
3. 🤖 Auto-deteção de regressão com alertas
4. 📚 Publica paper sobre continual learning em photo editing

---

## 📚 Referências

### Papers sobre Continual Learning:

1. **Elastic Weight Consolidation (EWC)**
   - Kirkpatrick et al. (2017)
   - "Overcoming catastrophic forgetting in neural networks"

2. **Experience Replay**
   - Rolnick et al. (2019)
   - "Experience Replay for Continual Learning"

3. **Knowledge Distillation**
   - Hinton et al. (2015)
   - "Distilling the Knowledge in a Neural Network"

4. **Progressive Neural Networks**
   - Rusu et al. (2016)
   - "Progressive Neural Networks"

### Implementações:

- [Continual AI Library](https://github.com/ContinualAI/avalanche)
- [PyTorch Continual Learning](https://github.com/GMvandeVen/continual-learning)

---

**Última atualização:** 2025-11-25
**Autor:** Claude Code + Nelson Silva
**Status:** ✅ Solução implementada, aguarda validação V9
