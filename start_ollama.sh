#!/bin/bash
GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m'

cd "$(dirname "$0")" || exit

# Ensure ollama is available
if ! command -v ollama >/dev/null 2>&1; then
  echo -e "${RED}❌ Chybí program 'ollama'. Nainstalujte jej a spusťte znovu.${NC}"
  exit 1
fi

# Start Ollama if not running
if ! pgrep -f "ollama serve" > /dev/null; then
  echo -e "${GREEN}🚀 Spouštím Ollama...${NC}"
  nohup ollama serve > ollama.log 2>&1 &
  for i in {1..10}; do
    if curl -s ${OLLAMA_URL:-http://localhost:11434}/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! curl -s ${OLLAMA_URL:-http://localhost:11434}/api/tags >/dev/null 2>&1; then
    echo -e "${RED}❌ Ollama se nespustila, zkontrolujte ollama.log${NC}"
    exit 1
  fi
else
  echo -e "${GREEN}✅ Ollama již běží${NC}"
fi
