# NSP Plugin – Análise de Arquitetura, UX e Roadmap de Produto

**Data:** 2025-11-09
**Versão:** 1.0
**Autor:** Claude Code (Arquiteto de Software)

---

## Sumário Executivo

O **NSP Plugin** é um sistema completo e funcional de IA local para Adobe Lightroom Classic, com arquitetura híbrida (Plugin Lua ↔ FastAPI ↔ Tauri), MLOps end-to-end e módulos avançados (Smart Culling, Auto-Profiling, Consistency Analysis).

**Estado atual:** Produto MVP funcional, mas com gaps significativos de UX, deployment e robustez que impedem adoção comercial imediata.

**Recomendação estratégica:** Executar roadmap em 3 fases (MVP Refinement → Pro Features → Commercial Launch) com foco em simplificação de deployment, UX unificada e estratégia de monetização clara.

---

## 1. Análise da Arquitetura Atual

### 1.1. Visão Geral do Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADOBE LIGHTROOM CLASSIC                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          NSP-Plugin.lrplugin (Lua SDK 11.0)             │   │
│  │  - Main.lua (Get AI Edit)                               │   │
│  │  - SmartCulling.lua, AutoProfiling.lua                  │   │
│  │  - ConsistencyReport.lua                                │   │
│  │  - SendFeedback.lua, SyncFeedback.lua (Learning Loop)   │   │
│  │  - Preferences.lua, ChooseModel.lua                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────────────┘
                  │ HTTP POST/GET
                  │ localhost:5678
                  │ JSON payloads
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│               SERVIDOR FASTAPI (services/server.py)             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Endpoints:                                              │   │
│  │  - GET  /health          → Status check                 │   │
│  │  - POST /predict         → Inferência (LightGBM/NN)     │   │
│  │  - POST /feedback        → Aprendizagem individual      │   │
│  │  - POST /feedback/bulk   → Sincronização lote           │   │
│  │  - POST /culling/score   → Smart culling batch          │   │
│  │  - POST /profiles/assign → Auto-profiling sugestão      │   │
│  │  - POST /consistency/report → Análise de consistência   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Motores:                                                │   │
│  │  - NSPInferenceEngine (inference.py)                    │   │
│  │    - LightGBM (22 modelos: slider_*.txt)                │   │
│  │    - PyTorch NN (multi_output_nn.pth)                   │   │
│  │    - CLIP embeddings (OpenAI/ViT-B-32)                  │   │
│  │  - CullingEngine (culling.py)                           │   │
│  │  - StyleProfileEngine (profiling.py)                    │   │
│  │  - ConsistencyAnalyzer (consistency.py)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SQLite (data/nsp_plugin.db)                    │
│  - training_data (id_local, embedding, develop_vector, exif)   │
│  - feedback_records (aprendizagem contínua)                     │
│  - profiles (clustering de estilos)                             │
│  - consistency_reports                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              INTERFACES DE GESTÃO                               │
│  ┌────────────────────────┐  ┌─────────────────────────────┐   │
│  │ Control Center (Tauri) │  │ Gradio UI (app_ui.py)       │   │
│  │ - Gestão de processos  │  │ - Pipeline de treino        │   │
│  │ - Workflows            │  │ - Extração de catálogos     │   │
│  │ - Diagnostics          │  │ - Avaliação de modelos      │   │
│  │ - Bundle verification  │  │ - Logs em tempo real        │   │
│  └────────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2. Avaliação de Componentes

#### ✅ Pontos Fortes

1. **Arquitetura modular e extensível**
   - Separação clara entre inferência, treino e gestão
   - Endpoints RESTful bem definidos
   - Dual model approach (LightGBM + Neural Network)

2. **MLOps completo**
   - Pipeline end-to-end (extração → embeddings → PCA → treino → avaliação)
   - Feedback loop funcional (individual + bulk sync)
   - Manifesto de modelos com SHA-256 verification
   - Re-treino incremental

3. **Módulos avançados (ViLearnStyle AI)**
   - Smart Culling com modelo PyTorch
   - Auto-Profiling com clustering
   - Consistency Analysis para lotes

4. **Control Center (Tauri) robusto**
   - Process management (servidor + UI)
   - Diagnostics automáticos
   - Workflow presets
   - Real-time logging

#### ⚠️ Gaps Críticos

1. **Fragmentação de UX**
   - 3 interfaces distintas (Plugin Lua + Gradio + Tauri)
   - Configuração duplicada (`nsp_config.json` + `LrPrefs` + localStorage)
   - Falta de sincronização de estado entre componentes

