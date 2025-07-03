#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit

GREEN='\033[1;32m'
NC='\033[0m'

# Remove accidentally tracked files
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  changes=false

  if git ls-files | grep -q '^venv/'; then
    git rm --cached -r venv >/dev/null 2>&1 || true
    changes=true
  fi

  memory_files=$(git ls-files 'memory/*.jsonl')
  if [ -n "$memory_files" ]; then
    echo "$memory_files" | xargs git rm --cached >/dev/null 2>&1 || true
    changes=true
  fi

  log_files=$(git ls-files '*.log')
  if [ -n "$log_files" ]; then
    echo "$log_files" | xargs git rm --cached >/dev/null 2>&1 || true
    changes=true
  fi

  for pattern in 'venv/' 'memory/*.jsonl' '*.log'; do
    if [ ! -f .gitignore ] || ! grep -qxF "$pattern" .gitignore; then
      echo "$pattern" >> .gitignore
      changes=true
    fi
  done

  if [ "$changes" = true ]; then
    git add .gitignore >/dev/null 2>&1 || true
    git commit -m "Automatická očista repozitáře (paměť, venv, logy)" >/dev/null 2>&1 || true
  fi
fi

# Download latest version if possible
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -n "$(git remote)" ]; then
    echo -e "${GREEN}🔄 Stahuji nejnovější verzi...${NC}"
    BEFORE_HASH="$(sha256sum "$0" | awk '{print $1}')"
    if git pull; then
      git submodule update --init --recursive
      AFTER_HASH="$(sha256sum "$0" | awk '{print $1}')"
      if [ "$BEFORE_HASH" != "$AFTER_HASH" ]; then
        echo -e "${GREEN}🔁 Skript byl aktualizován, znovu jej spouštím...${NC}"
        exec "$0" "$@"
      fi
    else
      echo -e "\033[1;33m⚠️  Nelze stáhnout nové soubory.\033[0m"
    fi
  else
    echo -e "${GREEN}⚠️  Git remote není nastaven, stahování vynecháno.${NC}"
  fi
  git submodule update --init --recursive
else
  echo -e "${GREEN}⚠️  Adresář není git repozitář, stahování vynecháno.${NC}"
fi

# Reinstall dependencies
bash uninstall_jarvik.sh
if ! bash install_jarvik.sh; then
  echo -e "\033[1;33m⚠️  Instalace závislostí selhala, pokračuji...\033[0m"
fi

# Re-add shell aliases
bash load.sh

# Start automatically
bash start_openchat.sh

echo -e "${GREEN}✅ Upgrade dokončen.${NC}"
