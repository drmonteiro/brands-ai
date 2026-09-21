#!/bin/bash
set -euo pipefail
cd /home/site/wwwroot

# Use CI-built virtualenv shipped with the deployment artifact
if [ -f "antenv/bin/activate" ]; then
  echo "[startup] Activating antenv virtualenv"
  source antenv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  echo "[startup] Activating venv virtualenv"
  source venv/bin/activate
else
  echo "[startup] WARNING: no virtualenv found, relying on system Python"
fi

echo "[startup] Python: $(which python)"
echo "[startup] Gunicorn: $(which gunicorn || echo 'NOT FOUND')"

exec gunicorn \
  -w 1 \
  -k uvicorn.workers.UvicornWorker \
  main:app \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
