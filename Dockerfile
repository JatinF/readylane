FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser

USER appuser
ENV READYLANE_HOST=0.0.0.0 \
    READYLANE_PORT=8080 \
    READYLANE_DB=/data/readylane.sqlite
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=8 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"]
CMD ["python", "-m", "readylane"]
