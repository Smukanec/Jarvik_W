# Shared helper functions

# Cross platform check if a process is running
process_running() {
  local pattern="$1"
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f "$pattern" >/dev/null 2>&1
  elif is_windows && command -v tasklist >/dev/null 2>&1; then
    tasklist | grep -i "$pattern" >/dev/null 2>&1
  else
    ps aux | grep "$pattern" | grep -v grep >/dev/null 2>&1
  fi
}

