#!/bin/bash

echo "🚀 Spouštím Flask server Jarvik..."

# Kill any previous Flask instance
echo "🛑 Zastavuji staré instance Flasku..."
is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

if is_windows && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { \$_.Path -like '*main.py' } | Stop-Process -Force"
else
  pkill -f 'python.*main.py' 2>/dev/null || true
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
python main.py
