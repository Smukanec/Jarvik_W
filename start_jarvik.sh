#!/bin/bash
GREEN="\033[1;32m"
RED="\033[1;31m"
NC="\033[0m"

# Allow overriding the Flask port
FLASK_PORT=${FLASK_PORT:-8010}

cd "$(dirname "$0")" || exit

# Model name can be overridden with the MODEL_NAME environment variable
MODEL_NAME=${MODEL_NAME:-"gemma:2b"}
# Log file for the model output
MODEL_LOG="${MODEL_NAME}.log"
# Optional LOCAL_MODEL_FILE can specify a .gguf file to register as this model

# Aktivovat venv, pokud ještě není aktivní
if [ -z "$VIRTUAL_ENV" ]; then
  if [ -f venv/bin/activate ]; then
    source venv/bin/activate
    echo -e "${GREEN}✅ Aktivováno virtuální prostředí${NC}"
  elif [ -f venv/Scripts/activate ]; then
    source venv/Scripts/activate
    echo -e "${GREEN}✅ Aktivováno virtuální prostředí${NC}"
  else
    echo -e "${RED}❌ Chybí virtuální prostředí venv/. Spusťte install_jarvik.sh.${NC}"
    exit 1
  fi
fi

# Zkontrolovat dostupnost příkazů
for cmd in ollama python3 curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo -e "${RED}❌ Chybí příkaz $cmd. Nainstalujte jej a spusťte znovu.${NC}"
    exit 1
  fi
done

# Potřebujeme také 'ss' nebo 'nc' pro kontrolu běžících portů
if ! command -v ss >/dev/null 2>&1 && ! command -v nc >/dev/null 2>&1; then
  echo -e "${RED}❌ Chybí příkazy 'ss' i 'nc'. Nainstalujte balíček iproute2 nebo netcat.${NC}"
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

# Spustit Ollama na lokální stanici, pokud neběží
if [ "$REMOTE_OLLAMA" -eq 0 ]; then
  if ! pgrep -f "ollama serve" > /dev/null; then
    echo -e "${GREEN}🚀 Spouštím Ollama...${NC}"
    nohup ollama serve > ollama.log 2>&1 &
  fi
  # Počkej na zpřístupnění API
  for i in {1..10}; do
    if curl -s ${OLLAMA_URL}/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! curl -s ${OLLAMA_URL}/api/tags >/dev/null 2>&1; then
    echo -e "${RED}❌ Ollama se nespustila, zkontrolujte ollama.log${NC}"
    exit 1
  fi
else
  # Jen zkontroluj, že vzdálená Ollama odpovídá
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
fi

# Ověřit dostupnost modelu $MODEL_NAME a případně jej stáhnout
if ! ollama list 2>/dev/null | grep -q "^${MODEL_NAME}"; then
  CREATED=""
  if [ -n "$LOCAL_MODEL_FILE" ] && [ -f "$LOCAL_MODEL_FILE" ] && [[ "$LOCAL_MODEL_FILE" == *.gguf ]]; then
    TMP_MODFILE=$(mktemp)
    echo "FROM $LOCAL_MODEL_FILE" > "$TMP_MODFILE"
    if ollama create "$MODEL_NAME" -f "$TMP_MODFILE" >> ollama.log 2>&1; then
      CREATED=1
    fi
    rm -f "$TMP_MODFILE"
  fi
  if [ -z "$CREATED" ]; then
    echo -e "${GREEN}⬇️  Stahuji model $MODEL_NAME...${NC}"
    if ! ollama pull "$MODEL_NAME" >> ollama.log 2>&1; then
      echo -e "${RED}❌ Stažení modelu selhalo, zkontrolujte připojení${NC}"
      exit 1
    fi
  fi
fi

# Spustit $MODEL_NAME, pokud neběží
if ! pgrep -f -x "ollama run $MODEL_NAME" > /dev/null; then
  echo -e "${GREEN}🧠 Spouštím model $MODEL_NAME...${NC}"
  nohup ollama run "$MODEL_NAME" > "$MODEL_LOG" 2>&1 &
  sleep 2
  if ! pgrep -f -x "ollama run $MODEL_NAME" > /dev/null; then
    echo -e "${RED}❌ Model $MODEL_NAME se nespustil, zkontrolujte $MODEL_LOG${NC}"
    exit 1
  fi
fi

# Spustit Flask
echo -e "${GREEN}🌐 Spouštím Flask server...${NC}"
nohup python3 main.py > flask.log 2>&1 &
sleep 2
if ! (ss -tuln 2>/dev/null | grep -q ":$FLASK_PORT" || nc -z localhost $FLASK_PORT >/dev/null 2>&1); then
  echo -e "${RED}❌ Flask se nespustil, zkontrolujte flask.log${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Jarvik běží na http://localhost:$FLASK_PORT${NC}"
