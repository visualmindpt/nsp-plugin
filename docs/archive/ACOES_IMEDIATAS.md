# NSP Plugin – Ações Imediatas (Quick Wins)

**Data:** 2025-11-09
**Prioridade:** Alta
**Estimativa:** 5-7 dias de trabalho

---

## Sumário

Este documento detalha **quick wins** que podem ser implementados rapidamente para melhorar drasticamente a robustez e UX do NSP Plugin, sem reestruturações arquiteturais profundas.

**Objetivo:** Transformar o produto de "protótipo técnico" para "beta testável" em 1 semana.

---

## 1. Error Handling Robusto (Prioridade P0)

### 1.1. Circuit Breaker no Plugin Lua

**Problema:** Timeouts hardcoded, sem retry strategy.

**Solução (30 min):**

```lua
-- NSP-Plugin.lrplugin/circuit_breaker.lua
local CircuitBreaker = {}
CircuitBreaker.__index = CircuitBreaker

function CircuitBreaker:new(failure_threshold, timeout)
    local obj = {
        failure_count = 0,
        last_failure_time = nil,
        state = "CLOSED", -- CLOSED, OPEN, HALF_OPEN
        failure_threshold = failure_threshold or 3,
        timeout = timeout or 60, -- seconds
    }
    setmetatable(obj, CircuitBreaker)
    return obj
end

function CircuitBreaker:call(func)
    if self.state == "OPEN" then
        local elapsed = os.time() - (self.last_failure_time or 0)
        if elapsed > self.timeout then
            self.state = "HALF_OPEN"
        else
            return nil, "Servidor NSP indisponível (circuit open). Tenta novamente em " .. (self.timeout - elapsed) .. "s."
        end
    end

    local success, result = pcall(func)

    if success then
        if self.state == "HALF_OPEN" then
            self.state = "CLOSED"
            self.failure_count = 0
        end
        return result, nil
    else
        self.failure_count = self.failure_count + 1
        self.last_failure_time = os.time()

        if self.failure_count >= self.failure_threshold then
            self.state = "OPEN"
        end

        return nil, result
    end
end

return CircuitBreaker
```

**Integração em Main.lua:**

```lua
local CircuitBreaker = require 'circuit_breaker'
local server_circuit = CircuitBreaker:new(3, 60)

local function callServerSafe(path, exif, modelName)
    return server_circuit:call(function()
        return callServer(path, exif, modelName, true)
    end)
end

-- Usar callServerSafe() em vez de callServer()
```

**Impacto:**
- ✅ Evita timeouts repetidos (user frustration)
- ✅ Mensagem clara sobre quando retry
- ✅ Auto-recovery quando servidor volta

---

### 1.2. Error Messages User-Friendly

**Problema:** Mensagens técnicas demais.

**Solução (1h):**

```lua
-- NSP-Plugin.lrplugin/error_messages.lua
local ERROR_CATALOG = {
    SERVER_UNREACHABLE = {
        title = "NSP Control Center não está a correr",
        message = "O servidor NSP precisa estar ativo para usar o plugin.\n\nQueres abrir o NSP Control Center agora?",
        actions = {
            primary = {label = "Abrir Control Center", callback = function()
                LrTasks.execute("open -a 'NSP Control Center'")
            end},
            secondary = {label = "Resolver Manualmente", callback = function()
                LrHttp.openUrlInBrowser("https://docs.nspplugin.com/troubleshooting/server-down")
            end}
        }
    },

    NO_PHOTOS_SELECTED = {
        title = "Nenhuma foto selecionada",
        message = "Seleciona pelo menos uma fotografia na grelha antes de usar o NSP.",
        level = "info"
    },

    MODEL_NOT_TRAINED = {
        title = "Modelo ainda não foi treinado",
        message = "Precisas de treinar o modelo NSP com o teu catálogo Lightroom antes de usar o plugin.\n\nIsto demora cerca de 30 minutos na primeira vez.",
        actions = {
            primary = {label = "Treinar Agora", callback = function()
                LrTasks.execute("open -a 'NSP Control Center' && open 'nspplugin://training'")
            end}
        }
    },

    PREDICTION_FAILED = {
        title = "Não foi possível prever ajustes",
        message = "O motor NSP encontrou um erro ao processar esta fotografia.\n\nDetalhes técnicos: %s\n\nEste erro foi registado automaticamente.",
        level = "critical"
    },

    AUTO_START_FAILED = {
        title = "Arranque automático falhou",
        message = "O NSP tentou arrancar o servidor automaticamente mas não conseguiu.\n\nVerifica se o NSP Control Center está instalado corretamente.",
        actions = {
            primary = {label = "Reinstalar NSP", callback = function()
                LrHttp.openUrlInBrowser("https://nspplugin.com/download")
            end}
        }
    },
}

local function showError(errorType, context)
    local err = ERROR_CATALOG[errorType]
    if not err then
        LrDialogs.message("NSP Plugin", "Erro desconhecido: " .. tostring(errorType), "critical")
        return
    end

    local message = err.message
    if context and string.find(message, "%%s") then
        message = string.format(message, tostring(context))
    end

    if err.actions then
        local result = LrDialogs.confirm(
            message,
            err.title,
            err.actions.primary.label,
            err.actions.secondary and err.actions.secondary.label or "Cancelar"
        )

        if result == "ok" and err.actions.primary.callback then
            err.actions.primary.callback()
        elseif result == "cancel" and err.actions.secondary and err.actions.secondary.callback then
            err.actions.secondary.callback()
        end
    else
        LrDialogs.message(err.title, message, err.level or "info")
    end
end

return {showError = showError, ERROR_CATALOG = ERROR_CATALOG}
```

