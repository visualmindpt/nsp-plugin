# NSP Control Center — Guia Rápido

## Visão Geral
O NSP Control Center é uma app desktop (Tauri) que agrega os principais serviços:

- **Servidor de Inferência**: arranca/parar `uvicorn services.server:app`.
- **UI de Treino**: lança `python app_ui.py`.
- **Atalhos**: abre rapidamente `http://127.0.0.1:7860`, diretório do projecto, etc.
- **Estado**: mostra se cada serviço está ligado e regista eventos (via notificações).

## Instalação / Desenvolvimento

```bash
cd control-center
npm install          # instala deps JS e o CLI do Tauri
npm run dev          # arranca a app em modo dev (com hot reload)
```

> Pré-requisitos: Node.js 18+, Rust toolchain, dependências do Tauri (ver https://tauri.app).

## Campos principais

| Campo              | Descrição                                                                 |
|--------------------|----------------------------------------------------------------------------|
| Diretório do projeto| Raiz do projecto (onde vivem `services/server.py`, `app_ui.py`, etc.).    |
| Python /venv/bin/python | Caminho para o interpretador Python com as dependências instaladas.   |
| Host / Porta       | Onde o servidor FastAPI irá ouvir (por omissão `127.0.0.1:5678`).         |

Os valores são guardados em `localStorage`, portanto ficam persistentes entre sessões.

## Botões

- **Iniciar** (Servidor): chama o comando `start_server` no backend Tauri → cria subprocesso `python -m uvicorn …`.
- **Parar** (Servidor): termina o subprocesso guardado em memória.
- **Abrir Gradio**: corre `python app_ui.py` no diretório indicado.
- **Parar UI**: envia `kill` para o processo `app_ui.py`.
- **Abrir localhost:7860**: usa `tauri::shell::open` para abrir o browser padrão na UI de treino.
- **Ping /health**: dispara um `GET /health` para o host/porto configurado (deteção imediata de motores remotos).
- **Validar bundle**: chama o comando `verify_model_bundle` e confirma que os hashes do manifesto (`models/model_bundle.lock.json`) batem certo antes de iniciar o servidor.
- **Abrir lockfile**: abre o `model_bundle.lock.json` diretamente no Finder/Explorer para inspeção manual quando algo falha.

## Build

```bash
npm run build   # gera o bundle nativo (src-tauri/target/release/)
```

O binário resultante pode ser distribuído como `.app` (macOS) ou `.exe/.msi` (Windows) — assina/notariza conforme necessário.

## Health-check remoto

- O painel verifica automaticamente se o host/porta configurados já têm um servidor FastAPI vivo (mesmo que tenha sido lançado noutra máquina).
- O botão **Ping /health** força a chamada imediata ao endpoint e regista o resultado no painel de atividade (útil para diagnosticar redes ou tunéis SSH).

## Streaming de logs

- stdout/stderr dos processos geridos (servidor FastAPI e `app_ui.py`) são pipeados para o painel de atividade em tempo real.
- As entradas são etiquetadas por origem e stream (`stdout` vs `stderr`), permitindo debugar falhas sem abrir o terminal.
- Os últimos 30 eventos são mantidos na UI; para histórico completo basta consultar `logs/`.

## Verificação do bundle

- Antes de arrancar o servidor, o Control Center carrega `models/model_bundle.lock.json` e confirma se todos os ficheiros listados existem e têm o `sha256` esperado.
- Se o manifesto estiver em falta ou divergente, o arranque é bloqueado com uma mensagem clara. Resolve-se regenerando o lockfile (`python tools/model_manifest.py`) ou sincronizando os modelos certos.
- O botão **Validar bundle** repete esta verificação manualmente a partir da UI.

## Integração futura

- Detecção automática do catálogo Lightroom (sincronizar com `app_ui.py`).
- Opção para arrancar o Lightroom automaticamente após os serviços estarem ativos.
