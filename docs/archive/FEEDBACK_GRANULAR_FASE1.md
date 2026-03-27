# Sistema de Feedback Granular - Fase 1: Infraestrutura Base

**Status:** ✅ Implementado e Testado
**Data:** 2025-11-12
**Versão:** 1.0

## Visão Geral

A Fase 1 implementa a infraestrutura base completa para o sistema de feedback granular, permitindo capturar, validar e armazenar feedback detalhado a nível de slider individual para re-treino inteligente do modelo.

## Ficheiros Implementados

### 1. Script de Migração SQL
**Ficheiro:** `migrations/001_feedback_granular.sql`

Cria toda a infraestrutura de base de dados:

#### Tabelas Criadas:
- **`granular_feedback`**: Armazena feedback granular (slider a slider)
  - Campos: slider_name, predicted_value, user_value, delta_value
  - Métricas: confidence_score, feedback_quality, is_outlier
  - Flags: used_in_training, validated

- **`retraining_history`**: Histórico de re-treinos executados
  - Timing: started_at, completed_at, duration_seconds
  - Dados: feedback_count, training_samples
  - Métricas: train_loss, validation_loss, train_mae, validation_mae
  - Status: success, failed, running, cancelled

- **`retraining_config`**: Configuração do sistema (uma linha)
  - Thresholds: min_feedback_count, min_feedback_quality
  - Outlier detection: outlier_std_multiplier
  - Scheduling: auto_retrain_enabled, check_interval_hours

- **`feedback_quality_metrics`**: Métricas agregadas por período
  - Estatísticas de volume e qualidade
  - Distribuição por slider

#### Índices Otimizados:
- `idx_granular_feedback_record_id`: Lookup por record
- `idx_granular_feedback_session`: Lookup por sessão
- `idx_granular_feedback_timestamp`: Queries temporais
- `idx_granular_feedback_training`: Filtro de feedback para treino
- `idx_granular_feedback_slider_analysis`: Análise por slider

#### Views Criadas:
- **`v_feedback_ready_for_training`**: Feedback pronto para re-treino
- **`v_slider_feedback_stats`**: Estatísticas por slider
- **`v_recent_retrainings`**: Resumo de re-treinos recentes

#### Triggers:
- Validação automática de consistency
- Atualização de timestamps

### 2. Configuração de Sliders
**Ficheiro:** `slider_config.py` (atualizado)

Adicionadas variáveis globais:
```python
ALL_SLIDER_NAMES: List[str]           # 38 sliders em ordem canónica
SLIDER_RANGES: Dict[str, dict]        # Ranges min/max/step
SLIDER_INDEX_TO_NAME: Dict[int, str]  # Lookup por índice
SLIDER_NAME_TO_INDEX: Dict[str, int]  # Lookup por nome
```

### 3. Pydantic Models
**Ficheiro:** `services/feedback_schemas.py`

#### Request Schemas:
- **`SliderFeedbackItem`**: Feedback de um slider individual
  - Validação de nome e ranges

- **`GranularFeedbackRequest`**: Feedback granular (lista de sliders)
  - Validação de duplicados

- **`ImplicitFeedbackRequest`**: Feedback implícito (aceitação)

- **`ExplicitFeedbackRequest`**: Feedback explícito (vetor completo)
  - Validação de todos os 38 valores

- **`RetrainingTriggerRequest`**: Trigger de re-treino manual

- **`RetrainingConfigUpdate`**: Atualização de configuração

#### Response Schemas:
- **`FeedbackProcessingResult`**: Resultado do processamento
- **`RetrainingStatus`**: Status de re-treino
- **`FeedbackStatistics`**: Estatísticas agregadas
- **`RetrainingConfigResponse`**: Configuração atual

### 4. FeedbackManager
**Ficheiro:** `services/feedback_manager.py`

Classe central para gestão de feedback.

#### Métodos Principais:

**Processamento de Feedback:**
```python
process_feedback(feedback: GranularFeedbackRequest) -> FeedbackProcessingResult
```
Processa feedback granular com fluxo completo:
1. Calcular deltas
2. Identificar sliders editados
3. Calcular confidence scores
4. Calcular feedback quality
5. Detetar outliers
6. Guardar na base de dados

**Processamento de Feedback Explícito:**
```python
process_explicit_feedback(feedback: ExplicitFeedbackRequest) -> FeedbackProcessingResult
```
Converte vetor completo em feedback granular.

