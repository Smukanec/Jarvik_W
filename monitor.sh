#!/bin/bash

# Continuous status and log viewer for Jarvik

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

get_active_model() {
  if command -v jq >/dev/null 2>&1; then
    curl -s http://localhost:11434/api/tags | jq -r '.[0].name'
  else
    curl -s http://localhost:11434/api/tags |\
      grep -o '"name":"[^"]*"' | head -n 1 | sed -e 's/"name":"//' -e 's/"$//'
  fi
}

MODEL="$(get_active_model)"
MODEL_LOG="${MODEL//:/_}.log"

while true; do
  MODEL="$(get_active_model)"
  MODEL_LOG="${MODEL//:/_}.log"
  clear
  echo "===== Stav Jarvika ====="
  bash status.sh
  echo

  if [ -f flask.log ]; then
    echo "--- Poslední logy Flasku ---"
    tail -n 5 flask.log
    echo
  else
    echo "(Žádný flask.log)"
    echo
  fi

  if [ -f "$MODEL_LOG" ]; then
    echo "--- Poslední logy modelu ---"
    tail -n 5 "$MODEL_LOG"
  echo
  else
    echo "(Žádný $MODEL_LOG)"
    echo
  fi

  if [ -f ollama.log ]; then
    echo "--- Poslední logy Ollamy ---"
    tail -n 5 ollama.log
    echo
  else
    echo "(Žádný ollama.log)"
    echo
  fi

  sleep 2
done
