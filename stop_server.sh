#!/bin/bash
# Script para parar o servidor NSP Plugin
# Uso: ./stop_server.sh

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 A parar servidor NSP Plugin...${NC}"

# Procurar processos do servidor
PIDS=$(pgrep -f run_server_gpu.py)

if [ -z "$PIDS" ]; then
    echo -e "${RED}❌ Nenhum servidor a correr.${NC}"
    exit 0
fi

# Parar processos
pkill -f run_server_gpu.py

# Aguardar
sleep 2

# Verificar se parou
REMAINING=$(pgrep -f run_server_gpu.py)
if [ -z "$REMAINING" ]; then
    echo -e "${GREEN}✅ Servidor parado com sucesso!${NC}"
else
    echo -e "${RED}⚠️  Alguns processos ainda estão a correr. A forçar...${NC}"
    pkill -9 -f run_server_gpu.py
    sleep 1
    echo -e "${GREEN}✅ Servidor forçado a parar.${NC}"
fi
