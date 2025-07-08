#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit
set -e

if [ ! -d knowledge ]; then
  echo "❌ Složka knowledge neexistuje." >&2
  exit 1
fi

cat <<'MSG'
⚠️  Tento skript smaže vše v knowledge/ kromě souboru _index.json.
   Provádí logiku podobnou příkazu:
       rm -rf knowledge/*
   Stiskněte Ctrl+C pro zrušení, nebo počkejte...
MSG
sleep 3

find knowledge -mindepth 1 ! -name _index.json -exec rm -rf {} +

echo "✅ Knowledge vyčištěno."

