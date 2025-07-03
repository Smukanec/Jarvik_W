#!/bin/bash

FLASK_PORT=${FLASK_PORT:-8010}
MODEL_NAME=${MODEL_NAME:-"openchat"}
MODEL_LOG="${MODEL_NAME//:/_}.log"

GREEN="\033[1;32m"
RED="\033[1;31m"
NC="\033[0m"

echo -e "${GREEN}🔧 Watchdog spuštěn. Kontroluji služby každých 5 sekund.${NC}"

is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

port_active() {
  local port="$1"
  if command_exists ss; then
    ss -tuln | grep -q ":$port"
  elif command_exists lsof; then
    lsof -i ":$port" 2>/dev/null | grep -q LISTEN
  else
    netstat -an | grep -q ":$port"
  fi
}

check_ollama() {
  if command_exists pgrep; then
    pgrep -f "ollama serve" >/dev/null && return
  elif is_windows && command_exists tasklist; then
    tasklist | grep -iq "ollama.exe" && return
  else
    ps aux | grep -i "ollama serve" | grep -v grep >/dev/null && return
  fi

  echo -e "${RED}❌ Ollama neběží. Restartuji...${NC}"
  nohup ollama serve > ollama.log 2>&1 &
}

check_model() {
  if ! curl -s http://localhost:11434/api/tags | grep -q "$MODEL_NAME"; then
    echo -e "${RED}❌ Model $MODEL_NAME neběží. Restartuji...${NC}"
    nohup ollama run "$MODEL_NAME" > "$MODEL_LOG" 2>&1 &
  fi
}

check_flask() {
  if ! port_active "$FLASK_PORT"; then
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
