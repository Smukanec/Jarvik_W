#!/bin/bash
# Stop Ollama, running models and Flask
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

# Terminate Ollama server
pkill -f "ollama serve" 2>/dev/null && echo "Stopped ollama serve" || true
# Terminate any running models
pkill -f "ollama run" 2>/dev/null && echo "Stopped running models" || true
# Terminate Flask application
pkill -f "python3 main.py" 2>/dev/null && echo "Stopped Flask" || true
