# `bluestar/api` — FastAPI Web Service

HTTP interface for health checks, readiness probes, and admin endpoints.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check — returns `{"status": "healthy"}` |
| `GET` | `/ready` | Readiness check — verifies dependencies (TODO) |
| `GET` | `/admin/pipeline/{plan_id}/{pay_freq}` | View pipeline configuration |
| `GET` | `/admin/rules/{category}` | View validation rules |

## Running

```bash
# Development (hot reload)
uvicorn bluestar.api.app:create_app --factory --reload --port 8080

# Production (via Docker)
docker compose -f docker/docker-compose.dev.yml up bluestar-api
```

## Structure

```
api/
├── app.py              # FastAPI factory with lifespan context
└── routes/
    ├── health.py       # /health and /ready endpoints
    └── admin.py        # /admin/* configuration endpoints
```

## App Factory (`app.py`)

Uses FastAPI's lifespan pattern for resource initialization:

```python
from bluestar.api.app import create_app

app = create_app()  # loads AppSettings, mounts routers
```

The lifespan context manager initializes persistence backends at startup and tears them down on shutdown.

## Adding New Routes

1. Create `routes/new_route.py` with an `APIRouter`
2. Mount in `app.py`: `app.include_router(new_router, prefix="/new")`
3. Inject dependencies via `app.state` (set during lifespan)
