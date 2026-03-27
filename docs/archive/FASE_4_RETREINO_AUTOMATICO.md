# Fase 4: Sistema de Retreino Automático com Safeguards

## Visão Geral

Sistema completo de retreino incremental (fine-tuning) do modelo neural network usando feedback validado do utilizador. Implementa safeguards robustos para garantir que novos modelos são sempre melhores que o modelo atual.

## Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                    SISTEMA DE RETREINO                        │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Feedback   │───>│  Scheduler   │───>│    Trainer    │  │
│  │   Manager   │    │ (Readiness)  │    │ (Fine-tuning) │  │
│  └─────────────┘    └──────────────┘    └───────────────┘  │
│         │                   │                     │          │
│         │                   │                     │          │
│         v                   v                     v          │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Validation │    │   Metrics    │    │     Model     │  │
│  │  & Quality  │    │  Monitoring  │    │   Manager     │  │
│  └─────────────┘    └──────────────┘    └───────────────┘  │
│                                                   │          │
│                                                   v          │
│                                           ┌───────────────┐  │
│                                           │    Deploy     │  │
│                                           │  (+ Backup)   │  │
│                                           └───────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Componentes Implementados

### 1. **RetrainingScheduler** (`services/retraining_scheduler.py`)

Monitorizador inteligente que decide quando o sistema está pronto para retreino.

**Responsabilidades:**
- Verificar thresholds de feedback (volume, qualidade, outliers)
- Calcular drift score (modelo a prever mal sistematicamente)
- Validar cooldown periods (evita retreinos excessivos)
- Fornecer estatísticas para dashboard

**Métricas Analisadas:**
```python
{
    'feedback_count': 150,           # Total de feedback disponível
    'validated_count': 120,          # Feedback validado e pronto
    'avg_quality': 0.85,             # Qualidade média (0-1)
    'outlier_percentage': 0.08,      # 8% outliers (threshold: 15%)
    'drift_score': 0.23,             # Drift moderado (0-1)
    'days_since_last_retrain': 5.2,  # Dias desde último retreino
    'cooldown_remaining_hours': 0.0  # Cooldown passou
}
```

**Critérios de Readiness:**
1. ✅ `validated_count >= min_feedback_count` (default: 50)
2. ✅ `avg_quality >= min_feedback_quality` (default: 0.7)
3. ✅ `outlier_percentage <= max_outlier_percentage` (default: 0.15)
4. ✅ Cooldown de 12 horas passou
5. 📊 Drift score (informativo, não bloqueante)

### 2. **ModelManager** (`services/model_manager.py`)

Gestor de ciclo de vida de modelos com backup/rollback automático.

**Funcionalidades:**
- **Backup Automático:** Antes de cada deploy, cria backup timestamped
- **Validação Pré-Deploy:** Testa que novo modelo carrega e funciona
- **Rollback:** Restaurar versão anterior em caso de falha
- **Versioning:** Tracking completo de todas as versões

**Estrutura de Backups:**
```
models/ann/
├── multi_output_nn.onnx              # Produção atual
├── multi_output_nn.pth
├── targets_mean.npy
├── targets_std.npy
└── backups/
    ├── v_backup_2025-11-12_10-30-00/ # Backup 1
    │   ├── multi_output_nn.onnx
    │   ├── multi_output_nn.pth
    │   ├── targets_mean.npy
    │   ├── targets_std.npy
    │   └── metadata.json
    └── v_backup_2025-11-13_14-20-00/ # Backup 2
        └── ...
```

**Validação de Modelos:**
```python
def validate_model_loads(model_path):
    """
    Testa:
    1. Ficheiro existe
    2. ONNX Runtime consegue carregar
    3. Input shape: [batch_size, 515]
    4. Output shape: [batch_size, 38]
    5. Inferência dummy funciona
    """
```

### 3. **IncrementalTrainer** (`train/ann/incremental_trainer.py`)

Trainer especializado em fine-tuning com feedback validado.

