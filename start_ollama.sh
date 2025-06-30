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

# Rozpoznat vzdálenou Ollamu
OLLAMA_URL=${OLLAMA_URL:-http://localhost:11434}
if [[ $OLLAMA_URL == http://localhost* ]] || [[ $OLLAMA_URL == http://127.* ]] || [[ $OLLAMA_URL == https://localhost* ]]; then
  REMOTE_OLLAMA=0
else
  REMOTE_OLLAMA=1
  export OLLAMA_HOST=${OLLAMA_URL#*://}
fi

# Start Ollama pouze lokálně
if [ "$REMOTE_OLLAMA" -eq 0 ]; then
  if ! pgrep -f "ollama serve" > /dev/null; then
    echo -e "${GREEN}🚀 Spouštím Ollama...${NC}"
    nohup ollama serve > ollama.log 2>&1 &
  else
    echo -e "${GREEN}✅ Ollama již běží${NC}"
  fi
fi

for i in {1..10}; do
  if curl -s ${OLLAMA_URL}/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -s ${OLLAMA_URL}/api/tags >/dev/null 2>&1; then
  echo -e "${RED}❌ Nelze se připojit k ${OLLAMA_URL}${NC}"
  exit 1
fi
