FROM python:3.10-slim AS builder

WORKDIR /app

# Build deps for compiled wheels (lxml, psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

# Create venv and install Python deps
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt


FROM python:3.10-slim

WORKDIR /app

# Runtime deps (TLS certs + optional native libs used by common wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY core/ /app/core/
COPY domain/ /app/domain/
COPY infrastructure/ /app/infrastructure/
COPY interfaces/ /app/interfaces/
COPY shared/ /app/shared/
COPY pyproject.toml /app/pyproject.toml

# Non-root user + writable runtime dirs (sqlite + charts + logs)
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data /app/data/charts /app/logs \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Use module invocation so we don't depend on a separate `uvicorn` executable in PATH.
CMD ["python", "-m", "uvicorn", "interfaces.rest_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "75"]


