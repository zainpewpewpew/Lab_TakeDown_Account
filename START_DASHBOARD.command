#!/bin/zsh
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 tidak ditemukan. Install Python 3 terlebih dahulu.'
  read '?Tekan Enter untuk keluar...'
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
if ! python -c 'import playwright' >/dev/null 2>&1; then
  pip install -r requirements.txt
  python -m playwright install chromium
fi
python dashboard.py