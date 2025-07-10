#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit
set -e
# Default model name can be overridden via MODEL_NAME
MODEL_NAME=${MODEL_NAME:-"openchat"}

# Optional flag to also clean knowledge base
WITH_KNOWLEDGE=false
for arg in "$@"; do
  if [ "$arg" = "--with-knowledge" ]; then
    WITH_KNOWLEDGE=true
  fi
done

echo "🗑️ Odinstalace Jarvika..."

# Kill running processes on both Linux and Windows
is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
  esac
  [ "$OS" = "Windows_NT" ]
}

if is_windows && command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -Command '$p=Get-Process -Name ollama -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; exit 0 } else { exit 1 }' && echo "Zastaven ollama serve" || true
  powershell.exe -Command '$p=Get-Process -Name ollama -ErrorAction SilentlyContinue; if ($p) { $p | Stop-Process -Force; exit 0 } else { exit 1 }' && echo "Zastaveny modely" || true
  powershell.exe -Command "\$p = Get-CimInstance Win32_Process | Where-Object {\$_.CommandLine -match 'main.py' }; if (\$p) { \$p | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force } }" && echo "Zastaven Flask" || true
else
  pkill -f "ollama serve" 2>/dev/null && echo "Zastaven ollama serve" || true
  pkill -f "ollama run" 2>/dev/null && echo "Zastaveny modely" || true
  pkill -f "python3 main.py" 2>/dev/null && echo "Zastaven Flask" || true
fi

# Remove directories and logs
rm -rf venv memory
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
rm -f *.log

# If requested, also remove knowledge contents
if [ "$WITH_KNOWLEDGE" = true ]; then
  bash "$DIR/clean_knowledge.sh"
fi

# Remove aliases from ~/.bashrc
sed -i '/# 🚀 Alias příkazy pro JARVIK/,+7d' ~/.bashrc

echo "✅ Jarvik odstraněn."
