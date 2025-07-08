#!/bin/bash
# Stop Ollama, running models and Flask
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

if is_windows && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -Command '$p=Get-Process -Name ollama -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; exit 0 } else { exit 1 }' && echo "Stopped ollama serve" || true
  powershell.exe -Command '$p=Get-Process -Name ollama -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; exit 0 } else { exit 1 }' && echo "Stopped running models" || true
  powershell.exe -Command "$p = Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match 'main.py' }; if ($p) { \$p | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }; exit 0 } else { exit 1 }" && echo "Stopped Flask" || true
else
  pkill -f "ollama serve" 2>/dev/null && echo "Stopped ollama serve" || true
  pkill -f "ollama run" 2>/dev/null && echo "Stopped running models" || true
  pkill -f "python.*main.py" 2>/dev/null && echo "Stopped Flask" || true
fi
