#!/bin/bash

echo "🔍 Kontrola systému JARVIK..."

MODEL_NAME=${MODEL_NAME:-"gemma:2b"}
FLASK_PORT=${FLASK_PORT:-8010}

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

ollama_running() {
  if command_exists pgrep; then
    pgrep -f "ollama serve" >/dev/null
  elif is_windows && command_exists tasklist; then
    tasklist | grep -iq "ollama.exe"
  else
    ps aux | grep -i "ollama serve" | grep -v grep >/dev/null
  fi
}

if ollama_running; then
  echo "✅ Ollama běží"
else
  echo "❌ Ollama neběží"
fi

if curl -s http://localhost:11434/api/tags | grep -q "$MODEL_NAME"; then
  echo "✅ Model $MODEL_NAME je k dispozici v Ollamě"
else
  echo "❌ Model $MODEL_NAME není nalezen (nebo Ollama neodpovídá)"
fi

if port_active "$FLASK_PORT"; then
  echo "✅ Flask (port $FLASK_PORT) běží"
else
  echo "❌ Flask (port $FLASK_PORT) neběží"
fi

if [ -f memory/public.jsonl ]; then
  echo "✅ Veřejná paměť existuje"
else
  echo "❌ Veřejná paměť chybí"
fi

if [ -d knowledge ]; then
  count=$(ls knowledge | wc -l)
  echo "✅ Znalostní soubory nalezeny: ($count)"
  for f in knowledge/*; do
    echo "   📄 $(basename "$f")"
  done
else
  echo "❌ Složka 'knowledge/' chybí"
fi
