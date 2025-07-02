#!/bin/bash
echo "🧹 Odstraňuji logy z verzování..."

log_files=$(git ls-files '*.log')
if [ -n "$log_files" ]; then
  echo "$log_files" | xargs git rm --cached >/dev/null 2>&1
fi

if [ ! -f .gitignore ] || ! grep -qxF "*.log" .gitignore; then
  echo "*.log" >> .gitignore
fi

git add .gitignore
git commit -m "Auto: odstranění logů a aktualizace .gitignore"


