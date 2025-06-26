#!/bin/bash

# Continuous status and log viewer for Jarvik

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

# Default model name if not provided
MODEL_NAME=${MODEL_NAME:-"gemma:2b"}
MODEL_LOG="${MODEL_NAME}.log"

while true; do
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
