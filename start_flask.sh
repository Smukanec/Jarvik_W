#!/bin/bash

echo "🚀 Spouštím Flask server Jarvik..."

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/flask.pid"

# Kill any previous Flask instance
echo "🛑 Zastavuji staré instance Flasku..."

# Terminate Flask from stored PID if available
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if ps -p "$OLD_PID" > /dev/null 2>&1; then
    kill "$OLD_PID" && echo "Killed old Flask with PID $OLD_PID" || true
  fi
  rm -f "$PID_FILE"
fi

is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

if is_windows && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { \$_.Path -like '*main.py' } | Stop-Process -Force"
else
  pkill -f "python.*${DIR}/main.py" 2>/dev/null || true
fi

# Kontrola existence a aktivace venv
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
  source venv/Scripts/activate
else
  echo "❌ Chybí virtuální prostředí venv/. Spusťte install_jarvik.sh."
  exit 1
fi

# Spuštění Flasku
python main.py &
echo $! > "$PID_FILE"
wait $!

