# `docker/` — Container Definitions

Docker configurations for development and production deployment.

## Quick Start (Development)

```bash
# Start full stack (LocalStack + Redis + API with hot reload)
docker compose -f docker/docker-compose.dev.yml up

# Start infrastructure only (LocalStack + Redis)
docker compose -f docker/docker-compose.yml up -d

# Seed DynamoDB tables
python scripts/seed_dynamodb.py --endpoint-url http://localhost:4566
```

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Production multi-stage build (Python 3.12 slim) |
| `Dockerfile.dev` | Development build with hot reload |
| `docker-compose.yml` | Infrastructure only (LocalStack + Redis) |
| `docker-compose.dev.yml` | Full stack (infra + API service) |

## Production Image (`Dockerfile`)

```
Stage 1 (builder): Install dependencies from pyproject.toml
Stage 2 (runtime): Copy deps + src into slim Python 3.12 image
```

- Exposes port **8080**
- Health check: `GET /health` every 30s
- Default CMD: `uvicorn bluestar.api.app:create_app --factory --host 0.0.0.0 --port 8080`
- Override CMD per agent via ECS task definition

## Development Image (`Dockerfile.dev`)

- Single-stage with all extras (`dev`, `agents`, `mcp`, `ingestion`)
- Volume mounts `src/` and `tests/` for hot reload
- Uses `--reload` flag for auto-restart on code changes

## Services

### `docker-compose.yml` (Infrastructure)

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| localstack | `localstack/localstack:3.6` | 4566 | DynamoDB, S3, SQS, EventBridge |
| redis | `redis:7-alpine` | 6379 | Cache backend |

### `docker-compose.dev.yml` (Full Stack)

Extends infrastructure with:

| Service | Build | Ports | Env |
|---------|-------|-------|-----|
| bluestar-api | `Dockerfile.dev` | 8080 | `BLUESTAR_ENVIRONMENT=dev`, `BLUESTAR_LLM_PROVIDER=mock` |

## Environment Variables

Key variables set in dev compose:

```
BLUESTAR_ENVIRONMENT=dev
BLUESTAR_LLM_PROVIDER=mock
BLUESTAR_DYNAMO_ENDPOINT_URL=http://localstack:4566
BLUESTAR_REDIS_HOST=redis
BLUESTAR_S3_ENDPOINT_URL=http://localstack:4566
```