2. **Deployment complexo**
   - Instalação manual multi-step
   - Dependências Python não empacotadas
   - Falta de auto-updater
   - Sem validação pré-instalação

3. **Error handling frágil**
   - Mensagens de erro genéricas no plugin Lua
   - Timeouts hardcoded
   - Recuperação manual de falhas
   - Logs dispersos (Lua logs, Python logs, Tauri logs)

4. **Onboarding inexistente**
   - Sem wizard de configuração inicial
   - Documentação técnica, não user-facing
   - Falta de validação de catálogo antes do treino

5. **Gestão de estado precária**
   - Auto-start condicional do servidor (pode falhar silenciosamente)
   - Health checks sem retry strategy
   - Processos órfãos possíveis

---

## 2. Análise de User Experience

### 2.1. Fluxos de Trabalho Atuais

#### Fluxo 1: Instalação (First Run)

**Estado atual:**
```
1. Clone/Download repositório
2. Executar ./install/macos/install.sh
3. Abrir Control Center manualmente
4. Configurar paths no Control Center
5. Adicionar plugin no Lightroom Plugin Manager
6. Usar menu "NSP – Preferências" para configurar
```

**Problemas:**
- 6 steps manuais
- Falta de validação em cada step
- Paths absolutos podem quebrar se mover instalação
- Sem rollback se falhar
- Experiência técnica demais para fotógrafos

**Target ideal:**
```
1. Download NSP.dmg
2. Arrastar para Applications
3. Abrir NSP Control Center
4. Wizard de setup:
   a. Auto-detect Lightroom
   b. Escolher modelo inicial (Catálogo/Criativo)
   c. Validar Python/dependencies
   d. Treinar modelo inicial ou usar pré-treinado
5. Plugin auto-instalado e ready
```

#### Fluxo 2: Primeira Edição com IA

**Estado atual:**
```
1. Garantir servidor está running (manual ou auto-start)
2. Selecionar foto no Lightroom
3. File → Plug-in Extras → "NSP – Get AI Edit"
4. (Se servidor não responder, erro genérico)
5. Aguardar aplicação de sliders
6. (Opcional) Ajustar manualmente
7. (Se auto-feedback ativo, envia feedback automático)
```

**Problemas:**
- Feedback de progresso limitado
- Sem preview antes de aplicar
- Não explica "porquê" das edições
- Auto-feedback é opaco (user não sabe quando/o quê aprende)

**Target ideal:**
```
1. Selecionar foto(s)
2. NSP → "Editar com IA"
3. Modal com:
   - Preview side-by-side (antes/depois)
   - Slider importance bars (quais sliders foram mais usados)
   - Confiança da predição (0-100%)
   - Botões: Aplicar | Ajustar | Cancelar
4. Se "Ajustar", aplica e abre painel de feedback inline
5. Learning automático em background
```

#### Fluxo 3: Treino de Modelo

**Estado atual:**
```
1. Control Center → Start Training UI (abre Gradio)
2. Gradio → Upload/selecionar catálogo .lrcat
3. Configurar opções (culling threshold, PCA components, etc.)
4. Executar pipeline completo (10-30 min)
5. Ver MAE em tabela no fim
6. (Sem guidance sobre se MAE é bom/mau)
7. Voltar ao Control Center, restart servidor
```

**Problemas:**
- 2 UIs diferentes (Tauri + Gradio)
- Sem estimativa de tempo
- Sem tutorial sobre configurações
- MAE técnico demais (fotógrafos não percebem)
- Restart manual do servidor

**Target ideal:**
```
1. Control Center → "Treinar Modelo"
2. Wizard integrado:
   a. Selecionar catálogo (com preview de stats)
   b. Escolher qualidade (Rápido/Balanceado/Máximo)
   c. Ver estimativa de tempo
3. Progress bar com sub-steps visíveis
4. Resultados apresentados como:
   - "Modelo pronto! Testado em 50 fotos, precisão 92%"
   - Gráficos visuais (antes/depois de fotos de teste)
5. Auto-restart servidor em background
```

### 2.2. Gaps de UX Priorizados

| Gap | Impacto | Dificuldade | Prioridade |
|-----|---------|-------------|------------|
| **Instalação multi-step manual** | Alto | Médio | 🔴 P0 |
| **Fragmentação UI (Tauri + Gradio + Plugin)** | Alto | Alto | 🟠 P1 |
| **Error messages genéricas** | Alto | Baixo | 🔴 P0 |
| **Falta de onboarding/wizard** | Alto | Médio | 🟠 P1 |
| **Auto-start não confiável** | Médio | Baixo | 🟡 P2 |
| **Sem preview antes de aplicar edições** | Médio | Alto | 🟡 P2 |
| **MAE técnico demais** | Baixo | Baixo | 🟢 P3 |
| **Logs dispersos** | Médio | Médio | 🟡 P2 |