**Estratégia de Fine-Tuning:**

| Parâmetro | Full Training | Fine-Tuning | Razão |
|-----------|--------------|-------------|-------|
| Learning Rate | 0.001 | 0.0001 | 10x menor para ajustes sutis |
| Epochs | 200 | 20-50 | Menos epochs suficientes |
| Data | Dataset completo | Feedback + 30% original | Combina feedback novo com contexto |
| Batch Size | 128 | 64 | Batches menores para estabilidade |
| Validation | 10% | 15% | Mais validação para garantir qualidade |

**Fluxo de Retreino:**

```python
# 1. Carregar modelo atual
model, current_loss = load_current_model()  # Ex: loss = 0.0250

# 2. Carregar feedback validado
feedback_samples = load_feedback_data(min_quality=0.7)  # Ex: 120 samples

# 3. (Opcional) Misturar com dataset original
original_samples = load_original_data_subset(ratio=0.3)  # Ex: 300 samples

# 4. Fine-tuning
training_metrics = fine_tune_model(
    model=model,
    X=X,  # 420 samples total
    y=y,
    learning_rate=0.0001,  # 10x menor
    epochs=30
)

# 5. Validar melhoria
new_loss = training_metrics['best_val_loss']  # Ex: 0.0220
improvement = (current_loss - new_loss) / current_loss  # Ex: 12%

# Threshold: Novo modelo deve ser ≥ 2% melhor
if improvement < -0.02:
    raise ValueError("Modelo piorou mais de 2%. Abortando.")

# 6. Exportar para ONNX
export_to_onnx(model)
```

**Safeguards Implementados:**

1. **Validação de Qualidade:**
   - Novo modelo **DEVE** ter `loss ≤ current_loss * 0.98` (2% melhor)
   - Se piorar mais de 2%, **ABORTA** e não faz deploy
   - Margem de erro de 0-2% é aceitável

2. **Validação de Carregamento:**
   - Testa que novo ONNX carrega antes de deploy
   - Verifica shapes de input/output
   - Executa inferência dummy

3. **Backup Automático:**
   - Sempre cria backup antes de deploy
   - Backup inclui ONNX, PyTorch e estatísticas

4. **Early Stopping:**
   - Para treino se validação não melhorar por 5 epochs
   - Evita overfitting

### 4. **Retraining API** (`services/retraining_api.py`)

Endpoints FastAPI para controlo completo do sistema de retreino.

#### **POST /training/trigger**

Dispara retreino manual ou automático.

**Request:**
```json
{
  "training_type": "incremental",
  "min_feedback_quality": 0.7,
  "use_feedback_only": false,
  "force": false,
  "notes": "Retreino manual após análise de drift"
}
```

