#!/bin/bash

echo "🚀 Spouštím Flask server Jarvik..."

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
