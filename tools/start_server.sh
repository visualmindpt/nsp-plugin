#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/server_autostart.log"
PYTHON_HINT="${NSP_PYTHON:-}"

mkdir -p "$LOG_DIR"

detect_python() {
  if [[ -n "$PYTHON_HINT" && -x "$PYTHON_HINT" ]]; then
    echo "$PYTHON_HINT"
    return 0
  fi
  local candidates=(
    "$PROJECT_ROOT/venv/bin/python3"
    "$PROJECT_ROOT/venv/bin/python"
    "$PROJECT_ROOT/.venv/bin/python3"
    "$PROJECT_ROOT/.venv/bin/python"
    "$(command -v python3 || true)"
    "$(command -v python || true)"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(detect_python)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Nenhum interpretador Python encontrado. Define NSP_PYTHON ou cria venv." | tee -a "$LOG_FILE"
  exit 1
fi

server_is_running() {
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 1 "http://127.0.0.1:5678/health" >/dev/null 2>&1; then
      return 0
    fi
  fi
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i tcp:5678 -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

if server_is_running; then
  echo "$(date '+%F %T') - Servidor já está em execução." >>"$LOG_FILE"
  exit 0
fi

echo "$(date '+%F %T') - A arrancar servidor NSP com $PYTHON_BIN." >>"$LOG_FILE"
nohup "$PYTHON_BIN" -m uvicorn services.server:app --host 127.0.0.1 --port 5678 >>"$LOG_FILE" 2>&1 &
disown
echo "$(date '+%F %T') - Comando enviado para background (PID $!)." >>"$LOG_FILE"
