#!/bin/sh
# Runs inside the container on every start:
#   1. bring the database schema up to date (safe to repeat: does nothing if already current)
#   2. start the web server
set -e

alembic upgrade head

# --proxy-headers: trust X-Forwarded-* from Azure's / Nginx's reverse proxy, so the app
# knows the original request used https.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
     --proxy-headers --forwarded-allow-ips='*'
