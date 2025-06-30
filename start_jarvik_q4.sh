#!/bin/bash

# Wrapper to start Jarvik with the Jarvik Q4 quantized model
DIR="$(cd "$(dirname "$0")" && pwd)"
# Stop any running instance before starting a new one
bash "$DIR/switch_model.sh" "jarvik-q4"

