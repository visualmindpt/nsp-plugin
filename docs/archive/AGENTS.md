# Repository Guidelines

## Project Structure & Module Organization
Principais raízes: `services/` (FastAPI e lógica de inferência/retraining), `train/` (pipelines de treino), `tools/` (scripts operacionais) e `tests/` (pytest). `NSP-Plugin.lrplugin/` guarda o plugin em Lua para Lightroom; `control-center` e `control-center-v2` são frentes Tauri/React para operar o servidor. Os modelos e datasets vivem em `models/`, `data/` e `logs/`; evita alterar manualmente. Documentação tática fica em `docs/` e `docs_portal/`. Scripts shell na raiz (ex.: `start_server.sh`, `diagnostico.sh`) são entrypoints oficiais—não duplicates lógica dentro do código Python.

## Build, Test e Desenvolvimento
Usa Python 3.11 com ambiente virtual. Exemplos:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn services.server:app --host 127.0.0.1 --port 5678 --reload
python app_ui.py  # UI Gradio para operadores
```
`start_server_cpu.sh` e `run_server_safe.py` levantam o backend endurecido; `start_control_center.sh` compila/lança o painel Tauri; `train/train_models_v2.py` (ou `./start_train_ui.sh`) e `train_culling.py` executam jobs batch (usa `--dry-run` antes de jobs longos).

## Estilo e Convenções
Python: indentação 4 espaços, type hints obrigatórios, evitar imports globais. Corre `ruff check services train tools --fix` e `ruff format` antes do commit; não desactivar regras sem justificativa. Lua: módulos em PascalCase, helpers snake_case; comentários focam em integrações Lightroom. React/Tauri: componentes PascalCase, hooks `useX`. Segredos vivem em `.env.local`/`install/.env` e nunca entram no repo.

## Testing Guidelines
`pytest.ini` já força `--cov` sobre `services`, `train` e `tools`; mantém cobertura ≥85%. Comando padrão:
```bash
pytest -n auto --maxfail=1
```
Marca testes caros com `@pytest.mark.slow` ou `ml`; usa `pytest -m "not slow"` em pipelines rápidos. Fixtures comuns residem em `tests/conftest.py`. Scripts legados `test_feedback_*.py` continuam válidos mas novos cenários pertencem a `tests/`.

## Commits & Pull Requests
Segue Conventional Commits (`feat:`, `fix:`, `docs:`). Mensagens ≤72 chars, corpo com contexto/tickets. Antes do PR: 1) linka issue, 2) descreve arquitetura e flags (ex.: `start_server_cpu.sh --safe`), 3) anexa saída de `pytest` e, se aplicável, `train/train_models_v2.py --dry-run` ou logs do `./start_train_ui.sh`, 4) inclui screenshots/GIFs para alterações no control-center ou no plugin. Mantém PRs focados; mudanças multi-área devem ser fatiadas.

## Segurança & Configuração
Não partilha `best_*_model.pth` nem dumps de `data/`. Tokens usados em `services/db_utils.py` carregam via gestor de segredos; em dev usa `install/.env.example`. Verifica portas (ex.: `lsof -i :5678`) antes de arrancar o uvicorn. Logs sensíveis vão para `logs/` com rotação (`start_server.sh` já implementa); limpa-os antes de anexar a issues públicas.