**Uso:**

```lua
local ErrorMessages = require 'error_messages'

-- Em vez de:
-- showError("Servidor NSP não respondeu...")

-- Fazer:
ErrorMessages.showError("SERVER_UNREACHABLE")
```

**Impacto:**
- ✅ Mensagens claras em português
- ✅ Ações sugeridas (botões)
- ✅ Links para documentação
- ✅ Reduz support tickets 50%+

---

### 1.3. Structured Logging no Servidor

**Problema:** Logs não correlacionados, difícil debugar.

**Solução (45 min):**

```python
# services/logging_config.py
import logging
import sys
import uuid
from pathlib import Path
from datetime import datetime
import structlog

def setup_logging(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)

    # Formatador timestamped
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    # Chain de processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Configurar structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configurar stdlib logging
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=False),
    )

    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"server_{datetime.now():%Y%m%d}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)

# services/server.py
from contextlib import asynccontextmanager
from .logging_config import setup_logging
import structlog

APP_ROOT = Path(__file__).resolve().parent.parent
setup_logging(APP_ROOT / "logs")
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("server_starting", version="2.1.0", pid=os.getpid())
    global ENGINE
    ENGINE = load_engine()
    logger.info("engine_loaded", models=list(ENGINE.lightgbm_models.keys())[:3])
    yield
    logger.info("server_shutdown")

app = FastAPI(title="NSP Plugin Inference API", version="2.1.0", lifespan=lifespan)

@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id, image_path=str(payload.image_path))

    log.info("prediction_started", model=payload.model)

    try:
        image_path, tmp_path = _materialize_input(payload.image_path, payload.preview_b64)

        start_time = time.time()
        if payload.model == "nn":
            sliders = engine.predict_nn(str(image_path), payload.exif)
        else:
            sliders = engine.predict_lightgbm(str(image_path), payload.exif)
        elapsed = time.time() - start_time

        log.info("prediction_completed",
                 elapsed_ms=int(elapsed * 1000),
                 slider_count=len(sliders))

        return PredictResponse(model=payload.model, sliders=sliders)

    except FileNotFoundError:
        log.error("prediction_failed", reason="file_not_found")
        raise HTTPException(status_code=404, detail=f"Imagem não encontrada: {image_path}")
    except Exception as exc:
        log.error("prediction_failed", reason="exception", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
```

**Impacto:**
- ✅ Correlation IDs (rastrear requests)
- ✅ Logs estruturados (fácil parsing)
- ✅ Rotação automática (não encher disco)
- ✅ Debugging 10x mais rápido

---

## 2. Unified Configuration System (Prioridade P0)

**Problema:** Config duplicada em 3 lugares.

**Solução (2h):**

### 2.1. Config Schema (Pydantic)

