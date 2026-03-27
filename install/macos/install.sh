#!/usr/bin/env bash
#
# NSP Plugin - macOS Installation Script
# Production-ready installer with pre-flight checks, rollback, and validation
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_ROOT="${NSP_INSTALL_PATH:-$HOME/Library/Application Support/NSP}"
PYTHON_BIN="${NSP_PYTHON:-python3}"
LOG_FILE="${TARGET_ROOT}_install.log"
BACKUP_DIR="${TARGET_ROOT}.backup.$(date +%Y%m%d_%H%M%S)"

MIN_PYTHON_VERSION="3.9"
MIN_DISK_SPACE_MB=500
DRY_RUN=false
UNINSTALL=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[${timestamp}]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[${timestamp}] ERROR:${NC} $*" | tee -a "$LOG_FILE"
}

log_warning() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[${timestamp}] WARNING:${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[${timestamp}] SUCCESS:${NC} $*" | tee -a "$LOG_FILE"
}

show_usage() {
    cat <<EOF
NSP Plugin - macOS Installation Script

Usage:
    $0 [options]

Options:
    --dry-run       Mostra o que seria feito sem executar
    --uninstall     Remove instalação existente
    --help          Mostra esta mensagem

Environment Variables:
    NSP_INSTALL_PATH    Directório de instalação (default: ~/Library/Application Support/NSP)
    NSP_PYTHON          Binário Python a usar (default: python3)

Examples:
    $0                              # Instalação normal
    $0 --dry-run                    # Preview das operações
    $0 --uninstall                  # Remover instalação
    NSP_PYTHON=python3.11 $0        # Usar Python específico
EOF
}

check_command() {
    local cmd=$1
    if ! command -v "$cmd" &>/dev/null; then
        log_error "Comando necessário não encontrado: $cmd"
        return 1
    fi
    return 0
}