---

## 3. Análise de Robustez e Reliability

### 3.1. Pontos de Falha Identificados

#### 🔴 Critical

1. **Auto-start do servidor**
   - **Problema:** `tools/start_server.sh` pode falhar silenciosamente se `venv` não ativado
   - **Impacto:** Plugin fica inoperável, erro genérico
   - **Solução:** Validar `venv` antes de spawn, fallback para Python system, retry logic

2. **Health check timeout**
   - **Problema:** `SERVER_MAX_WAIT = 25s` hardcoded, sem exponential backoff
   - **Impacto:** Falha em máquinas lentas ou cold start
   - **Solução:** Adaptive timeout baseado em histórico, retry com backoff

3. **Process orphan no Control Center**
   - **Problema:** `Child::kill()` pode deixar processos filhos órfãos
   - **Impacto:** Portas ocupadas, consumo de recursos
   - **Solução:** Process groups, cleanup no shutdown

#### 🟠 High

4. **Bundle verification não automático**
   - **Problema:** Só valida manualmente, pode correr com modelos corrompidos
   - **Impacto:** Predições erradas, crashes
   - **Solução:** Validação automática no startup do servidor

5. **Sincronização de configuração**
   - **Problema:** `nsp_config.json` + `LrPrefs` podem divergir
   - **Impacto:** Comportamento inconsistente
   - **Solução:** Single source of truth, sync mechanism

6. **Embedding generation sem caching**
   - **Problema:** Re-computa embeddings em cada treino mesmo se imagem não mudou
   - **Impacto:** Desperdício de tempo (CLIP é lento)
   - **Solução:** Cache baseado em file hash + timestamp

#### 🟡 Medium

7. **No graceful degradation**
   - **Problema:** Se NN não disponível, não há fallback para LightGBM
   - **Impacto:** Erro completo em vez de funcionalidade reduzida
   - **Solução:** Fallback chain: NN → LightGBM → Default preset

8. **Feedback sem confirmação visual**
   - **Problema:** Auto-feedback envia sem mostrar o que foi enviado
   - **Impacto:** User não confia no sistema
   - **Solução:** Toast notification com resumo ("Ajuste de Exposição +0.3 aprendido")

### 3.2. Estratégias de Error Recovery

#### Implementar Circuit Breaker Pattern
```python
class ServerCircuitBreaker:
    def __init__(self, failure_threshold=3, timeout=60):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()

        try:
            result = func()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise
```

#### Retry Strategy com Exponential Backoff
```python
def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
```

#### Health Check Multi-level
```python
@app.get("/health")
def healthcheck():
    return {
        "status": "ok",
        "models": {
            "lightgbm": check_lightgbm_models(),
            "nn": check_nn_model(),
        },
        "dependencies": {
            "clip": check_clip_available(),
            "database": check_db_connection(),
        },
        "version": get_version(),
        "uptime": get_uptime_seconds(),
    }
```

### 3.3. Logging e Monitoring

**Problema atual:** Logs fragmentados, sem correlação.

**Solução proposta:**

```python
# Structured logging com correlation IDs
import structlog

logger = structlog.get_logger()

@app.post("/predict")
def predict(payload: PredictRequest):
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id, image_path=payload.image_path)

    log.info("prediction_started")
    try:
        result = engine.predict(...)
        log.info("prediction_completed", mae=result.confidence)
        return result
    except Exception as e:
        log.error("prediction_failed", error=str(e))
        raise
```

**Centralizar logs:**
- Todos os logs (Lua, Python, Rust) para `~/Library/Application Support/NSP/logs/`
- Rotação automática (max 10MB por ficheiro)
- Viewer integrado no Control Center

---

## 4. Deployment e Packaging

### 4.1. Estado Atual

**Install script (`install/macos/install.sh`):**
```bash
# Pontos positivos:
✓ Cria estrutura de diretórios
✓ Copia bundle para ~/Library/Application Support/NSP
✓ Cria virtualenv
✓ Gera config/nsp_config.json

# Problemas:
✗ Depende de Python system (pode não existir ou versão errada)
✗ Não valida pré-requisitos
✗ Sem tratamento de erros (set -e mata script)
✗ Não instala dependências opcionais (rawpy para RAW)
✗ Não verifica se Lightroom está instalado
✗ Não cria atalho na Dock
```

### 4.2. Estratégia de Packaging Melhorada

#### Opção A: PyInstaller Bundle (Atual Roadmap)

