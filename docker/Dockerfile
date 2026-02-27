# BlueStar Payroll Processing Platform — Production Build
# Multi-stage: build dependencies, then copy into slim image.
# Per-agent entrypoint via ECS task definition CMD override.

FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --target=/app/deps .

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/deps /app/deps
COPY --from=builder /app/src /app/src
ENV PYTHONPATH=/app/deps:/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Default: run the API server. Override CMD per agent in ECS task definition.
CMD ["python", "-m", "uvicorn", "bluestar.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
