#!/bin/bash
echo "🧹 Odstraňuji logy z verzování..."

git rm --cached flask.log 2>/dev/null
git rm --cached ollama.log 2>/dev/null
git rm --cached "gemma2b.log" 2>/dev/null

echo "*.log" >> .gitignore

git add .gitignore
git commit -m "Auto: odstranění logů a aktualizace .gitignore"