**Vantagens:**
- Elimina dependência de Python system
- Bundle auto-contido
- Arranque mais rápido

**Desvantagens:**
- Bundle grande (~500MB com PyTorch + CLIP)
- Dificulta updates de modelos
- Complexo de debugar

**Implementação:**
```bash
# Gerar executável
pyinstaller \
  --onefile \
  --name nsp-engine \
  --add-data "models:models" \
  --add-data "services:services" \
  --hidden-import torch \
  --hidden-import clip \
  services/server.py

# Integrar no Control Center
# Control Center chama ~/Library/Application Support/NSP/bin/nsp-engine
```

#### Opção B: Conda/Micromamba Bundle (Recomendado)

**Vantagens:**
- Ambiente Python isolado e reproduzível
- Easier para incluir dependências binárias (rawpy, etc.)
- Updates de modelos simples
- Compatibilidade multi-plataforma (macOS Intel/ARM)

**Implementação:**
```yaml
# environment.yml
name: nsp
channels:
  - conda-forge
  - pytorch
dependencies:
  - python=3.11
  - pytorch::pytorch
  - torchvision
  - fastapi
  - uvicorn
  - lightgbm
  - scikit-learn
  - clip
  - gradio
  - rawpy
  - pip:
    - pydantic
```

**Install script refatorizado:**
```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Detect architecture
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
  CONDA_INSTALLER="Mambaforge-MacOSX-arm64.sh"
else
  CONDA_INSTALLER="Mambaforge-MacOSX-x86_64.sh"
fi

# 2. Install Mambaforge se não existir
if ! command -v mamba &>/dev/null; then
  echo "Installing Mambaforge..."
  curl -L -o /tmp/mambaforge.sh \
    "https://github.com/conda-forge/miniforge/releases/latest/download/$CONDA_INSTALLER"
  bash /tmp/mambaforge.sh -b -p "$TARGET_ROOT/mambaforge"
  rm /tmp/mambaforge.sh
fi

# 3. Create environment
"$TARGET_ROOT/mambaforge/bin/mamba" env create -f environment.yml -p "$TARGET_ROOT/env" -y

# 4. Verify installation
"$TARGET_ROOT/env/bin/python" -c "import torch, clip, fastapi; print('OK')"
```

### 4.3. Distribuição

#### macOS DMG (Short-term)

```
NSP Plugin v1.0.dmg
├── NSP Control Center.app (Tauri)
├── NSP-Plugin.lrplugin (symlink)
├── Install NSP.command (script with UI feedback)
└── README.html
```

**Fluxo:**
1. Montar DMG
2. Correr "Install NSP.command"
3. Script abre janela de progresso (AppleScript + osascript)
4. Valida pré-requisitos → Instala env → Configura plugin → Abre Control Center

#### macOS PKG (Medium-term, Commercial)

- Installer nativo do macOS
- Opções customizadas (Install for all users vs. current user)
- Code signing + notarization (Apple Developer ID)
- Auto-update via Sparkle framework

#### Future: Mac App Store

**Desafios:**
- Sandboxing (acesso ao catálogo Lightroom)
- Plugin installation (user-level vs. system-level)
- Review process (ML models)

**Solução:**
- App principal no App Store (Control Center + Treino)
- Plugin distribuído via download direto (permitido pelo Lightroom)
- In-App Purchase para features Pro

---

## 5. Redesign de Fluxos Críticos

### 5.1. Unified Configuration System

**Problema:** 3 sources of truth (`nsp_config.json`, `LrPrefs`, Control Center localStorage)

**Solução:**

```python
# services/config.py
from pydantic import BaseSettings, Field
from pathlib import Path
import json

class NSPConfig(BaseSettings):
    # Paths
    project_root: Path = Field(default=Path.home() / "Library/Application Support/NSP")
    python_bin: Path = Field(default=...)

    # Server
    host: str = "127.0.0.1"
    port: int = 5678

    # Model
    default_model: str = "lightgbm"  # ou "nn"
    workflow: str = "catalog"  # ou "creative"

    # Features
    force_auto_horizon: bool = True
    auto_feedback: bool = False
    smart_culling_threshold: float = 0.4

    # Advanced
    max_concurrent_predictions: int = 4
    embedding_cache_ttl: int = 86400  # 24h

    class Config:
        env_prefix = "NSP_"

    @classmethod
    def load(cls):
        config_path = cls().project_root / "config/nsp_config.json"
        if config_path.exists():
            return cls(**json.loads(config_path.read_text()))
        return cls()

    def save(self):
        config_path = self.project_root / "config/nsp_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(self.json(indent=2))
```

