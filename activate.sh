#!/bin/bash

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

if [ -f venv/bin/activate ]; then
  source venv/bin/activate
elif [ -f venv/Scripts/activate ]; then
  source venv/Scripts/activate
else
  echo "❌ Chybí virtuální prostředí venv/. Spusťte install_jarvik.sh."
  exit 1
fi

echo "✅ Aktivováno virtuální prostředí JARVIK (venv)"
