#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

# Update submodules if possible
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git submodule update --init --recursive
fi

bash "$DIR/start_jarvik.sh" "$@"