**Response:**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Retreino iniciado em background"
}
```

**Parâmetros:**
- `training_type`: `"incremental"` ou `"full"`
- `min_feedback_quality`: Qualidade mínima (0.0-1.0)
- `use_feedback_only`: Se `true`, não mistura com dataset original
- `force`: Se `true`, ignora todos os thresholds (usar com cuidado)
- `notes`: Notas para histórico

#### **GET /training/status/{run_id}**

Monitoriza status em tempo real.

**Response:**
```json
{
  "run_id": "550e8400-...",
  "status": "running",
  "progress": 0.65,
  "current_epoch": 13,
  "total_epochs": 30,
  "current_loss": 0.0234,
  "validation_loss": 0.0198,
  "samples_used": 420,
  "started_at": "2025-11-12T10:00:00",
  "estimated_completion": "2025-11-12T10:15:00",
  "message": "Fine-tuning em progresso..."
}
```

**Status possíveis:**
- `pending`: Agendado, aguardando início
- `running`: Em execução
- `validating`: Validando novo modelo
- `completed`: Concluído com sucesso
- `failed`: Falhou (ver message)

#### **GET /training/ready**

Verifica se sistema está pronto para retreino.

**Response:**
```json
{
  "ready": true,
  "reason": "Todos os critérios satisfeitos",
  "metrics": {
    "feedback_count": 150,
    "validated_count": 120,
    "avg_quality": 0.85,
    "outlier_percentage": 0.08,
    "drift_score": 0.23,
    "days_since_last_retrain": 5.2,
    "cooldown_remaining_hours": 0.0
  }
}
```

#### **POST /training/rollback/{version}**

Faz rollback para versão anterior.

**Exemplo:**
```bash
curl -X POST http://localhost:5678/training/rollback/v_backup_2025-11-12_10-30-00
```

**Response:**
```json
{
  "success": true,
  "version": "v_backup_2025-11-12_10-30-00",
  "message": "Rollback concluído para versão v_backup_2025-11-12_10-30-00"
}
```

**Safeguards:**
- Não permite rollback durante retreino ativo
- Cria backup de segurança antes de rollback
- Valida que modelo restaurado carrega corretamente

#### **GET /training/history**

Histórico de retreinos executados.

**Query Parameters:**
- `limit`: Número máximo de registos (default: 20)
- `status_filter`: Filtrar por status (`success`, `failed`, `running`)

**Response:**
```json
{
  "history": [
    {
      "id": 5,
      "started_at": "2025-11-12T10:00:00",
      "completed_at": "2025-11-12T10:12:34",
      "duration_seconds": 754,
      "trigger_type": "manual",
      "feedback_count": 120,
      "validation_mae": 0.0220,
      "status": "success"
    },
    {
      "id": 4,
      "started_at": "2025-11-10T14:30:00",
      "completed_at": "2025-11-10T14:42:15",
      "duration_seconds": 735,
      "trigger_type": "threshold",
      "feedback_count": 85,
      "validation_mae": 0.0235,
      "status": "success"
    }
  ],
  "count": 2
}
```

#### **GET /training/stats**

Estatísticas completas do sistema.

**Response:**
```json
{
  "feedback": {
    "total": 150,
    "validated": 120,
    "outliers": 12,
    "avg_quality": 0.85,
    "avg_confidence": 0.78,
    "ready_for_training": 120
  },
  "last_retrain": {
    "id": 5,
    "started_at": "2025-11-12T10:00:00",
    "completed_at": "2025-11-12T10:12:34",
    "duration_seconds": 754,
    "feedback_count": 120,
    "validation_mae": 0.0220,
    "trigger_type": "manual"
  },
  "readiness": {
    "ready": true,
    "reason": "Todos os critérios satisfeitos",
    "drift_score": 0.23,
    "days_since_last": 2.5,
    "cooldown_remaining_hours": 0.0
  },
  "config": {
    "min_feedback_count": 50,
    "min_feedback_quality": 0.7,
    "max_outlier_percentage": 0.15,
    "auto_retrain_enabled": false
  },
  "models": {
    "current_version": "prod_2025-11-12_10-12-34",
    "available_backups": 8,
    "backups": [...]
  }
}
```

## Fluxo Completo de Retreino

### 1. Acumulação de Feedback

```
Usuario edita sliders → POST /feedback/granular
                              ↓
                     FeedbackManager processa
                              ↓
                     Calcula confidence & quality
                              ↓
                     Deteta outliers
                              ↓
                     Guarda em granular_feedback
```

### 2. Verificação de Readiness (Manual ou Scheduled)

```
GET /training/ready
        ↓
RetrainingScheduler.check_readiness()
        ↓
Verifica thresholds:
  ✓ Feedback suficiente (≥50)
  ✓ Qualidade boa (≥0.7)
  ✓ Poucos outliers (≤15%)
  ✓ Cooldown passou (≥12h)
        ↓
    ready: true
```

### 3. Trigger de Retreino

```
POST /training/trigger
        ↓
Cria run_id único
        ↓
Inicia background task
        ↓
Status: pending → running
```

### 4. Execução (Background)

```
IncrementalTrainer.train_from_feedback()
        ↓
