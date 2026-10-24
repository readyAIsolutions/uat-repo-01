# MARLIN Rhino MVP — backend + UI (single service).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY backend/requirements-mvp.txt /app/backend/requirements-mvp.txt
RUN pip install --no-cache-dir -r /app/backend/requirements-mvp.txt rhino3dm

COPY backend /app/backend

ENV MARLIN_ENVIRONMENT=production \
    MARLIN_LOG_LEVEL=INFO \
    MARLIN_STORAGE_DIR=/data/storage
RUN mkdir -p /data/storage
VOLUME ["/data"]

EXPOSE 8011
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8011/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.mvp:create_app", "--factory", "--app-dir", "/app/backend", \
     "--host", "0.0.0.0", "--port", "8011", "--no-access-log"]