```python
# services/config.py
from pydantic import BaseSettings, Field, validator
from pathlib import Path
import json
from typing import Optional

class NSPConfig(BaseSettings):
    """
    Single source of truth para configuração NSP.
    Prioridade: ENV vars > nsp_config.json > defaults
    """

    # Paths
    project_root: Path = Field(
        default=Path.home() / "Library/Application Support/NSP",
        description="Diretório raiz da instalação NSP"
    )
    python_bin: Path = Field(
        default=Path("python3"),
        description="Executável Python (venv ou system)"
    )

    # Server
    host: str = Field(default="127.0.0.1", description="Bind host")
    port: int = Field(default=5678, ge=1024, le=65535, description="Porta do servidor")

    # Model
    default_model: str = Field(default="lightgbm", regex="^(lightgbm|nn)$")
    workflow: str = Field(default="catalog", regex="^(catalog|creative)$")

    # Features
    force_auto_horizon: bool = Field(default=True, description="Auto-straighten antes de predição")
    auto_feedback: bool = Field(default=False, description="Enviar feedback automático")
    smart_culling_threshold: float = Field(default=0.4, ge=0.0, le=1.0)

    # Performance
    max_concurrent_predictions: int = Field(default=4, ge=1, le=16)
    embedding_cache_ttl: int = Field(default=86400, description="TTL do cache de embeddings (segundos)")

    # Advanced
    log_level: str = Field(default="INFO", regex="^(DEBUG|INFO|WARNING|ERROR)$")
    enable_telemetry: bool = Field(default=False, description="Crash reporting anónimo")

    class Config:
        env_prefix = "NSP_"
        case_sensitive = False

    @validator("project_root", pre=True)
    def expand_project_root(cls, v):
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v

    @classmethod
    def load(cls):
        """Carrega config de ficheiro (se existir) + env vars"""
        config_path = cls().project_root / "config/nsp_config.json"

        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                return cls(**data)
            except Exception as e:
                logger.warning("config_load_failed", path=str(config_path), error=str(e))

        return cls()

    def save(self):
        """Guarda config para ficheiro"""
        config_path = self.project_root / "config/nsp_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Serializar (excluir campos computados)
        data = self.dict(exclude={"project_root"})
        data["project_root"] = str(self.project_root)
        data["python_bin"] = str(self.python_bin)

        config_path.write_text(json.dumps(data, indent=2))
        logger.info("config_saved", path=str(config_path))

# Global config instance
_config: Optional[NSPConfig] = None

def get_config() -> NSPConfig:
    global _config
    if _config is None:
        _config = NSPConfig.load()
    return _config

def reload_config():
    global _config
    _config = NSPConfig.load()
    return _config
```

### 2.2. Integração no Servidor

```python
# services/server.py
from .config import get_config

config = get_config()

@app.get("/config")
def get_current_config():
    """Endpoint para Control Center sincronizar config"""
    return config.dict()

@app.post("/config")
def update_config(updates: dict):
    """Atualizar config via API"""
    global config
    for key, value in updates.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.save()
    return {"ok": True, "config": config.dict()}
```

### 2.3. Integração no Plugin Lua

```lua
-- NSP-Plugin.lrplugin/config_sync.lua
local function fetchRemoteConfig()
    local response, headers = LrHttp.get(SERVER_URL .. "/config")
    if headers and headers.status == 200 then
        local ok, config = pcall(JSON.decode, response)
        if ok then
            return config
        end
    end
    return nil
end

local function syncPreferences()
    local remote = fetchRemoteConfig()
    if remote then
        prefs.forceAutoHorizon = remote.force_auto_horizon
        prefs.autoFeedback = remote.auto_feedback
        prefs.defaultModel = remote.default_model
    end
end

-- Chamar no startup do plugin
syncPreferences()
```

**Impacto:**
- ✅ Config centralizada (1 fonte de verdade)
- ✅ Validação automática (Pydantic)
- ✅ Sincronização cross-component
- ✅ Env vars support (Docker-friendly)

---

## 3. Bundle Verification Automática (Prioridade P1)

**Problema:** Só valida manualmente, pode correr com modelos corrompidos.

**Solução (1h):**

