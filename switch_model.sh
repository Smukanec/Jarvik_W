#!/bin/bash
# Helper to switch models by restarting all components

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

NEW_MODEL="$1"
if [ -z "$NEW_MODEL" ]; then
  echo "Usage: $0 <model_name>" >&2
  exit 1
fi

echo "🔄 Switching to model $NEW_MODEL..."

# Stop running services across platforms
FLASK_PORT=${FLASK_PORT:-8000}

is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

if is_windows && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -Command '$p=Get-Process -Name ollama -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; exit 0 } else { exit 1 }'
  powershell.exe -Command '$p=Get-Process -Name ollama -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; exit 0 } else { exit 1 }'
  powershell.exe -Command "\$p = Get-CimInstance Win32_Process | Where-Object {\$_.CommandLine -match 'main.py' }; if (\$p) { \$p | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force } }"
else
  pkill -f "python3 main.py" 2>/dev/null
  pkill -f "ollama run" 2>/dev/null
  pkill -f "ollama serve" 2>/dev/null
fi
sleep 2

# Wait for Flask port to become free before restarting
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

echo "⌛ Waiting for port $FLASK_PORT to be free..."
while true; do
  PORT_IN_USE=0
  if [ -n "$SS_CMD" ] && $SS_CMD -tuln 2>/dev/null | grep -q ":$FLASK_PORT"; then
    PORT_IN_USE=1
  elif [ -n "$NC_CMD" ] && $NC_CMD -z localhost $FLASK_PORT >/dev/null 2>&1; then
    PORT_IN_USE=1
  fi
  [ "$PORT_IN_USE" -eq 0 ] && break
  sleep 1
done

if [ "$NEW_MODEL" = "api" ]; then
  MODEL_MODE="api"
else
  MODEL_MODE="local"
fi
MODEL_NAME="$NEW_MODEL" MODEL_MODE="$MODEL_MODE" bash "$DIR/start_jarvik.sh"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  echo "❌ Jarvik se nepodařilo spustit"
  exit "$STATUS"
fi

# Wait for Flask port to become ready
TIMEOUT=30
PORT_READY=0
echo "⌛ Waiting for Flask on port $FLASK_PORT..."
for ((i=0;i<TIMEOUT;i++)); do
  if [ -n "$SS_CMD" ] && $SS_CMD -tln 2>/dev/null | grep -q ":$FLASK_PORT"; then
    PORT_READY=1
  elif [ -n "$NC_CMD" ] && $NC_CMD -z localhost $FLASK_PORT >/dev/null 2>&1; then
    PORT_READY=1
  elif command -v curl >/dev/null 2>&1 && curl -sf "http://localhost:$FLASK_PORT/" >/dev/null 2>&1; then
    PORT_READY=1
  fi
  [ "$PORT_READY" -eq 1 ] && break
  sleep 1
done

if [ "$PORT_READY" -ne 1 ]; then
  echo "❌ Flask port $FLASK_PORT did not respond"
  exit 1
fi
echo "✅ Flask responded"
