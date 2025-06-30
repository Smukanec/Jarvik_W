DIR="$(cd "$(dirname "$0")" && pwd)"

# Add Jarvik aliases only if they aren't already present
if ! grep -q "# 🚀 Alias příkazy pro JARVIK" ~/.bashrc; then
  cat >> ~/.bashrc <<EOF

# 🚀 Alias příkazy pro JARVIK
alias jarvik='bash $DIR/activate.sh'
alias jarvik-start='bash $DIR/start_gemma_2b.sh'
alias jarvik-start-7b='bash $DIR/start_mistral_7b.sh'
alias jarvik-start-q4='bash $DIR/start_jarvik_q4.sh'
alias jarvik-status='bash $DIR/status.sh'
alias jarvik-install='bash $DIR/install_jarvik.sh'
alias jarvik-flask='bash $DIR/start_flask.sh'
alias jarvik-model='bash $DIR/start_model.sh'
alias jarvik-ollama='bash $DIR/start_ollama.sh'
alias jarvik-start-phi3='bash $DIR/start_phi3_mini.sh'
alias jarvik-start-nh2='bash $DIR/start_nous_hermes2.sh'
alias jarvik-start-llama3='bash $DIR/start_llama3_8b.sh'
alias jarvik-start-command-r='bash $DIR/start_command_r.sh'
alias jarvik-start-zephyr='bash $DIR/start_zephyr.sh'
alias jarvik-start-coder='bash $DIR/start_deepseek_coder.sh'
alias jarvik-start-gemma='bash $DIR/start_gemma_2b.sh'

EOF
fi

# Načtení změn
source ~/.bashrc
