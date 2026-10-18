#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Setting up the private local app (first run only)…"
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
exec .venv/bin/python app.py