**Integração:**
- Plugin Lua lê de `nsp_config.json` (source of truth)
- Control Center edita via Tauri command
- Server usa Pydantic Settings (valida + default values)

### 5.2. Smart Auto-Start com Fallback Chain

```python
# services/lifecycle.py
import subprocess
import time
from typing import Optional
from enum import Enum

class ServerStatus(Enum):
    RUNNING = "running"
    STARTING = "starting"
    STOPPED = "stopped"
    FAILED = "failed"

class ServerManager:
    def __init__(self, config: NSPConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.status = ServerStatus.STOPPED

    def start(self, timeout: int = 30) -> bool:
        if self.status == ServerStatus.RUNNING:
            return True

        self.status = ServerStatus.STARTING

        # 1. Tentar via script configurado
        if self._try_configured_script():
            return self._wait_for_health(timeout)

        # 2. Fallback: arranque direto via uvicorn
        if self._try_direct_uvicorn():
            return self._wait_for_health(timeout)

        # 3. Fallback: sugerir instalação
        self.status = ServerStatus.FAILED
        return False

    def _try_configured_script(self) -> bool:
        script = self.config.project_root / "tools/start_server.sh"
        if not script.exists():
            return False
        try:
            self.process = subprocess.Popen(
                ["/usr/bin/env", "bash", str(script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        except Exception:
            return False

    def _try_direct_uvicorn(self) -> bool:
        try:
            self.process = subprocess.Popen(
                [
                    str(self.config.python_bin),
                    "-m", "uvicorn",
                    "services.server:app",
                    "--host", self.config.host,
                    "--port", str(self.config.port)
                ],
                cwd=str(self.config.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        except Exception:
            return False

    def _wait_for_health(self, timeout: int) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self._check_health():
                self.status = ServerStatus.RUNNING
                return True
            time.sleep(0.5)
        self.status = ServerStatus.FAILED
        return False

    def _check_health(self) -> bool:
        import requests
        try:
            resp = requests.get(
                f"http://{self.config.host}:{self.config.port}/health",
                timeout=1
            )
            return resp.status_code == 200
        except:
            return False
```

**Integração no Plugin Lua:**
```lua
local function ensureServerRunning()
    local health_ok, _ = LrHttp.get(SERVER_URL .. "/health")
    if health_ok then
        return true
    end

    -- Pedir ao Control Center para arrancar (via AppleScript ou TCP socket)
    local ok = LrTasks.execute("open 'nspplugin://start-server'")
    if not ok then
        showError("Arranca o NSP Control Center e tenta novamente.")
        return false
    end

    -- Aguardar até 30s
    for i = 1, 30 do
        LrTasks.sleep(1)
        health_ok, _ = LrHttp.get(SERVER_URL .. "/health")
        if health_ok then
            return true
        end
    end

    return false
end
```

### 5.3. Unified Onboarding Wizard

**Control Center: First Run Experience**

```javascript
// control-center/src/onboarding.js

const ONBOARDING_STEPS = [
  {
    id: "welcome",
    title: "Bem-vindo ao NSP Plugin",
    component: WelcomeScreen,
  },
  {
    id: "lightroom-detect",
    title: "Detetar Adobe Lightroom",
    component: LightroomDetection,
    validate: async () => {
      const lrPath = await detectLightroom();
      return { valid: !!lrPath, data: { lrPath } };
    },
  },
  {
    id: "workflow-choice",
    title: "Escolher Modo de Trabalho",
    component: WorkflowChoice,
    options: [
      {
        id: "catalog",
        label: "Catálogo Gigante",
        description: "Milhares de fotos, velocidade máxima (LightGBM)",
      },
      {
        id: "creative",
        label: "Modo Criativo",
        description: "Sessões premium, qualidade artística (Neural Network)",
      },
    ],
  },
  {
    id: "dependencies",
    title: "Instalar Dependências",
    component: DependencyInstaller,
    action: async (context) => {
      await installPythonEnv(context.projectRoot);
    },
  },
  {
    id: "initial-training",
    title: "Treinar Modelo Inicial",
    component: InitialTraining,
    options: [
      {
        id: "use-pretrained",
        label: "Usar Modelo Pré-treinado",
        description: "Começar imediatamente (recomendado)",
      },
      {
        id: "train-from-catalog",
        label: "Treinar do Meu Catálogo",
        description: "Personalizar desde o início (30-60 min)",
      },
    ],
  },
  {
    id: "complete",
    title: "Tudo Pronto!",
    component: OnboardingComplete,
  },
];
```

### 5.4. Error Messages User-Friendly