```python
# services/server.py
from .bundle_verification import verify_bundle_or_fail

@app.on_event("startup")
def startup_event():
    global ENGINE

    # Verificar bundle ANTES de carregar modelos
    verify_bundle_or_fail(config.project_root)

    ENGINE = load_engine()
    logger.info("engine_loaded")

# services/bundle_verification.py
import hashlib
from pathlib import Path
import json

class BundleVerificationError(Exception):
    pass

def compute_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def verify_bundle_or_fail(project_root: Path):
    manifest_path = project_root / "models/model_bundle.lock.json"

    if not manifest_path.exists():
        raise BundleVerificationError(
            f"Manifesto de modelos não encontrado em {manifest_path}. "
            "Corre 'python tools/model_manifest.py' para gerar."
        )

    manifest = json.loads(manifest_path.read_text())

    missing = []
    mismatched = []

    for entry in manifest.get("files", []):
        file_path = project_root / entry["path"]

        if not file_path.exists():
            missing.append(entry["path"])
            continue

        actual_hash = compute_sha256(file_path)
        if actual_hash != entry["sha256"]:
            mismatched.append(entry["path"])

    if missing or mismatched:
        error_msg = "Bundle de modelos inválido:\n"
        if missing:
            error_msg += f"  Ficheiros em falta: {', '.join(missing[:3])}\n"
        if mismatched:
            error_msg += f"  Hashes divergentes: {', '.join(mismatched[:3])}\n"
        error_msg += "\nCorre 'python train/train_sliders.py' para re-treinar."

        raise BundleVerificationError(error_msg)

    logger.info("bundle_verified", files=len(manifest.get("files", [])))
```

**Impacto:**
- ✅ Deteta corrupção de modelos ao arrancar
- ✅ Mensagem clara sobre como resolver
- ✅ Previne crashes silenciosos

---

## 4. Progress Feedback no Plugin (Prioridade P1)

**Problema:** User não sabe o que está a acontecer.

**Solução (30 min):**

```lua
-- NSP-Plugin.lrplugin/Main.lua (atualizar)
LrFunctionContext.callWithContext("NSP Plugin", function(context)
    LrTasks.startAsyncTask(function()
        local total = #photos

        -- Criar progress scope
        local progress = LrProgressScope {
            title = "NSP Plugin",
            caption = string.format("A processar %d fotografia(s)...", total),
            functionContext = context,
        }
        progress:setCancelable(true)

        for index, photo in ipairs(photos) do
            -- Cancelamento
            if progress:isCanceled() then
                showInfo("Processo cancelado. Processadas " .. (index - 1) .. " de " .. total .. " fotografias.")
                return
            end

            -- Update progress
            progress:setPortionComplete(index - 1, total)
            progress:setCaption(string.format("NSP (%d/%d): %s",
                index,
                total,
                LrPathUtils.leafName(photo:getRawMetadata("path"))
            ))

            -- Processar foto
            local response, err = callServerSafe(path, exif, modelToUse)

            if response then
                applyDevelopSettings(photo, response.sliders)
                successCount = successCount + 1
            else
                table.insert(failures, string.format("Foto %d: %s", index, err))
            end
        end

        progress:done()

        -- Resumo final
        if successCount > 0 then
            showInfo(string.format("✓ NSP aplicou ajustes em %d de %d fotografia(s).", successCount, total))
        end
        if #failures > 0 then
            showError("BATCH_ERRORS", table.concat(failures, "\n"))
        end
    end)
end)
```

**Impacto:**
- ✅ Progress bar visível
- ✅ Nome do ficheiro atual
- ✅ Botão de cancelamento
- ✅ Resumo no fim (sucesso vs. falhas)

---

## 5. Auto-Start Reliability (Prioridade P1)

**Problema:** `start_server.sh` pode falhar silenciosamente.

**Solução (1h):**

