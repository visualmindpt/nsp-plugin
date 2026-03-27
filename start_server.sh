#!/bin/bash
# Script de arranque do servidor NSP Plugin
# Uso: ./start_server.sh

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  NSP Plugin - Iniciar Servidor${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Ir para diretório do projeto (detecta automaticamente onde está o script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Verificar se venv existe
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Ambiente virtual não encontrado!${NC}"
    echo "Execute: python3 -m venv venv"
    exit 1
fi

# Ativar ambiente virtual
echo -e "${BLUE}🔧 A ativar ambiente virtual...${NC}"
source venv/bin/activate

# Verificar se uvicorn está instalado
if ! python -c "import uvicorn" 2>/dev/null; then
    echo -e "${RED}❌ uvicorn não está instalado!${NC}"
    echo "Execute: pip install -r requirements.txt"
    exit 1
fi

# Parar servidor existente
echo -e "${BLUE}🛑 A parar servidor existente (se houver)...${NC}"
pkill -f "services/server.py" 2>/dev/null
sleep 1

# Iniciar servidor
echo -e "${GREEN}🚀 A iniciar servidor...${NC}"
echo ""
python services/server.py

# Nota: Se quiser iniciar em background, substitua a linha acima por:
# nohup python services/server.py > server.log 2>&1 &
# echo -e "${GREEN}✅ Servidor iniciado em background!${NC}"
# echo -e "${BLUE}📄 Logs: tail -f server.log${NC}"
# echo -e "${BLUE}🌐 URL: http://127.0.0.1:5678${NC}"