**Antes (Plugin Lua):**
```lua
showError("Servidor NSP não respondeu. Garante que executaste `uvicorn services.server:app --host 127.0.0.1 --port 5678`.")
```

**Depois:**
```lua
local ERROR_MESSAGES = {
    SERVER_UNREACHABLE = {
        title = "Servidor NSP não está disponível",
        message = "O NSP Control Center precisa estar a correr para usar o plugin.",
        actions = {
            {label = "Abrir Control Center", callback = openControlCenter},
            {label = "Resolver Manualmente", callback = openTroubleshooting}
        }
    },
    NO_PHOTOS_SELECTED = {
        title = "Nenhuma foto selecionada",
        message = "Seleciona pelo menos uma foto na grelha antes de usar o NSP.",
    },
    MODEL_NOT_TRAINED = {
        title = "Modelo ainda não foi treinado",
        message = "Precisas de treinar o modelo com o teu catálogo antes de usar o plugin.",
        actions = {
            {label = "Treinar Agora", callback = openTrainingUI}
        }
    }
}

function showErrorWithContext(errorType, context)
    local err = ERROR_MESSAGES[errorType]
    if not err then
        showError("Erro desconhecido: " .. tostring(errorType))
        return
    end

    -- Dialog com botões de ação
    local result = LrDialogs.presentModalDialog({
        title = err.title,
        message = err.message,
        actionVerb = err.actions and err.actions[1].label or "OK",
        cancelVerb = err.actions and #err.actions > 1 and err.actions[2].label or nil
    })

    if result == "ok" and err.actions and err.actions[1].callback then
        err.actions[1].callback(context)
    end
end
```

---

## 6. Roadmap de Produto

### Fase 1: MVP Refinement (2-3 semanas)

**Objetivo:** Transformar protótipo funcional em produto MVP pronto para beta testers.

#### Sprint 1: Robustez e Reliability (Semana 1)
- [ ] **P0:** Implementar Circuit Breaker no server client (Lua + Tauri)
- [ ] **P0:** Retry strategy com exponential backoff
- [ ] **P0:** Graceful degradation (NN → LightGBM → Preset fallback)
- [ ] **P0:** Bundle verification automática no startup
- [ ] **P0:** Process cleanup no shutdown (process groups)
- [ ] **P1:** Logging centralizado (structured logs com correlation IDs)
- [ ] **P1:** Health check multi-level (/health/deep)

#### Sprint 2: UX Critical (Semana 2)
- [ ] **P0:** Error messages user-friendly (todas as 15+ mensagens)
- [ ] **P0:** Onboarding wizard no Control Center (5 steps)
- [ ] **P0:** Unified config system (single source of truth)
- [ ] **P1:** Progress feedback no plugin (LrProgressScope + estimates)
- [ ] **P1:** Toast notifications no Control Center (server events)
- [ ] **P2:** Log viewer integrado (últimos 100 eventos)

#### Sprint 3: Deployment Simplificado (Semana 3)
- [ ] **P0:** Installer refatorizado (pre-requisites check + progress UI)
- [ ] **P0:** DMG packaging (drag-and-drop + Install script)
- [ ] **P1:** Auto-detect Lightroom + catálogo default
- [ ] **P1:** Pré-validação de catálogo (antes de treino)
- [ ] **P2:** Modelo pré-treinado incluído (sample dataset)

**Entregável:** NSP Plugin v1.0-beta (DMG para macOS)

---

### Fase 2: Pro Features (4-6 semanas)

**Objetivo:** Adicionar funcionalidades diferenciadas para utilizadores profissionais.

#### Feature Set A: Advanced AI (Semanas 4-5)
- [ ] **Batch processing otimizado** (multi-threading, queue)
- [ ] **Smart Culling UI integrada** (slider de agressividade, preview)
- [ ] **Auto-Profiling visual** (galeria de estilos, thumbnails)
- [ ] **Consistency Analyzer dashboard** (gráficos de distribuição)
- [ ] **Custom presets AI-assisted** (user cria preset, IA sugere ajustes)

#### Feature Set B: Learning & Personalization (Semana 6)
- [ ] **Feedback UI melhorada** (slider diff visual, antes/depois)
- [ ] **Learning analytics** (dashboard de progresso do modelo)
- [ ] **Style transfer** (aplicar estilo de foto A em foto B)
- [ ] **A/B testing** (comparar LightGBM vs NN side-by-side)

#### Feature Set C: Integration & Export (Semanas 7-8)
- [ ] **Export de presets Lightroom** (desenvolver vector → .lrtemplate)
- [ ] **Sincronização cloud** (backup de modelos, Google Drive/Dropbox)
- [ ] **API externa** (permitir scripts custom via REST)
- [ ] **Plugin para Capture One** (port da lógica Lua)

