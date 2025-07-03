#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit
set -e

# Update DevLab submodule if possible
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "🔄 Stahuji DevLab submodul..."
  git submodule update --init --recursive
fi

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

# Create personal memory logs for users defined in users.json
if [ -f users.json ]; then
  echo "📄 Vytvářím osobní paměti pro uživatele..."
  python - <<'PY'
import json, os
with open('users.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
for u in data:
    nick = u.get('nick')
    if not nick:
        continue
    path = os.path.join('memory', nick)
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, 'log.jsonl'), 'a', encoding='utf-8').close()
PY
fi

# Vytvoření virtuálního prostředí (pokud není)
if [ ! -d venv ]; then
  echo "🧪 Vytvářím virtuální prostředí venv/..."
  python -m venv venv
fi

# Aktivace venv a instalace požadavků
echo "📦 Instalace Python závislostí..."
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
  source venv/Scripts/activate
else
  echo "❌ Chybí virtuální prostředí venv/. Spusťte skript znovu." >&2
  exit 1
fi

if ! pip install -r requirements.txt; then
  echo -e "\033[1;33m⚠️  Instalace Python závislostí selhala. Zkontrolujte připojení k internetu.\033[0m"
  exit 1
fi

echo -e "✅ Instalace dokončena."
