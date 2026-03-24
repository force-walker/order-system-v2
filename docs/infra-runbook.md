# Infra Runbook (Minimum)

This runbook defines fixed operational commands for local development.

## Scope

- Target repo: `order_system_v2`
- Runtime: Docker Compose
- Services: `api`, `db`, `redis`, `worker`

## 1) Start

```bash
cd ~/.openclaw/workspace/order_system_v2
docker-compose up --build -d
```

Health checks:

```bash
docker-compose ps
curl -i --max-time 8 http://127.0.0.1:8000/health
```

Expected:
- services are `Up`
- `/health` returns `HTTP/1.1 200`

## 2) Stop

```bash
cd ~/.openclaw/workspace/order_system_v2
docker-compose down
```

## 3) Migration

Run migration in API container:

```bash
cd ~/.openclaw/workspace/order_system_v2
docker-compose exec api alembic upgrade head
```

Check current revision:

```bash
docker-compose exec api alembic current
```

## 4) Recovery (local)

Use this when startup is unstable or DB state is inconsistent.

```bash
cd ~/.openclaw/workspace/order_system_v2
docker-compose down -v --remove-orphans
docker-compose up --build -d
```

Then verify:

```bash
docker-compose ps
docker-compose logs --tail=120 api
curl -i --max-time 8 http://127.0.0.1:8000/health
```

## 5) Known issue quick fix

### API tries `127.0.0.1:5432` and fails

Cause: wrong DB host in `backend/.env`.

Fix `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/order_system_v2
```

Restart:

```bash
docker-compose down -v --remove-orphans
docker-compose up --build -d
```
