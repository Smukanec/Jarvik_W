#!/bin/bash
GREEN="\033[1;32m"
RED="\033[1;31m"
NC="\033[0m"

# Allow overriding the Flask port
FLASK_PORT=${FLASK_PORT:-8000}
STATUS_FILE="startup_status"

echo "starting" > "$STATUS_FILE"

cd "$(dirname "$0")" || exit

# Shared helpers
source utils.sh

# Model name can be overridden with the MODEL_NAME environment variable
MODEL_NAME=${MODEL_NAME:-"openchat"}
# Log file for the model output
MODEL_LOG="${MODEL_NAME//:/_}.log"
# Allow API mode when MODEL_NAME or MODEL_MODE indicate so
MODEL_MODE=${MODEL_MODE:-"local"}
if [ "$MODEL_NAME" = "api" ]; then
  MODEL_MODE="api"
fi
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
CMDS="python3 curl"
if [ "$MODEL_MODE" != "api" ]; then
  CMDS="ollama $CMDS"
fi
for cmd in $CMDS; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo -e "${RED}❌ Chybí příkaz $cmd. Nainstalujte jej a spusťte znovu.${NC}"
    exit 1
  fi
done

# Helper to detect Windows
is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

# Helper to open the web interface in the default browser
open_browser() {
  local url="http://localhost:$FLASK_PORT/"
  if is_windows; then
    command -v cmd.exe >/dev/null 2>&1 && cmd.exe /C start "" "$url"
  else
    case "$(uname -s)" in
      Darwin*) command -v open >/dev/null 2>&1 && open "$url" >/dev/null 2>&1 & ;;
      *) command -v xdg-open >/dev/null 2>&1 && xdg-open "$url" >/dev/null 2>&1 & ;;
    esac
  fi
}

# Potřebujeme také 'ss' nebo 'nc' (případně BusyBox) pro kontrolu běžících portů
SS_CMD=""
NC_CMD=""
if command -v ss >/dev/null 2>&1; then
  SS_CMD="ss"
elif command -v busybox >/dev/null 2>&1; then
  SS_CMD="busybox ss"
fi
if command -v nc >/dev/null 2>&1; then
  NC_CMD="nc"
elif command -v busybox >/dev/null 2>&1; then
  NC_CMD="busybox nc"
fi
if [ -z "$SS_CMD" ] && [ -z "$NC_CMD" ]; then
  echo -e "${RED}❌ Chybí příkazy 'ss' i 'nc'. Nainstalujte balíček iproute2, netcat nebo BusyBox pro Windows.${NC}"
  exit 1
fi

if [ "$MODEL_MODE" != "api" ]; then
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
    if ! process_running "ollama serve"; then
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
  if ! process_running "ollama run $MODEL_NAME"; then
    echo -e "${GREEN}🧠 Spouštím model $MODEL_NAME...${NC}"
    nohup ollama run "$MODEL_NAME" > "$MODEL_LOG" 2>&1 &
    sleep 2
    if ! process_running "ollama run $MODEL_NAME"; then
      echo -e "${RED}❌ Model $MODEL_NAME se nespustil, zkontrolujte $MODEL_LOG${NC}"
      exit 1
    fi
  fi
else
  echo -e "${GREEN}➡️  Používám externí API, model se nespouští${NC}"
fi

# Spustit Flask s několika pokusy o spuštění
echo -e "${GREEN}🌐 Spouštím Flask server...${NC}"
MAX_ATTEMPTS=5
ATTEMPT=1
PORT_OK=0
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
  if [ $ATTEMPT -gt 1 ]; then
    echo -e "${RED}❌ Flask se nespustil, pokus $((ATTEMPT-1)). Zkouším znovu...${NC}"
    echo "---- Retry $ATTEMPT ----" >> flask.log
  fi
  if [ $ATTEMPT -eq 1 ]; then
    nohup python3 main.py > flask.log 2>&1 &
  else
    nohup python3 main.py >> flask.log 2>&1 &
  fi
  FLASK_PID=$!
  sleep 2
  if [ -n "$SS_CMD" ] && $SS_CMD -tuln 2>/dev/null | grep -q ":$FLASK_PORT"; then
    PORT_OK=1
  elif [ -n "$NC_CMD" ] && $NC_CMD -z localhost $FLASK_PORT >/dev/null 2>&1; then
    PORT_OK=1
  fi
  [ "$PORT_OK" -eq 1 ] && break
  kill "$FLASK_PID" 2>/dev/null || true
  sleep 1
  ATTEMPT=$((ATTEMPT+1))
done
if [ "$PORT_OK" -ne 1 ]; then
  echo -e "${RED}❌ Flask se nespustil, zkontrolujte flask.log${NC}"
  echo "error" > "$STATUS_FILE"
  exit 1
fi

# Wait for Flask to respond
echo -e "${GREEN}⌛ Čekám na odpověď Flasku...${NC}"
HTTP_OK=0
for i in {1..30}; do
  if curl -sf "http://localhost:$FLASK_PORT/" >/dev/null 2>&1; then
    HTTP_OK=1
    break
  elif [ -n "$NC_CMD" ]; then
    echo -e "GET / HTTP/1.0\r\n" | $NC_CMD -w 1 localhost $FLASK_PORT >/dev/null 2>&1 && HTTP_OK=1 && break
  fi
  sleep 1
done

if [ "$HTTP_OK" -ne 1 ]; then
  echo -e "${RED}❌ Port $FLASK_PORT nereaguje${NC}"
  echo "error" > "$STATUS_FILE"
  exit 1
fi

echo -e "${GREEN}✅ Jarvik běží na http://localhost:$FLASK_PORT${NC}"
echo "running" > "$STATUS_FILE"
if [ -z "$NO_BROWSER" ]; then
  open_browser
fi
