#!/bin/bash
# Azure App Service startup — bind to $PORT (injected by platform)
exec gunicorn \
  -w 1 \
  -k uvicorn.workers.UvicornWorker \
  main:app \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
