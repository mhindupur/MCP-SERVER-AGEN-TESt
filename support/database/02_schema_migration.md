# Database schema + migrations (MySQL)

This project uses **Alembic** migrations.

## Local (your setup)

- Host: `127.0.0.1`
- Port: `3307`
- User: `root`
- Database: `mcp-agen-db`

## Bootstrap database

```bash
mysql -h 127.0.0.1 -P 3307 -u root -p < support/database/01_create_database.sql
```

## Apply migrations

From repo root (recommended):

```bash
cd services/api
source .venv/bin/activate  # or your active venv
export DATABASE_URL='mysql+pymysql://root:btt-root-local-only@127.0.0.1:3307/mcp-agen-db'
alembic -c alembic.ini upgrade head
```

## Create a new migration (future)

```bash
cd services/api
export DATABASE_URL='mysql+pymysql://root:btt-root-local-only@127.0.0.1:3307/mcp-agen-db'
alembic -c alembic.ini revision --autogenerate -m "describe change"
```

