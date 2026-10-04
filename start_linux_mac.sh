#!/usr/bin/env bash
# Roohvi launcher: creates .venv, installs dependencies once, then starts the app.
set -e
cd "$(dirname "$0")"

PY=""
for c in python3.12 python3.13 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11-3.13 install karein, phir dobara chalayein."; exit 1
fi

[ -d .venv ] || "$PY" -m venv .venv

if [ ! -f .venv/.deps_installed ]; then
  echo "Installing dependencies (pehli dafa kuch minute lagenge)..."
  .venv/bin/python setup.py
  touch .venv/.deps_installed
fi

# optional: 3D avatar support (also upgrades older installs); never blocks start-up
if ! .venv/bin/python -c "import PyQt6.QtWebEngineWidgets" >/dev/null 2>&1; then
  echo "Installing 3D avatar support (one time)..."
  .venv/bin/python -m pip install "PyQt6-WebEngine>=6.6,<7" || true
fi

exec .venv/bin/python main.py
