#!/bin/bash

echo "🚀 Spouštím Flask server Jarvik..."

# Kontrola existence správné aktivace
if [ ! -f "venv/Scripts/activate" ]; then
  echo "❌ Chybí virtuální prostředí venv/. Spusťte install_jarvik.sh."
  exit 1
fi

# Aktivace venv
source venv/Scripts/activate

# Spuštění Flasku
python main.py &