check_python_version() {
    local python_cmd=$1
    if ! command -v "$python_cmd" &>/dev/null; then
        log_error "Python não encontrado: $python_cmd"
        return 1
    fi

    local version=$($python_cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
    if [[ -z "$version" ]]; then
        log_error "Não foi possível determinar versão do Python"
        return 1
    fi

    log "Python version detectada: $version"

    # Compare versions (simple numeric comparison)
    if awk "BEGIN {exit !($version >= $MIN_PYTHON_VERSION)}"; then
        return 0
    else
        log_error "Python $version é inferior à versão mínima $MIN_PYTHON_VERSION"
        return 1
    fi
}

check_disk_space() {
    local target_dir=$1
    local parent_dir=$(dirname "$target_dir")

    # Get available space in MB
    local available_mb=$(df -m "$parent_dir" | awk 'NR==2 {print $4}')

    log "Espaço disponível: ${available_mb}MB"

    if [[ $available_mb -lt $MIN_DISK_SPACE_MB ]]; then
        log_error "Espaço insuficiente. Necessário: ${MIN_DISK_SPACE_MB}MB, Disponível: ${available_mb}MB"
        return 1
    fi
    return 0
}

backup_existing_installation() {
    if [[ -d "$TARGET_ROOT" ]]; then
        log "A criar backup da instalação existente em: $BACKUP_DIR"
        if [[ "$DRY_RUN" == false ]]; then
            cp -R "$TARGET_ROOT" "$BACKUP_DIR"
            log_success "Backup criado com sucesso"
        else
            log "[DRY-RUN] Seria criado backup em: $BACKUP_DIR"
        fi
        return 0
    fi
    log "Nenhuma instalação existente encontrada"
    return 0
}

rollback() {
    log_error "Instalação falhou. A reverter para backup..."

    if [[ -d "$BACKUP_DIR" ]]; then
        rm -rf "$TARGET_ROOT"
        mv "$BACKUP_DIR" "$TARGET_ROOT"
        log_success "Rollback concluído. Instalação anterior restaurada."
    else
        log_warning "Nenhum backup disponível para rollback"
    fi

    exit 1
}

validate_installation() {
    log "A validar instalação..."

    local critical_files=(
        "$TARGET_ROOT/services/server.py"
        "$TARGET_ROOT/NSP-Plugin.lrplugin/Info.lua"
        "$TARGET_ROOT/NSP-Plugin.lrplugin/Main.lua"
        "$TARGET_ROOT/requirements.txt"
        "$TARGET_ROOT/venv/bin/python"
        "$TARGET_ROOT/config/nsp_config.json"
    )

    local errors=0
    for file in "${critical_files[@]}"; do
        if [[ ! -e "$file" ]]; then
            log_error "Ficheiro crítico não encontrado: $file"
            ((errors++))
        fi
    done

    if [[ $errors -gt 0 ]]; then
        log_error "Validação falhou: $errors ficheiros críticos em falta"
        return 1
    fi

    # Test Python environment
    log "A testar ambiente Python..."
    if ! "$TARGET_ROOT/venv/bin/python" -c "import fastapi, lightgbm, torch" 2>/dev/null; then
        log_error "Dependências Python não instaladas corretamente"
        return 1
    fi

    log_success "Validação concluída com sucesso"
    return 0
}

uninstall() {
    log "A remover instalação NSP..."

    local paths_to_remove=(
        "$TARGET_ROOT"
        "$HOME/Documents/NSP Plugin.lrplugin"
        "$HOME/Library/Application Support/Adobe/Lightroom/Modules/NSP-Plugin.lrplugin"
    )

    for path in "${paths_to_remove[@]}"; do
        if [[ -e "$path" ]]; then
            log "A remover: $path"
            if [[ "$DRY_RUN" == false ]]; then
                rm -rf "$path"
            else
                log "[DRY-RUN] Seria removido: $path"
            fi
        fi
    done

    log_success "Desinstalação concluída"
    exit 0
}

# ============================================================================
# MAIN INSTALLATION FLOW
# ============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                log "MODO DRY-RUN: Nenhuma alteração será feita"
                shift
                ;;
            --uninstall)
                UNINSTALL=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Opção desconhecida: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Handle uninstall
    if [[ "$UNINSTALL" == true ]]; then
        uninstall
    fi

    # Banner
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           NSP Plugin - macOS Installer v2.0                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    log "Origem: $REPO_ROOT"
    log "Destino: $TARGET_ROOT"
    log "Log file: $LOG_FILE"
    echo ""

    # Setup trap for rollback on error
    if [[ "$DRY_RUN" == false ]]; then
        trap rollback ERR
    fi

    # ========================================================================
    # PHASE 1: PRE-FLIGHT CHECKS
    # ========================================================================

    log "┌─ PHASE 1: Pre-flight Checks"

    log "  → A verificar comandos necessários..."
    check_command rsync || exit 1
    check_command python3 || exit 1
    check_command pip || log_warning "pip não encontrado (pode causar problemas)"

    log "  → A verificar versão do Python..."
    check_python_version "$PYTHON_BIN" || exit 1

    log "  → A verificar espaço em disco..."
    check_disk_space "$TARGET_ROOT" || exit 1

    log_success "└─ Pre-flight checks concluídos"
    echo ""

    # ========================================================================
    # PHASE 2: BACKUP
    # ========================================================================

    log "┌─ PHASE 2: Backup"
    backup_existing_installation
    log_success "└─ Backup concluído"
    echo ""

    # ========================================================================
    # PHASE 3: INSTALLATION
    # ========================================================================

    log "┌─ PHASE 3: Instalação"

    if [[ "$DRY_RUN" == false ]]; then
        log "  → A criar directório de instalação..."
        mkdir -p "$TARGET_ROOT"

        log "  → A copiar ficheiros (pode demorar)..."
        rsync -av --delete \
            --exclude ".git" \
            --exclude "venv" \
            --exclude "*.pyc" \
            --exclude "__pycache__" \
            --exclude ".DS_Store" \
            "$REPO_ROOT/" "$TARGET_ROOT/" | tee -a "$LOG_FILE" | grep -v "/$" | tail -n 10

        log "  → A criar virtualenv Python..."
        VENV_PATH="$TARGET_ROOT/venv"
        if [[ ! -d "$VENV_PATH" ]]; then
            "$PYTHON_BIN" -m venv "$VENV_PATH"
        fi

        log "  → A instalar dependências Python (pode demorar vários minutos)..."
        "$VENV_PATH/bin/pip" install --upgrade pip --quiet
        "$VENV_PATH/bin/pip" install -r "$TARGET_ROOT/requirements.txt" --quiet

        log "  → A gerar ficheiro de configuração..."
        mkdir -p "$TARGET_ROOT/config"
        cat >"$TARGET_ROOT/config/nsp_config.json"<<EOF
{
  "project_root": "$TARGET_ROOT",
  "python_bin": "$VENV_PATH/bin/python",
  "start_server_script": "$TARGET_ROOT/tools/start_server.sh",
  "default_model": "nn",
  "force_auto_horizon": true,
  "auto_feedback": false
}
EOF

        log "  → A criar symlink para ~/Documents..."
        ln -sfn "$TARGET_ROOT/NSP-Plugin.lrplugin" "$HOME/Documents/NSP Plugin.lrplugin"

        log "  → A instalar plugin no Lightroom..."
        LR_MODULES_DIR="$HOME/Library/Application Support/Adobe/Lightroom/Modules"
        LR_PLUGIN_TARGET="$LR_MODULES_DIR/NSP-Plugin.lrplugin"
        mkdir -p "$LR_PLUGIN_TARGET"
        rsync -a --delete "$TARGET_ROOT/NSP-Plugin.lrplugin/" "$LR_PLUGIN_TARGET/"

        log_success "└─ Instalação concluída"
        echo ""

        # ====================================================================
        # PHASE 4: VALIDATION
        # ====================================================================

        log "┌─ PHASE 4: Validação"
        validate_installation || rollback
        log_success "└─ Validação concluída"
        echo ""

        # ====================================================================
        # PHASE 5: CLEANUP
        # ====================================================================

        log "┌─ PHASE 5: Cleanup"
        log "  → A remover backup (sucesso confirmado)..."
        if [[ -d "$BACKUP_DIR" ]]; then
            rm -rf "$BACKUP_DIR"
        fi
        log_success "└─ Cleanup concluído"

    else
        log "[DRY-RUN] mkdir -p \"$TARGET_ROOT\""
        log "[DRY-RUN] rsync -av --delete \"$REPO_ROOT/\" \"$TARGET_ROOT/\""
        log "[DRY-RUN] python3 -m venv \"$TARGET_ROOT/venv\""
        log "[DRY-RUN] pip install -r requirements.txt"
        log "[DRY-RUN] Criar config em $TARGET_ROOT/config/nsp_config.json"
        log "[DRY-RUN] ln -sfn plugin para ~/Documents"
        log "[DRY-RUN] Copiar plugin para Lightroom Modules"
    fi

    # Disable trap
    trap - ERR

    # ========================================================================
    # SUCCESS SUMMARY
    # ========================================================================

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              ✅ INSTALAÇÃO CONCLUÍDA COM SUCESSO            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    if [[ "$DRY_RUN" == false ]]; then
        log_success "NSP Plugin instalado em: $TARGET_ROOT"
        log_success "Plugin Lightroom: $LR_PLUGIN_TARGET"
        log_success "Atalho disponível: ~/Documents/NSP Plugin.lrplugin"
        echo ""
        log "Próximos passos:"
        log "  1. Abrir Adobe Lightroom Classic"
        log "  2. File → Plug-in Manager → Add"
        log "  3. Selecionar: $LR_PLUGIN_TARGET"
        log "  4. (Opcional) Executar Control Center: cd control-center && npm run dev"
        echo ""
        log "Log completo guardado em: $LOG_FILE"

        # Show Finder dialog on macOS
        if command -v osascript >/dev/null 2>&1; then
            /usr/bin/osascript <<APPLESCRIPT >/dev/null 2>&1 || true
try
  tell application "Finder"
    set pluginFolder to POSIX file "$LR_PLUGIN_TARGET"
    reveal pluginFolder
    activate
  end tell
  display dialog "✅ NSP Plugin instalado com sucesso!

Próximo passo: Ativa o plugin no Lightroom Plug-in Manager." buttons {"Fechar"} default button "Fechar" with icon note giving up after 30
on error errMsg number errNum
  -- Silently fail if Finder is not available
end try
APPLESCRIPT
        fi
    else
        log "[DRY-RUN] Instalação simulada concluída"
    fi
}

# ============================================================================
# ENTRY POINT
# ============================================================================

main "$@"
