#!/usr/bin/env bash
# alertledger installer: python3 check → setup wizard → first sync → service. Idempotent; rerun after `git pull`.
set -euo pipefail
cd "$(dirname "$0")"
PY=$(command -v python3 || true)
[ -n "$PY" ] || { echo "python3 not found. Debian/Raspberry Pi OS: sudo apt install python3 — macOS: xcode-select --install"; exit 1; }
"$PY" - <<'PYCHK' || { echo "python3 >= 3.11 required (found $($PY --version))"; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
PYCHK
if [ ! -f "${ALERTLEDGER_HOME:-$HOME/.alertledger}/config.json" ]; then
  "$PY" alertledger.py setup
  echo; echo "first pull of your whole mailbox (a few minutes)…"; "$PY" alertledger.py sync --full
fi
echo
if [ "$(uname)" = "Darwin" ]; then
  "$PY" alertledger.py install
else
  echo "registering the systemd service (needs sudo once)…"
  sudo -E "$PY" alertledger.py install
fi