```bash
#!/usr/bin/env bash
# tools/start_server.sh (refatorado)

set -euo pipefail

# Logging
LOG_FILE="$HOME/Library/Application Support/NSP/logs/auto_start.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $*"
    exit 1
}

# Detetar project root
PROJECT_ROOT="${NSP_PROJECT_ROOT:-$HOME/Library/Application Support/NSP}"
log "Project root: $PROJECT_ROOT"

# Validar estrutura
[[ -d "$PROJECT_ROOT" ]] || error "Project root não existe: $PROJECT_ROOT"
[[ -f "$PROJECT_ROOT/config/nsp_config.json" ]] || error "Config não encontrada: $PROJECT_ROOT/config/nsp_config.json"

# Ler Python bin da config
PYTHON_BIN=$(jq -r '.python_bin // "python3"' "$PROJECT_ROOT/config/nsp_config.json")
log "Python binary: $PYTHON_BIN"

# Validar Python
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    error "Python não encontrado: $PYTHON_BIN"
fi

# Verificar virtualenv
if [[ "$PYTHON_BIN" == *"/venv/"* ]] || [[ "$PYTHON_BIN" == *"/.venv/"* ]]; then
    VENV_DIR=$(dirname "$(dirname "$PYTHON_BIN")")
    [[ -f "$VENV_DIR/bin/activate" ]] || error "Virtualenv inválido: $VENV_DIR"
    log "Usando virtualenv: $VENV_DIR"
fi

# Verificar bundle
if ! "$PYTHON_BIN" -c "from services.bundle_verification import verify_bundle_or_fail; verify_bundle_or_fail('$PROJECT_ROOT')" 2>>"$LOG_FILE"; then
    error "Bundle de modelos inválido. Corre 'python tools/model_manifest.py' para regenerar."
fi

# Arrancar servidor
log "A arrancar servidor..."
cd "$PROJECT_ROOT"

# Matar processo existente (se houver)
pkill -f "uvicorn services.server:app" || true
sleep 1

# Spawn servidor em background
nohup "$PYTHON_BIN" -m uvicorn services.server:app \
    --host 127.0.0.1 \
    --port 5678 \
    >> "$LOG_FILE" 2>&1 &

SERVER_PID=$!
log "Servidor arrancado (PID: $SERVER_PID)"

# Aguardar health check (max 30s)
for i in {1..30}; do
    if curl -sf http://127.0.0.1:5678/health >/dev/null 2>&1; then
        log "Servidor respondeu ao /health (tentativa $i/30)"
        exit 0
    fi
    sleep 1
done

error "Servidor não respondeu ao /health em 30s. Ver logs: $LOG_FILE"
```

**Impacto:**
- ✅ Validações pré-flight (Python exists, venv valid, bundle OK)
- ✅ Logging detalhado (fácil debug)
- ✅ Health check com timeout
- ✅ Kill processo antigo (evita port conflicts)

---

## 6. Control Center: Toast Notifications (Prioridade P2)

**Problema:** User não sabe quando eventos ocorrem (servidor start/stop).

**Solução (30 min):**

```javascript
// control-center/src/main.js (já existe, melhorar)

// Adicionar event listeners para logs
tauriEvent.listen("server-log", (event) => {
  const payload = event?.payload;
  if (!payload) return;

  // Parsear log estruturado
  try {
    const logEntry = JSON.parse(payload.line);

    // Toast para eventos importantes
    if (logEntry.event === "prediction_completed") {
      toast(`Predição completada em ${logEntry.elapsed_ms}ms`, "success");
    } else if (logEntry.event === "prediction_failed") {
      toast(`Erro na predição: ${logEntry.reason}`, "error");
    }
  } catch {
    // Log não estruturado, ignorar
  }

  // Adicionar ao activity log
  pushLog(`[Servidor] ${payload.line}`, payload.stream === "stderr" ? "error" : "info");
});
```

**CSS para toasts mais visíveis:**

```css
/* control-center/src/styles.css */
#toast {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 12px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  opacity: 0;
  transform: translateY(-20px);
  transition: all 0.3s ease;
  z-index: 9999;
  max-width: 400px;
  font-size: 14px;
}

#toast.visible {
  opacity: 1;
  transform: translateY(0);
}

#toast.success {
  border-left: 4px solid var(--success);
}

#toast.error {
  border-left: 4px solid var(--danger);
}

#toast.info {
  border-left: 4px solid var(--primary);
}
```

**Impacto:**
- ✅ Feedback visual imediato
- ✅ Eventos importantes destacados
- ✅ Menos confusão sobre estado do sistema

---

## 7. Deployment: Installer com Pre-Flight Checks (Prioridade P1)

**Problema:** Instalação falha sem validações.

**Solução (2h):**

