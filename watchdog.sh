#!/bin/bash

FLASK_PORT=8010
GREEN="\033[1;32m"
RED="\033[1;31m"
NC="\033[0m"

echo -e "${GREEN}🔧 Watchdog spuštěn. Kontroluji služby každých 5 sekund.${NC}"

check_ollama() {
  if ! tasklist | grep -iq "ollama.exe"; then
    echo -e "${RED}❌ Ollama neběží. Restartuji...${NC}"
    nohup ollama serve > ollama.log 2>&1 &
  fi
}

check_model() {
  if ! curl -s http://localhost:11434/api/tags | grep -q "gemma:2b"; then
    echo -e "${RED}❌ Model gemma:2b neběží. Restartuji...${NC}"
    nohup ollama run gemma:2b > gemma.log 2>&1 &
  fi
}

check_flask() {
  if ! netstat -an | grep -q ":$FLASK_PORT"; then
    echo -e "${RED}❌ Flask neběží. Restartuji...${NC}"
    if [ -f venv/bin/activate ]; then
      source venv/bin/activate
    elif [ -f venv/Scripts/activate ]; then
      source venv/Scripts/activate
    else
      echo -e "${RED}❌ Chybí virtuální prostředí venv/.${NC}"
      return
    fi
    nohup python main.py > flask.log 2>&1 &
  fi
}

while true; do
  check_ollama
  check_model
  check_flask
  sleep 5
done
