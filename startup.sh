#!/bin/sh
# Startup command for Azure App Service (Linux, built-in Python runtime, code deployment).
# Azure's Python runtime sends web traffic to port 8000 by default.
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