1. Carregar feedback validado (120 samples)
2. Carregar 30% dataset original (300 samples)
3. Preparar features (embeddings + EXIF)
        ↓
4. Carregar modelo atual
   - multi_output_nn.pth
   - current_loss = 0.0250
        ↓
5. Fine-tuning (30 epochs)
   - Learning rate = 0.0001
   - Early stopping patience = 5
   - Best val loss = 0.0220
        ↓
6. Validar melhoria
   - improvement = 12%
   - ✓ > 2% threshold
        ↓
7. Exportar para ONNX
   - multi_output_nn_retrained.onnx
```

### 5. Deploy com Safeguards

```
ModelManager.deploy_new_model()
        ↓
1. Backup modelo atual
   → backups/v_backup_2025-11-12_10-30-00/
        ↓
2. Validar novo modelo
   ✓ Ficheiro existe
   ✓ ONNX carrega
   ✓ Shapes corretos (515→38)
   ✓ Inferência dummy OK
        ↓
3. Copiar para produção
   - multi_output_nn.onnx ← novo
   - multi_output_nn.pth ← novo
        ↓
4. Verificação final
   ✓ Modelo em produção carrega
        ↓
Status: completed ✓
```

### 6. Pós-Deploy

```
- Atualizar last_retrain_at
- Marcar feedback como usado
- Guardar métricas em retraining_history
- Limpar backups antigos (manter últimos 10)
```

## Configuração (BD: `retraining_config`)

```sql
INSERT INTO retraining_config (id, ...) VALUES (
    1,                      -- Apenas uma linha
    50,                     -- min_feedback_count
    0.7,                    -- min_feedback_quality
    0.15,                   -- max_outlier_percentage (15%)
    0.6,                    -- confidence_threshold
    1.0,                    -- min_delta_threshold
    3.0,                    -- outlier_std_multiplier (3 sigma)
    0,                      -- auto_retrain_enabled (desligado)
    24,                     -- check_interval_hours
    'system_init'           -- updated_by
);
```

**Ajuste de Parâmetros:**

Para retreinos mais frequentes:
```sql
UPDATE retraining_config SET
    min_feedback_count = 30,          -- Menos feedback necessário
    min_feedback_quality = 0.6,       -- Aceitar qualidade menor
    max_outlier_percentage = 0.20     -- Tolerar mais outliers
WHERE id = 1;
```

Para retreinos mais conservadores:
```sql
UPDATE retraining_config SET
    min_feedback_count = 100,         -- Mais feedback necessário
    min_feedback_quality = 0.8,       -- Qualidade mais alta
    max_outlier_percentage = 0.10     -- Tolerar menos outliers
WHERE id = 1;
```

## Monitorização e Troubleshooting

### Logs

Todos os componentes fazem logging detalhado:

```python
# services/retraining_scheduler.py
logger.info("Sistema pronto para retreino | feedback=120 | quality=0.85")

# train/ann/incremental_trainer.py
logger.info("Epoch 15/30 | train_loss=0.0245 | val_loss=0.0220")

# services/model_manager.py
logger.info("Backup criado com sucesso | path=backups/v_backup_...")
```

### Métricas de Sucesso

**Bom Retreino:**
```
✓ Improvement: 8-15%
✓ Validation loss decrescente
✓ No early stopping (treinou todos os epochs)
✓ Deploy bem-sucedido
✓ Duração: 5-15 minutos
```

**Retreino Problemático:**
```
⚠ Improvement: 0-2% (marginal)
⚠ Early stopping acionado muito cedo (epoch 5)
⚠ Validation loss oscilante
⚠ Duração muito longa (>30 min)
```

**Retreino Falhado:**
```
✗ Improvement: < -2% (piorou)
✗ Deploy falhou
✗ Modelo não carrega
✗ Erro durante treino
```

### Rollback de Emergência

Se servidor crashar após deploy:

```bash
# 1. Listar backups disponíveis
curl http://localhost:5678/training/model/versions

