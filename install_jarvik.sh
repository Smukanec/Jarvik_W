#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit
set -e

# Optional cleanup
if [ "$1" == "--clean" ]; then
  bash "$DIR/uninstall_jarvik.sh"
fi

echo "🔧 Instalace závislostí pro Jarvika..."

# Vytvoření složek
mkdir -p memory
mkdir -p knowledge

# Vytvoření prázdné veřejné paměti (pokud není)
if [ ! -f memory/public.jsonl ]; then
  echo "📄 Vytvářím veřejnou paměť..."
  touch memory/public.jsonl
fi

# Vytvoření virtuálního prostředí (pokud není)
if [ ! -d venv ]; then
  echo "🧪 Vytvářím virtuální prostředí venv/..."
  python -m venv venv
fi

# Aktivace venv a instalace požadavků
echo "📦 Instalace Python závislostí..."
source venv/Scripts/activate

if ! pip install -r requirements.txt; then
  echo -e "\033[1;33m⚠️  Instalace Python závislostí selhala. Zkontrolujte připojení k internetu.\033[0m"
  exit 1
fi

echo -e "✅ Instalace dokončena."