#### Feature Set D: Performance & Scale (Semana 9)
- [ ] **GPU acceleration** (MPS no Apple Silicon, CUDA no Windows)
- [ ] **Model quantization** (reduzir tamanho NN 50-70%)
- [ ] **Embedding cache inteligente** (baseado em hash + timestamp)
- [ ] **Incremental training** (re-treino só com fotos novas)

**Entregável:** NSP Plugin v1.5-pro (com tier Pro pago)

---

### Fase 3: Commercial Launch (8-12 semanas)

**Objetivo:** Produto comercial com licenciamento, support e marketing.

#### Milestone 1: Licensing System (Semanas 10-11)
- [ ] License key generation (RSA signature)
- [ ] Online activation (servidor de licenças)
- [ ] Offline grace period (30 dias)
- [ ] License transfer (até 3 máquinas)
- [ ] Trial mode (14 dias, watermark nas predições)

#### Milestone 2: Auto-Update (Semana 12)
- [ ] Update checker (versão + changelog)
- [ ] Delta updates (só ficheiros modificados)
- [ ] Rollback automático (se update falhar)
- [ ] Beta channel (early access para testers)

#### Milestone 3: Support Infrastructure (Semanas 13-14)
- [ ] In-app diagnostics export (logs + config + system info)
- [ ] Crash reporter (sentry.io ou similar)
- [ ] Knowledge base integrada (FAQs, troubleshooting)
- [ ] Support ticket system (Zendesk/Intercom)

#### Milestone 4: Marketing & Distribution (Semanas 15-16)
- [ ] Website de produto (landing page + documentação)
- [ ] Vídeos tutoriais (YouTube: Install, First Edit, Training)
- [ ] Case studies (fotógrafos profissionais)
- [ ] Partnership program (educators, influencers)

#### Milestone 5: Multi-Platform (Semanas 17-20, Opcional)
- [ ] Windows support (Tauri build, installer .exe)
- [ ] Linux support (AppImage ou Flatpak)
- [ ] Lightroom CC plugin (diferente de Classic)

**Entregável:** NSP Plugin v2.0-commercial

---

## 7. Modelo de Monetização

### Tier Comparison

| Feature | Free (Hobbyist) | Pro | Studio |
|---------|----------------|-----|--------|
| **Preço** | $0 | $49/year | $199/year |
| **Edições IA/mês** | 100 | Unlimited | Unlimited |
| **Modelos** | LightGBM only | LightGBM + NN | + Custom NN |
| **Treino** | Manual | Auto-retrain | + Cloud training |
| **Smart Culling** | ❌ | ✅ | ✅ |
| **Auto-Profiling** | ❌ | ✅ | ✅ + Custom |
| **Consistency** | ❌ | ✅ | ✅ + Reports |
| **Batch processing** | Max 10 fotos | Unlimited | Unlimited |
| **Support** | Community | Email (48h) | Priority (4h) |
| **Commercial use** | ❌ | ✅ | ✅ |
| **Team licenses** | ❌ | ❌ | ✅ (5+ seats) |

### Revenue Projections (Conservador)

**Assumptions:**
- Target: Fotógrafos profissionais (weddings, events, portraits)
- Market size: 50,000 potenciais users (PT + BR + EN markets)
- Conversion: 5% Free → Pro, 1% Free → Studio

**Year 1:**
- Installs: 1,000 (marketing inicial)
- Pro: 50 × $49 = $2,450
- Studio: 10 × $199 = $1,990
- **Total: $4,440**

**Year 2:**
- Installs: 5,000 (word-of-mouth + SEO)
- Pro: 250 × $49 = $12,250
- Studio: 50 × $199 = $9,950
- **Total: $22,200**

**Year 3:**
- Installs: 15,000
- Pro: 750 × $49 = $36,750
- Studio: 150 × $199 = $29,850
- **Total: $66,600**

---

## 8. Métricas de Sucesso

### Product Metrics

| Métrica | Baseline (atual) | Target MVP | Target Pro | Target Commercial |
|---------|-----------------|------------|------------|-------------------|
| **Time to First Edit** | ~15 min | <5 min | <2 min | <1 min |
| **Installation Success Rate** | ~60% (estimado) | >90% | >95% | >98% |
| **Server Auto-Start Success** | ~70% | >95% | >98% | >99% |
| **Average Error Rate** | ~10% | <2% | <1% | <0.5% |
| **MAE (LightGBM)** | 16.5 | <12 | <10 | <8 |
| **User Satisfaction (NPS)** | N/A | >40 | >60 | >70 |

