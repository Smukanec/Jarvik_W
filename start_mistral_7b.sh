#!/bin/bash

# Wrapper to start Jarvik with the Mistral 7B quantized model
DIR="$(cd "$(dirname "$0")" && pwd)"
# Stop any running instance before starting a new one
bash "$DIR/switch_model.sh" "mistral:7b-Q4_K_M"

