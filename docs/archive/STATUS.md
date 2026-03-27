# NSP Bundle – Estado Atual (2025-11-08)

## Visão global
- Motor FastAPI (`services/server.py`) com endpoints `/predict`, `/feedback` e **novo** `/feedback/bulk`.
- Ingestão baseada no `id_local` do Lightroom (`tools/extract_from_lrcat.py`) para alinhar feedback direto do plugin.
- Modelo LightGBM (22 sliders) + Rede Neural multi-output; avaliação recente:
  - LightGBM Overall MAE: **16.50** (dataset reduzido para 28 amostras válidas)
  - Rede Neural Overall MAE: **34.35** (mesmo dataset, val/test diminutos)
- Manifesto de modelos (`models/model_bundle.lock.json`) atualizado automaticamente após treino (`train/train_sliders.py`, `train/ann/train_nn.py`).

## Plugin Lightroom
- **Auto-horizonte**: `photo:applyAutoStraighten()` aplicado automaticamente (configurável via `force_auto_horizon`).
- **Auto-feedback híbrido**:
  - Toggle “Aprender automaticamente” → envia feedback após cada aplicação AI.
  - Comandos adicionais:
    - `NSP – Enviar feedback` (foto atual).
    - `NSP – Sincronizar feedback` (seleção → `/feedback/bulk`).
    - `NSP – Preferências` (UI para as flags).
  - Menu `NSP – Get AI Edit` agora suporta seleção múltipla com `LrProgressScope`.

## Control Center / Config
- `config/nsp_config.json` passa a incluir `force_auto_horizon` e `auto_feedback`.
- Logs “live” a partir do Control Center; bundle verificado via manifesto.

## MLOps / Scripts
- `train/retrain_from_feedback.py` continua a incorporar `feedback_records`.
- `train/ann/evaluate_nn.py` aceita `--skip-validation` / `--iqr-multiplier` (alinhado com treino).
- `tests/test_data_validation.py` + `tests/conftest.py` criados (em progresso de integração com pytest).

## Tarefas pendentes / recomendações
1. **Python 3.11**: recriar o `venv` com o Python Homebrew para eliminar avisos de LibreSSL/Accelerate.
2. **Dataset**: aumentar exemplos válidos (atualmente 28 após validação) antes de comparar MAE.
3. **CI/Testes**: formalizar pytest (resolver crash atual, adicionar casos para `evaluate_nn.py` e `/feedback/bulk`).
4. **Control Center**: expor toggles + botão “Sync feedback” para paridade com o plugin.
5. **Documentação**: atualizar README principal com o fluxo híbrido (auto-feedback + bulk).