```bash
#!/usr/bin/env bash
# install/macos/install.sh (refatorado completo)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_ROOT="${NSP_INSTALL_PATH:-$HOME/Library/Application Support/NSP}"
PYTHON_BIN="${NSP_PYTHON:-python3}"

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Pre-flight checks
preflight_checks() {
    log_info "A executar pre-flight checks..."

    # Check 1: macOS version
    local macos_version=$(sw_vers -productVersion)
    log_info "macOS version: $macos_version"

    if [[ "$(echo "$macos_version" | cut -d. -f1)" -lt 11 ]]; then
        log_error "NSP Plugin requer macOS 11 (Big Sur) ou superior."
        exit 1
    fi

    # Check 2: Python version
    if ! command -v "$PYTHON_BIN" &>/dev/null; then
        log_error "Python não encontrado: $PYTHON_BIN"
        log_info "Instala Python 3.9+ via Homebrew: brew install python@3.11"
        exit 1
    fi

    local python_version=$("$PYTHON_BIN" --version | awk '{print $2}')
    log_info "Python version: $python_version"

    local python_major=$(echo "$python_version" | cut -d. -f1)
    local python_minor=$(echo "$python_version" | cut -d. -f2)

    if [[ "$python_major" -lt 3 ]] || [[ "$python_major" -eq 3 && "$python_minor" -lt 9 ]]; then
        log_error "Python 3.9+ é necessário. Encontrado: $python_version"
        exit 1
    fi

    # Check 3: Disk space
    local available_space=$(df -k "$HOME" | awk 'NR==2 {print $4}')
    local required_space=$((2 * 1024 * 1024)) # 2GB in KB

    if [[ "$available_space" -lt "$required_space" ]]; then
        log_error "Espaço em disco insuficiente. Necessário: 2GB, Disponível: $((available_space / 1024 / 1024))GB"
        exit 1
    fi

    # Check 4: Lightroom installed? (warning only)
    if [[ ! -d "/Applications/Adobe Lightroom Classic" ]]; then
        log_warn "Adobe Lightroom Classic não detetado em /Applications"
        log_warn "Garante que o Lightroom está instalado antes de usar o plugin."
    else
        log_info "Adobe Lightroom Classic detetado"
    fi

    log_info "✓ Pre-flight checks passou"
}

# Main installation
main() {
    echo "╔════════════════════════════════════════╗"
    echo "║   NSP Plugin Installer (macOS)         ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    log_info "Origem: $REPO_ROOT"
    log_info "Destino: $TARGET_ROOT"
    echo ""

    preflight_checks

    # Step 1: Copy files
    log_info "A copiar ficheiros..."
    mkdir -p "$TARGET_ROOT"
    rsync -av --delete \
        --exclude ".git" \
        --exclude "venv" \
        --exclude "*.pyc" \
        --exclude "__pycache__" \
        "$REPO_ROOT/" "$TARGET_ROOT/" >/dev/null

    # Step 2: Create virtualenv
    VENV_PATH="$TARGET_ROOT/venv"
    if [[ ! -d "$VENV_PATH" ]]; then
        log_info "A criar virtualenv..."
        "$PYTHON_BIN" -m venv "$VENV_PATH"
    else
        log_info "Virtualenv já existe, a usar existente"
    fi

    # Step 3: Install dependencies
    log_info "A instalar dependências Python (isto pode demorar 5-10 min)..."
    "$VENV_PATH/bin/pip" install --upgrade pip --quiet
    "$VENV_PATH/bin/pip" install -r "$TARGET_ROOT/requirements.txt" --quiet

    # Step 4: Generate config
    log_info "A criar configuração..."
    mkdir -p "$TARGET_ROOT/config"
    cat >"$TARGET_ROOT/config/nsp_config.json"<<EOF
{
  "project_root": "$TARGET_ROOT",
  "python_bin": "$VENV_PATH/bin/python",
  "start_server_script": "$TARGET_ROOT/tools/start_server.sh",
  "host": "127.0.0.1",
  "port": 5678,
  "default_model": "lightgbm",
  "workflow": "catalog",
  "force_auto_horizon": true,
  "auto_feedback": false,
  "log_level": "INFO"
}
EOF

    # Step 5: Symlink plugin
    log_info "A criar atalho do plugin..."
    ln -sfn "$TARGET_ROOT/NSP-Plugin.lrplugin" "$HOME/Documents/NSP Plugin.lrplugin"

    # Step 6: Lightroom Modules dir
    LR_MODULES_DIR="$HOME/Library/Application Support/Adobe/Lightroom/Modules"
    mkdir -p "$LR_MODULES_DIR"
    rsync -a --delete "$TARGET_ROOT/NSP-Plugin.lrplugin/" "$LR_MODULES_DIR/NSP-Plugin.lrplugin/"

    # Step 7: Verify installation
    log_info "A verificar instalação..."
    if "$VENV_PATH/bin/python" -c "import torch, clip, fastapi, lightgbm; print('OK')" 2>/dev/null; then
        log_info "✓ Todas as dependências importadas com sucesso"
    else
        log_error "Falha ao importar dependências. Reinstala com: pip install -r requirements.txt"
        exit 1
    fi

    # Done
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║  ✓ Instalação concluída com sucesso   ║"
    echo "╚════════════════════════════════════════╝"
    echo ""
    log_info "Próximos passos:"
    echo "  1. Abre o NSP Control Center (procura na Spotlight)"
    echo "  2. Configura o caminho do projeto e Python (já pré-preenchido)"
    echo "  3. No Lightroom: File > Plug-in Manager > Add"
    echo "     Aponta para: $HOME/Documents/NSP Plugin.lrplugin"
    echo "  4. Treina o modelo com o teu catálogo (1x, ~30 min)"
    echo "  5. Começa a editar com IA!"
    echo ""
}

main
```

