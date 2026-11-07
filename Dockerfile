FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# Copy requirements first: Docker caches this layer, so rebuilds are fast
# unless requirements.txt itself changed.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as a normal user, not root. Uploaded files go to /data/media, which you mount as a volume.
RUN useradd --create-home appuser \
    && mkdir -p /data/media \
    && chown -R appuser /code /data \
    && chmod +x /code/docker-entrypoint.sh
USER appuser
ENV MEDIA_DIR=/data/media \
    PORT=8000

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"

CMD ["/code/docker-entrypoint.sh"]