**Obtenção de Feedback para Treino:**
```python
get_validated_feedback_for_training(
    min_quality: float = None,
    max_count: int = None,
    exclude_outliers: bool = True
) -> List[Dict]
```
Retorna feedback validado e pronto para re-treino.

#### Cálculo de Métricas:

**Confidence Score** (0-1):
- Magnitude do delta (normalizada)
- Tempo até editar (se disponível)
- Consistência com histórico

**Feedback Quality** (0-1):
- Número de edições
- Magnitude média dos deltas
- Confidence médio
- Consistência dos deltas

**Outlier Detection**:
- Z-score (>3 desvios padrão)
- IQR (Interquartile Range)
- Range check (>80% do range)

### 5. Script de Migração Python
**Ficheiro:** `tools/database_migration.py`

Sistema completo de gestão de migrações.

#### Funcionalidades:
- Descoberta automática de migrações
- Aplicação idempotente
- Tracking de migrações aplicadas
- Validação de integridade
- CLI interativa

#### Uso:
```bash
# Ver status
python tools/database_migration.py --status

# Aplicar migrações pendentes
python tools/database_migration.py --apply

# Aplicar migração específica
python tools/database_migration.py --apply --migration 001_feedback_granular

# Validar integridade
python tools/database_migration.py --validate
```

### 6. Testes
**Ficheiro:** `tests/test_feedback_system.py`

Suite completa de testes:
1. Validação de Pydantic schemas
2. FeedbackManager (processamento completo)
3. Obtenção de feedback validado
4. Processamento de feedback explícito
5. Views da base de dados

## Configuração Default

A migração insere automaticamente configuração default:

```python
min_feedback_count = 50          # Mínimo de feedbacks para trigger
min_feedback_quality = 0.7       # Qualidade mínima (0-1)
max_outlier_percentage = 0.15    # Máximo 15% de outliers
confidence_threshold = 0.6       # Threshold de confiança
min_delta_threshold = 1.0        # Delta mínimo significativo
outlier_std_multiplier = 3.0     # 3 sigma para outliers
auto_retrain_enabled = False     # Re-treino automático desligado
check_interval_hours = 24        # Verificar a cada 24h
```

## Instalação

### Dependências
Adicionar ao `requirements.txt`:
```
pydantic>=2.9.2
scipy>=1.16.3
```

### Instalação:
```bash
# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install pydantic scipy

# Aplicar migrações
python tools/database_migration.py --apply

# Executar testes
python tests/test_feedback_system.py
```

## Exemplo de Uso

### 1. Processar Feedback Granular

```python
from pathlib import Path
from services.feedback_manager import FeedbackManager
from services.feedback_schemas import (
    GranularFeedbackRequest,
    SliderFeedbackItem
)

# Inicializar manager
db_path = Path('data/nsp_plugin.db')
manager = FeedbackManager(db_path)

# Criar feedback
feedback = GranularFeedbackRequest(
    original_record_id=123,
    session_id='session-abc-123',
    edited_sliders=[
        SliderFeedbackItem(
            slider_name='exposure',
            predicted_value=0.0,
            user_value=1.5,
            time_to_edit_seconds=2.0
        ),
        SliderFeedbackItem(
            slider_name='contrast',
            predicted_value=10.0,
            user_value=25.0,
            time_to_edit_seconds=3.5
        )
    ]
)

# Processar
result = manager.process_feedback(feedback)

print(f"Success: {result.success}")
print(f"Validated: {result.validated_count}")
print(f"Quality: {result.message}")
```

### 2. Obter Feedback para Treino

```python
# Obter feedback validado
validated_feedback = manager.get_validated_feedback_for_training(
    min_quality=0.7,
    max_count=1000,
    exclude_outliers=True
)

print(f"Feedback pronto para treino: {len(validated_feedback)}")

for fb in validated_feedback[:5]:
    print(f"Slider: {fb['slider_name']}, Delta: {fb['delta_value']:.2f}")
```

### 3. Marcar Feedback como Usado

```python
# Após usar em re-treino
feedback_ids = [1, 2, 3, 4, 5]
manager.mark_feedback_as_used(feedback_ids)
```

## Schema da Base de Dados

### Diagrama Relacional

