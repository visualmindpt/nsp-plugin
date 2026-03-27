# NSP Plugin - Test Suite

Suite de testes automatizados para validar funcionalidade, segurança e robustez do NSP Plugin.

## Estrutura

```
tests/
├── conftest.py              # Fixtures e configuração pytest
├── pytest.ini               # Configuração pytest (na raiz do projeto)
├── test_data_validation.py  # Validação de dados EXIF/develop_vector
├── test_db_utils.py          # WAL mode, retry logic, database utils
├── test_security.py          # SQL injection, path traversal, rate limiting
├── test_server.py            # Endpoints FastAPI
└── README.md                 # Este ficheiro
```

## Instalação

```bash
# Instalar dependências de teste
pip install pytest pytest-cov pytest-timeout httpx

# Ou instalar tudo via requirements.txt
pip install -r requirements.txt
```

## Executar Testes

### Todos os testes
```bash
pytest
```

### Com coverage report
```bash
pytest --cov=services --cov=train --cov=tools --cov-report=html
```

### Por categoria
```bash
# Apenas testes unitários (rápidos)
pytest -m unit

# Apenas testes de integração
pytest -m integration

# Apenas testes de segurança
pytest -m security

# Apenas testes de API
pytest -m api

# Apenas testes de database
pytest -m db
```

### Testes específicos
```bash
# Arquivo específico
pytest tests/test_security.py

# Teste específico
pytest tests/test_security.py::test_sql_injection_prevention_consistency

# Com output verbose
pytest -v tests/test_db_utils.py
```

### Opções úteis
```bash
# Parar no primeiro erro
pytest -x

# Mostrar print statements
pytest -s

# Re-executar apenas testes falhados
pytest --lf

# Executar em paralelo (requer pytest-xdist)
pytest -n auto
```

## Markers (Categorias)

Os testes estão organizados por markers para facilitar execução seletiva:

- **`unit`**: Testes unitários rápidos sem dependências externas
- **`integration`**: Testes de integração (requerem DB, modelos, etc.)
- **`slow`**: Testes lentos (> 1 segundo)
- **`api`**: Testes de endpoints FastAPI
- **`db`**: Testes de database
- **`security`**: Testes de validação de segurança
- **`ml`**: Testes de machine learning

## Coverage Report

Após executar `pytest --cov`, o report HTML estará disponível em:

```
htmlcov/index.html
```

Abrir no browser:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Fixtures Disponíveis

Definidas em `conftest.py`:

- **`project_root`**: Path para raiz do projeto
- **`temp_db`**: Base de dados SQLite temporária com schema
- **`sample_records`**: Database com 10 records de exemplo
- **`sample_image`**: Imagem PNG 1x1 para testes
- **`sample_develop_vector`**: Develop vector válido (22 sliders)
- **`sample_exif`**: EXIF metadata de exemplo
- **`mock_embeddings`**: Embeddings PCA mockados
- **`mock_models`**: Artefactos de modelo mockados (PCA, scaler)

## Testes Críticos

### Segurança
- `test_sql_injection_prevention_consistency`: Previne SQL injection via record IDs
- `test_path_traversal_prevention`: Bloqueia path traversal attacks
- `test_rate_limiting_*`: Valida rate limiting em endpoints

### Database
- `test_get_db_connection_retry_on_lock`: Retry logic funciona quando DB locked
- `test_enable_wal_mode`: WAL mode é ativado corretamente
- `test_get_db_connection_auto_commit`: Auto-commit no sucesso

### API
- `test_health_endpoint`: Endpoint /health responde corretamente
- `test_feedback_endpoint_wrong_vector_size`: Valida tamanho do develop_vector
- `test_predict_endpoint_invalid_model`: Rejeita modelos inválidos

## Troubleshooting

### Testes falhando com "database is locked"
- Certifica-te que WAL mode está ativado (`test_enable_wal_mode` passa)
- Aumenta timeout em `get_db_connection`

### Testes de rate limiting falhando
- Rate limiter usa cache in-memory que pode persistir entre testes
- Executar testes individualmente: `pytest tests/test_security.py::test_rate_limiting_predict_endpoint`

### Import errors
- Certifica-te que estás na raiz do projeto
- Verifica que `conftest.py` está a adicionar root ao sys.path

## CI/CD

Para integração contínua, adicionar ao pipeline:

```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov --cov-report=xml --maxfail=5

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Contribuir

Ao adicionar novos testes:

1. Usar fixtures de `conftest.py` quando possível
2. Adicionar markers apropriados (`@pytest.mark.unit`, etc.)
3. Nomear testes claramente: `test_<functionality>_<scenario>`
4. Adicionar docstrings explicativas
5. Limpar recursos (usar fixtures com cleanup automático)

## Métricas de Sucesso

Objetivos de coverage:

- **services/**: > 80%
- **train/**: > 70%
- **tools/**: > 70%
- **Overall**: > 75%

Estado atual: Execute `pytest --cov` para ver.