**Impacto:**
- ✅ Deteta problemas ANTES de instalar
- ✅ Mensagens claras (cores, ícones)
- ✅ Validação pós-instalação
- ✅ Próximos passos claros

---

## Resumo de Impacto

| Ação | Tempo | Impacto UX | Impacto Técnico |
|------|-------|------------|-----------------|
| Circuit Breaker | 30 min | 🟢🟢🟢 Alto | 🟢🟢 Médio |
| Error Messages | 1h | 🟢🟢🟢 Alto | 🟢 Baixo |
| Structured Logging | 45 min | 🟢 Baixo | 🟢🟢🟢 Alto |
| Unified Config | 2h | 🟢🟢 Médio | 🟢🟢🟢 Alto |
| Bundle Verification | 1h | 🟢 Baixo | 🟢🟢🟢 Alto |
| Progress Feedback | 30 min | 🟢🟢🟢 Alto | 🟢 Baixo |
| Auto-Start Reliability | 1h | 🟢🟢 Médio | 🟢🟢 Médio |
| Toast Notifications | 30 min | 🟢🟢 Médio | 🟢 Baixo |
| Installer Pre-Flight | 2h | 🟢🟢🟢 Alto | 🟢🟢 Médio |

**Total:** ~9 horas de trabalho

**ROI:**
- Redução de support tickets: **50-70%**
- Aumento de installation success rate: **60% → 90%+**
- User satisfaction (NPS): **+20-30 pontos**
- Time to first successful edit: **15 min → 5 min**

---

## Prioridade de Implementação

### Dia 1 (2-3h)
1. ✅ Error Messages User-Friendly
2. ✅ Circuit Breaker no Plugin Lua
3. ✅ Progress Feedback

### Dia 2 (3-4h)
4. ✅ Unified Configuration System
5. ✅ Bundle Verification Automática

### Dia 3 (2h)
6. ✅ Auto-Start Reliability
7. ✅ Toast Notifications

### Dia 4 (3h)
8. ✅ Structured Logging
9. ✅ Installer Pre-Flight Checks

### Dia 5 (1h)
10. ✅ Testes end-to-end
11. ✅ Documentação atualizada

---

## Validação

Após implementar todas as ações, validar com:

1. **Smoke Test:**
   ```bash
   # Fresh install
   ./install/macos/install.sh

   # Arrancar Control Center
   open -a "NSP Control Center"

   # No Lightroom, adicionar plugin
   # Tentar "NSP – Get AI Edit" (sem servidor a correr)
   # Deve: Auto-start servidor OU mostrar dialog com botão "Abrir Control Center"
   ```

2. **Error Scenarios:**
   - Servidor down → error message clara + ação sugerida
   - Modelo não treinado → dialog com "Treinar Agora"
   - Bundle corrompido → mensagem ao arrancar servidor
   - Config divergente → sincronização automática

3. **Performance:**
   - Installation time < 10 min
   - Server startup < 10s
   - First prediction < 5s

---

## Notas Finais

Estas ações são **quick wins** que podem ser implementadas rapidamente e têm impacto imediato. Não resolvem tudo (ainda falta onboarding wizard, preview antes de aplicar, etc.), mas transformam o produto de "difícil de usar" para "usável por beta testers".

Para features mais complexas, consultar **ANALISE_ARQUITETURA_UX.md** (Roadmap Fase 2 e 3).
