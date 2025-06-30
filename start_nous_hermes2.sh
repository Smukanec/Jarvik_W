#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$DIR/switch_model.sh" "nous-hermes2:7b" "$@"
