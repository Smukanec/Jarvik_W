#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$DIR/switch_model.sh" "deepseek-coder:6.7b" "$@"
