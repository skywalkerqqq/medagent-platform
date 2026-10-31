FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY server ./server
COPY web ./web
COPY tests ./tests
COPY docs ./docs

RUN mkdir -p /app/data

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=3)" || exit 1

CMD ["python", "server/app.py", "--port", "8090", "--host", "0.0.0.0", "--db", "data/medagent.db"]
