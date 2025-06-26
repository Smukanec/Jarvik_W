#!/bin/bash

echo "🔍 Kontrola systému JARVIK..."

# Kontrola běhu Ollamy pomocí tasklist
if tasklist.exe | grep -iq "ollama.exe"; then
  echo "✅ Ollama běží"
else
  echo "❌ Ollama neběží"
fi

# Kontrola dostupnosti modelu přes API
if curl -s http://localhost:11434/api/tags | grep -q "gemma:2b"; then
  echo "✅ Model gemma:2b je k dispozici v Ollamě"
else
  echo "❌ Model gemma:2b není nalezen (nebo Ollama neodpovídá)"
fi

# Kontrola portu 8010
if netstat -an | grep -q ":8010"; then
  echo "✅ Flask (port 8010) běží"
else
  echo "❌ Flask (port 8010) neběží"
fi

# Kontrola veřejné paměti
if [ -f memory/public.jsonl ]; then
  echo "✅ Veřejná paměť existuje"
else
  echo "❌ Veřejná paměť chybí"
fi

# Znalosti
if [ -d knowledge ]; then
  count=$(ls knowledge | wc -l)
  echo "✅ Znalostní soubory nalezeny: ($count)"
  for f in knowledge/*; do
    echo "   📄 $(basename "$f")"
  done
else
  echo "❌ Složka 'knowledge/' chybí"
fi