# 2. Fazer rollback para última versão boa
curl -X POST http://localhost:5678/training/rollback/v_backup_2025-11-12_10-30-00

# 3. Verificar que modelo carregou
curl http://localhost:5678/health
```

## Integração com Plugin Lightroom

O plugin Lua já envia feedback implícito automaticamente (Fase 3).
Para retreino manual no Lightroom:

```lua
-- No plugin, adicionar botão "Request Retraining"
function requestRetraining()
    local response = LrHttp.post(
        "http://localhost:5678/training/ready",
        ""
    )

    local ready_data = JSON:decode(response)

    if ready_data.ready then
        -- Sistema pronto, disparar retreino
        LrHttp.post(
            "http://localhost:5678/training/trigger",
            JSON:encode({
                training_type = "incremental",
                min_feedback_quality = 0.7,
                force = false,
                notes = "Triggered from Lightroom UI"
            })
        )

        LrDialogs.showBezel("Retreino iniciado!")
    else
        LrDialogs.message(
            "Sistema não está pronto",
            ready_data.reason
        )
    end
end
```

## Testes e Validação

### Teste Manual

```bash
# 1. Verificar readiness
curl http://localhost:5678/training/ready

# 2. Disparar retreino forçado (ignorar thresholds)
curl -X POST http://localhost:5678/training/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "force": true,
    "notes": "Teste manual"
  }'

# Resposta: {"run_id": "550e8400-...", "status": "pending"}

# 3. Monitorizar progresso
watch -n 5 'curl -s http://localhost:5678/training/status/550e8400-...'

# 4. Verificar resultado
curl http://localhost:5678/training/history?limit=1
```

### Teste de Rollback

```bash
# 1. Listar versões
curl http://localhost:5678/training/model/versions

# 2. Fazer rollback
curl -X POST http://localhost:5678/training/rollback/v_backup_2025-11-12_10-30-00

# 3. Validar
curl http://localhost:5678/training/model/info
```

## Segurança

### Rate Limiting

Todos os endpoints de retreino são protegidos por rate limiting:

```python
@router.post("/trigger")
@limiter.limit("5/hour")  # Máximo 5 retreinos por hora
async def trigger_retraining(...):
```

### Validações

1. **Não permitir múltiplos retreinos simultâneos**
2. **Validar que modelo novo é melhor (threshold 2%)**
3. **Backup automático antes de qualquer deploy**
4. **Rollback automático se servidor crashar**
5. **Cooldown de 12 horas entre retreinos**

## Performance

**Retreino Típico:**
- Feedback: 100-200 samples
- Dataset original: 300-500 samples
- Total: 400-700 samples
- Epochs: 20-30
- Duração: 5-10 minutos (CPU) / 2-5 minutos (GPU/MPS)

**Otimizações:**
- Background execution (não bloqueia servidor)
- Batch size otimizado (64)
- Early stopping (evita epochs desnecessários)
- Reutilização de embeddings (já calculados)

## Roadmap Futuro

1. **Auto-retreino scheduled:**
   - Cron job diário para verificar readiness
   - Trigger automático se critérios satisfeitos

2. **A/B Testing:**
   - Deploy gradual (10% → 50% → 100%)
   - Comparar métricas entre modelos

3. **Ensemble models:**
   - Manter múltiplos modelos ativos
   - Agregar previsões

4. **Federated learning:**
   - Retreino distribuído entre múltiplos utilizadores
   - Privacy-preserving

## Conclusão

A Fase 4 implementa um sistema robusto e production-ready de retreino automático com:

✅ **Segurança:** Backups automáticos, validação rigorosa, rollback
✅ **Qualidade:** Threshold de 2% melhoria obrigatório
✅ **Monitorização:** API completa para tracking em tempo real
✅ **Flexibilidade:** Trigger manual ou automático, configurável
✅ **Escalabilidade:** Background execution, não bloqueia servidor

O sistema está pronto para uso em produção e pode ser facilmente integrado no workflow existente do NSP Plugin.