```
┌─────────────────────┐
│     records         │
│  (existente)        │
└──────────┬──────────┘
           │
           │ 1:N
           │
┌──────────▼──────────────────────┐
│   granular_feedback             │
│  ─────────────────────────────  │
│  id (PK)                        │
│  original_record_id (FK)        │
│  session_id                     │
│  slider_name                    │
│  slider_index                   │
│  predicted_value                │
│  user_value                     │
│  delta_value                    │
│  confidence_score               │
│  feedback_quality               │
│  is_outlier                     │
│  used_in_training               │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│   retraining_history            │
│  ─────────────────────────────  │
│  id (PK)                        │
│  started_at                     │
│  completed_at                   │
│  feedback_count                 │
│  validation_mae                 │
│  status                         │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│   retraining_config             │
│  ─────────────────────────────  │
│  id = 1 (única linha)           │
│  min_feedback_count             │
│  min_feedback_quality           │
│  confidence_threshold           │
│  auto_retrain_enabled           │
└─────────────────────────────────┘
```

## Queries Úteis

### Estatísticas de Feedback
```sql
SELECT * FROM v_slider_feedback_stats
ORDER BY edit_count DESC
LIMIT 10;
```

### Feedback Pronto para Treino
```sql
SELECT COUNT(*) as ready_count
FROM v_feedback_ready_for_training;
```

### Top Sliders Editados
```sql
SELECT
    slider_name,
    COUNT(*) as edit_count,
    AVG(ABS(delta_value)) as avg_delta
FROM granular_feedback
WHERE was_edited = 1
GROUP BY slider_name
ORDER BY edit_count DESC
LIMIT 10;
```

## Métricas e KPIs

O sistema calcula automaticamente:

### Por Feedback:
- **Confidence Score**: Confiança na correção (0-1)
- **Feedback Quality**: Qualidade do feedback (0-1)
- **Is Outlier**: Flag de outlier

### Agregadas:
- Total de feedbacks
- Taxa de validação
- Taxa de outliers
- Quality score médio
- Sliders mais editados
- Magnitude média de correções

## Performance

### Índices Otimizados:
- Lookup por record_id: O(log n)
- Lookup por session_id: O(log n)
- Queries temporais: O(log n)
- Filtro para treino: O(log n)

### Base de Dados:
- WAL mode ativado (concorrência)
- Page size: 4KB
- Memory-mapped I/O: 30GB
- Synchronous: NORMAL (performance/segurança)

## Próximos Passos

### Fase 2: Endpoints API
- `POST /feedback/granular` - Submeter feedback
- `POST /feedback/explicit` - Submeter vetor completo
- `GET /feedback/stats` - Estatísticas
- `GET /feedback/ready` - Feedback para treino

### Fase 3: Sistema de Re-treino
- Trigger automático por threshold
- Pipeline de re-treino
- Validação de modelos
- Deploy automático

### Fase 4: Dashboard
- Visualização de métricas
- Análise de sliders
- Histórico de re-treinos
- Configuração online

## Troubleshooting

### Erro: "Record original não encontrado"
**Solução:** Garantir que o record existe na tabela `records` antes de submeter feedback.

### Erro: "slider_name inválido"
**Solução:** Verificar que o nome está em `ALL_SLIDER_NAMES`.

### Erro: "valor fora do range"
**Solução:** Validar que valores estão dentro dos limites definidos em `SLIDER_RANGES`.

### Base de dados locked
**Solução:** WAL mode deve estar ativo. Verificar com:
```sql
PRAGMA journal_mode;
```

## Logs

O sistema usa logging estruturado:

```
INFO:services.feedback_manager:FeedbackManager inicializado | confidence_threshold=0.60
INFO:services.feedback_manager:Processando feedback | record_id=123 | sliders_editados=3
INFO:services.feedback_manager:Feedback processado | validated=3 | outliers=0 | quality=0.814
```

## Validação

### Testes Automatizados:
```bash
python tests/test_feedback_system.py
```

Todos os testes devem passar:
- ✓ Validação de schemas
- ✓ FeedbackManager
- ✓ Retrieval de feedback
- ✓ Feedback explícito
- ✓ Views da base de dados

### Validação Manual:
```bash
# Status das migrações
python tools/database_migration.py --status

# Integridade da base de dados
python tools/database_migration.py --validate
```

## Suporte

Para questões ou problemas:
1. Verificar logs em `logs/`
2. Executar testes de validação
3. Consultar este documento
4. Verificar schema da base de dados

---

**Implementado por:** Claude (AI Assistant)
**Projeto:** NSP Plugin - Sistema de Feedback Granular
**Versão:** 1.0 - Fase 1 Completa
