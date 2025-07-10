#!/bin/bash

echo "🚀 Spouštím Flask server Jarvik..."

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/flask.pid"
FLASK_LOG="$DIR/flask.log"

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
  powershell.exe -Command "\$p = Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match 'main.py' }; if (\$p) { \$p | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force } }"
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
# Např. FLASK_DEBUG=false bash start_flask.sh vypne debug mód
python main.py > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > "$PID_FILE"
wait $FLASK_PID
STATUS=$?
if [ $STATUS -ne 0 ]; then
  FLASK_LOG_PATH=$(realpath "$FLASK_LOG")
  echo "❌ Flask se nespustil. Podrobnosti naleznete ve $FLASK_LOG_PATH"
  [ -f "$FLASK_LOG" ] && tail -n 5 "$FLASK_LOG"
fi
exit $STATUS

