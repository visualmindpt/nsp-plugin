#!/bin/bash
# -*- coding: utf-8 -*-
# NSP Plugin - Script de Instalação Automatizada (macOS/Linux)
# Versão: 2.0

set -e  # Exit on error

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║            NSP PLUGIN - INSTALADOR AUTOMATIZADO           ║"
echo "║                        Versão 2.0                          ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detectar diretório do script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}📂 Diretório do projeto: ${PROJECT_ROOT}${NC}\n"

# 1. VERIFICAR PRÉ-REQUISITOS
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PASSO 1/6: Verificar Pré-requisitos${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

# Python
echo -n "Verificando Python 3.8+... "
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 não encontrado!${NC}"
    echo "Instale Python 3.8+ de: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"

# Git (opcional)
echo -n "Verificando Git... "
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | awk '{print $3}')
    echo -e "${GREEN}✓${NC} Git $GIT_VERSION"
else
    echo -e "${YELLOW}⚠${NC}  Git não encontrado (opcional)"
fi

# 2. CRIAR AMBIENTE VIRTUAL
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PASSO 2/6: Criar Ambiente Virtual${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

cd "$PROJECT_ROOT"

if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠  Ambiente virtual já existe. Remover? (s/N)${NC}"
    read -r response
    if [[ "$response" =~ ^([sS]|[sS][iI][mM])$ ]]; then
        echo "Removendo venv antigo..."
        rm -rf venv
    else
        echo "Mantendo venv existente."
    fi
fi

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Ambiente virtual criado"
else
    echo -e "${GREEN}✓${NC} Usando ambiente virtual existente"
fi

# Ativar venv
source venv/bin/activate

# 3. INSTALAR DEPENDÊNCIAS
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PASSO 3/6: Instalar Dependências${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

echo "Atualizando pip..."
pip install --upgrade pip setuptools wheel

echo -e "\nInstalando dependências do projeto..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Dependências instaladas"
else
    echo -e "${RED}❌ requirements.txt não encontrado!${NC}"
    exit 1
fi

# 4. CRIAR ESTRUTURA DE DIRETÓRIOS
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PASSO 4/6: Criar Estrutura de Diretórios${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

mkdir -p data/{sessions,feedback}
mkdir -p models/backup_v1
mkdir -p logs
mkdir -p presets
mkdir -p datasets

echo -e "${GREEN}✓${NC} Estrutura de diretórios criada"

# 5. VERIFICAR MODELOS
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PASSO 5/6: Verificar Modelos ML${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

REQUIRED_MODELS=(
    "models/best_preset_classifier_v2.pth"
    "models/best_refinement_model_v2.pth"
)

MISSING_MODELS=()
for model in "${REQUIRED_MODELS[@]}"; do
    if [ -f "$model" ]; then
        SIZE=$(ls -lh "$model" | awk '{print $5}')
        echo -e "${GREEN}✓${NC} $model ($SIZE)"
    else
        echo -e "${RED}❌${NC} $model - FALTANDO"
        MISSING_MODELS+=("$model")
    fi
done

if [ ${#MISSING_MODELS[@]} -gt 0 ]; then
    echo -e "\n${YELLOW}⚠  Modelos em falta. Precisa de treinar primeiro:${NC}"
    echo "   python train/train_models_v2.py"
fi

# 6. INSTALAR PLUGIN NO LIGHTROOM
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PASSO 6/6: Instalar Plugin no Lightroom${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"

PLUGIN_DIR="$PROJECT_ROOT/NSP-Plugin.lrplugin"

if [ ! -d "$PLUGIN_DIR" ]; then
    echo -e "${RED}❌ Diretório do plugin não encontrado: $PLUGIN_DIR${NC}"
    exit 1
fi

echo "Plugin localizado: $PLUGIN_DIR"
echo ""
echo -e "${YELLOW}Para instalar no Lightroom Classic:${NC}"
echo "1. Abrir Lightroom Classic"
echo "2. File > Plug-in Manager..."
echo "3. Clicar 'Add'"
echo "4. Navegar para: $PLUGIN_DIR"
echo "5. Selecionar a pasta 'NSP-Plugin.lrplugin'"
echo ""
echo -e "${YELLOW}Ou copiar manualmente para:${NC}"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    LR_PLUGINS_DIR="$HOME/Library/Application Support/Adobe/Lightroom/Modules"
    echo "   $LR_PLUGINS_DIR"

    echo -e "\n${BLUE}Copiar automaticamente? (s/N)${NC}"
    read -r response
    if [[ "$response" =~ ^([sS]|[sS][iI][mM])$ ]]; then
        mkdir -p "$LR_PLUGINS_DIR"
        cp -R "$PLUGIN_DIR" "$LR_PLUGINS_DIR/"
        echo -e "${GREEN}✓${NC} Plugin copiado para Lightroom"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "   ~/.config/Adobe/Lightroom/Modules"
fi

# RESUMO FINAL
echo -e "\n${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║               ✓ INSTALAÇÃO CONCLUÍDA COM SUCESSO!         ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}📋 Próximos Passos:${NC}\n"

echo "1. Iniciar o servidor:"
echo "   ${GREEN}./start_server.sh${NC}"
echo ""

echo "2. (Opcional) Treinar modelos se ainda não tiver:"
echo "   ${GREEN}source venv/bin/activate${NC}"
echo "   ${GREEN}python train/train_models_v2.py${NC}"
echo ""

echo "3. Instalar plugin no Lightroom (ver instruções acima)"
echo ""

echo "4. (Opcional) Ativar autenticação API:"
echo "   Editar ${GREEN}config.json${NC} e definir:"
echo "   ${YELLOW}\"api_auth_enabled\": true${NC}"
echo ""

echo "5. (Opcional) Gerar API key:"
echo "   ${GREEN}python manage_api_keys.py generate \"Nome\" --level standard${NC}"
echo ""

echo -e "${BLUE}📚 Documentação:${NC}"
echo "   - RESUMO_OTIMIZACOES.md"
echo "   - MELHORIAS_COMPLETAS_FINAL.md"
echo "   - GUIA_TESTES_RAPIDO.md"
echo ""

echo -e "${BLUE}🎉 Pronto para usar!${NC}\n"
