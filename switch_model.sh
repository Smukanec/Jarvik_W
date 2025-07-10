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

if [ "$NEW_MODEL" = "api" ]; then
  MODEL_MODE="api"
else
  MODEL_MODE="local"
fi
MODEL_NAME="$NEW_MODEL" MODEL_MODE="$MODEL_MODE" bash "$DIR/start_jarvik.sh"