### Business Metrics

| Métrica | Target Year 1 | Target Year 2 | Target Year 3 |
|---------|--------------|--------------|--------------|
| **Total Users** | 1,000 | 5,000 | 15,000 |
| **Pro Subscribers** | 50 | 250 | 750 |
| **Studio Subscribers** | 10 | 50 | 150 |
| **MRR** | $370 | $1,850 | $5,550 |
| **Churn Rate** | <5%/month | <3%/month | <2%/month |
| **Support Tickets** | <10/week | <30/week | <80/week |

---

## 9. Riscos e Mitigações

### Technical Risks

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| **Modelo não generaliza** | Médio | Alto | Dataset curado, transfer learning, ensembles |
| **Performance em RAW** | Médio | Médio | Cache agressivo, GPU accel, preview mode |
| **Compatibilidade Lightroom** | Baixo | Alto | Testes automáticos, versioning, deprecation plan |
| **Dependências Python** | Médio | Médio | Conda lock, vendoring, fallback versions |
| **Crash em produção** | Médio | Alto | Crash reporter, auto-recovery, safe mode |

### Business Risks

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| **Low adoption** | Médio | Alto | Beta program, influencers, free tier generoso |
| **Competitor** | Baixo | Médio | Diferenciação (local AI, privacy), patents |
| **Lightroom API changes** | Baixo | Alto | Community engagement, Adobe partnership |
| **Pricing resistance** | Médio | Médio | Trial period, pricing experiments, bundles |

### Legal/Privacy Risks

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| **GDPR compliance** | Baixo | Médio | Local-only processing, data export, deletion |
| **Copyright (training data)** | Baixo | Alto | User owns data, clear ToS, no cloud upload |
| **Model IP** | Baixo | Médio | License terms, DRM nos modelos comerciais |

---

## 10. Recomendações Estratégicas

### Curto Prazo (Próximos 30 dias)

1. **Priorizar Fase 1 completa**
   - Foco total em robustez e UX básica
   - Goal: Demo publicamente sem crashes

2. **Recrutar 10 beta testers**
   - Fotógrafos profissionais (weddings, portraits)
   - Coletar feedback estruturado (survey + interviews)

3. **Criar landing page**
   - Explicar valor (tempo poupado, consistência)
   - Waitlist para launch
   - SEO básico (Lightroom AI plugin, etc.)

4. **Definir pricing final**
   - A/B test com beta testers (reactions a tiers)
   - Considerar lifetime deal para early adopters

### Médio Prazo (3-6 meses)

1. **Launch Pro tier**
   - Marketing push (Product Hunt, photography forums)
   - Partnership com 2-3 educators/influencers
   - Target: 100 paying users

2. **Iterar em feedback**
   - Weekly releases com melhorias
   - Public roadmap (transparent, community-driven)

3. **Expandir dataset**
   - Partnerships com fotógrafos (treinar modelo universal)
   - Crowdsourced learning (opt-in, anonymizado)

### Longo Prazo (6-12 meses)

1. **Multi-platform**
   - Windows (maior mercado)
   - Capture One (nicho premium)

2. **Cloud offering** (opcional)
   - Training-as-a-Service (users sem GPU)
   - Model marketplace (comprar estilos pré-treinados)

3. **Enterprise tier**
   - Studios com 10+ fotógrafos
   - Central model management
   - Analytics dashboard

---

## 11. Conclusão

O **NSP Plugin** tem fundações sólidas de arquitetura e um motor de ML funcional. Os gaps principais são de **UX** (fragmentação, onboarding), **deployment** (complexidade, falta de packaging) e **reliability** (error handling, auto-start).

A execução do **Roadmap Fase 1** (MVP Refinement) é crítica e deve ser prioridade máxima. Com ~3 semanas de trabalho focado, o produto pode passar de "protótipo técnico impressionante" para "ferramenta que fotógrafos realmente usam diariamente".

**Próximos passos imediatos:**
1. Implementar Circuit Breaker + Retry Logic (2 dias)
2. Redesign de error messages (1 dia)
3. Onboarding wizard (3 dias)
4. Installer refatorizado (2 dias)
5. DMG packaging (1 dia)
6. Beta testing round 1 (1 semana)

**Potencial comercial:** Com execução sólida das 3 fases, projeção realista de **$66k ARR em 36 meses** (conservador). Com marketing agressivo e features diferenciadas, potencial para **$200k+ ARR**.

---

**Documento gerado por:** Claude Code (Sonnet 4.5)
**Para questões técnicas:** Consultar `/docs/` ou abrir issue no repositório
**Feedback:** Bem-vindo via Pull Request ou discussion
