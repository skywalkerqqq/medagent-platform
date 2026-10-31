FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MEDAGENT_DB=/app/data/medagent.db

WORKDIR /app

COPY production/requirements.txt /app/production/requirements.txt
RUN pip install --no-cache-dir -r /app/production/requirements.txt

COPY server /app/server
COPY web /app/web
COPY production /app/production

RUN useradd --system --uid 10001 --create-home medagent \
    && mkdir -p /app/data \
    && chown -R medagent:medagent /app

USER medagent
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"

# 单 worker：SQLite 写锁限制；完成 PostgreSQL 迁移后再水平扩展
CMD ["uvicorn", "production.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
