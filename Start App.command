#!/bin/zsh
cd -- "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ ! -x .venv/bin/python ]]; then
  print "Missing .venv. Follow the Python setup in README.md first."
  read "?Press Enter to close."
  exit 1
fi
.venv/bin/python scripts/start_app.py
read "?Press Enter to close."
