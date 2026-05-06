# Web IDE Platform Guide (Next.js + FastAPI + MCP + AWS)

This document explains the codebase structure, dependencies, and how the application works end-to-end so you can confidently extend it later.

---

## 1) Repository layout (what each folder does)

### `src/` — Python MCP server (AWS tools)
This is the **Model Context Protocol server** that exposes AWS tools (EC2 list/start/stop, memory filter, CPU utilization filter).

Key files:
- `src/cloud_mcp_agent/server.py`
  - Defines MCP tools (what the LLM can call).
  - Tool docstrings are important for “semantic tool selection”.
- `src/cloud_mcp_agent/providers/aws.py`
  - Actual AWS implementation using `boto3`:
    - EC2 instance listing
    - DescribeInstanceTypes (RAM in MiB)
    - CloudWatch `GetMetricData` (CPUUtilization)

Notes:
- Tool defaults (`region`, `profile`) are set in `src/cloud_mcp_agent/server.py`.
- Provider `_session()` prefers **env creds** if present (enables server-side STS creds).

### `services/api/` — FastAPI backend (team orchestrator)
This is the **team-hosted backend** that:
- authenticates users via OIDC (Okta/Keycloak) (optional in local dev)
- stores conversations/audits in MySQL
- calls OpenAI
- executes MCP tools via an MCP **stdio client** (spawns the MCP server process)

Key files:
- `services/api/src/ide_platform_api/main.py`
  - FastAPI app setup
  - CORS configuration (dev-friendly)
- `services/api/src/ide_platform_api/routes.py`
  - HTTP endpoints used by the UI:
    - `GET /health`
    - `GET /me`
    - `GET/POST /conversations`
    - `POST /chat` (JSON response)
    - `POST /chat/stream` (SSE stream with tool trace + final answer)
  - In local dev (`AUTH_DISABLED=true`) the backend skips STS AssumeRole enforcement.
- `services/api/src/ide_platform_api/openai_orchestrator.py`
  - The OpenAI “tool-calling loop”
  - Lists MCP tools and converts them to OpenAI tool schema
  - Executes tool calls and feeds tool outputs back to the model
- `services/api/src/ide_platform_api/mcp_client.py`
  - MCP stdio client wrapper
  - Spawns `python -m cloud_mcp_agent.server` and calls tools through MCP
- `services/api/src/ide_platform_api/models.py`
  - SQLAlchemy models (tables): users, conversations, messages, tool_audit, auth_nonces
- `services/api/src/ide_platform_api/auth_oidc.py`
  - OIDC login flow (issuer metadata discovery, redirect, callback token exchange)
- `services/api/alembic/` + `services/api/alembic.ini`
  - Alembic migrations

### `apps/web/` — Next.js web UI (your “Cursor/Claude-like” interface)
This is the UI that provides:
- conversation selection
- message input
- assistant output
- tool trace panel (streams updates during execution)

Key files:
- `apps/web/app/page.tsx`
  - UI
  - Calls the **local Next.js proxy routes** under `/api/*`
  - Parses SSE events (`ready`, `trace`, `final`, `error`)
- `apps/web/app/api/**/route.ts`
  - Server-side proxy routes (important: this removes browser CORS headaches)
  - Proxies cookies and streams SSE from FastAPI to the browser:
    - `apps/web/app/api/me/route.ts`
    - `apps/web/app/api/conversations/route.ts`
    - `apps/web/app/api/chat/stream/route.ts`

### `support/database/` — “support documents” for DB and migrations
- `support/database/01_create_database.sql` creates the MySQL database.
- `support/database/02_schema_migration.md` explains how to run migrations.

### `infra/terraform/` — AWS deployment scaffold (starter)
Terraform starter for VPC + RDS + ECS Fargate + ALB.

---

## 2) Dependencies (what each component uses)

### MCP server (`pyproject.toml` at repo root)
- `fastmcp`: MCP server framework
- `boto3`, `botocore`: AWS SDK

### Backend API (`services/api/pyproject.toml`)
- **Web**: `fastapi`, `uvicorn`
- **Config**: `pydantic`, `pydantic-settings`
- **Database**: `SQLAlchemy`, `PyMySQL`, `alembic`
- **OIDC/security**: `authlib`, `python-jose`, `itsdangerous`
- **LLM**: `openai`
- **MCP client**: `mcp`, `anyio`
- **AWS STS** (prod mode): `boto3`

### Web UI (`apps/web/package.json`)
- `next`, `react`, `react-dom`, `typescript`, `eslint`

---

## 3) Architecture diagram (end-to-end)

```mermaid
flowchart TD
  browser[Browser_UI] --> nextjs[NextJs_apps_web]
  nextjs --> nextApi[NextJs_proxy_routes_/api/*]
  nextApi --> fastapi[FastAPI_services_api]
  fastapi --> mysql[(MySQL_mcp-agen-db)]
  fastapi --> openai[OpenAI_API]
  fastapi --> mcpClient[MCP_stdio_client]
  mcpClient --> mcpServer[cloud_mcp_agent_MCP_server]
  mcpServer --> aws[EC2_CloudWatch_APIs]
```

Why the Next.js proxy matters:
- The browser calls only `http://localhost:3000/api/...` (same origin).
- The proxy talks to FastAPI internally.
- This avoids CORS and “Failed to fetch” issues from origin/IP/localhost/IPv6 mismatches.

---

## 4) How a chat request works (tool-calling loop)

1) User clicks **Send** in UI.
2) UI calls `POST /api/chat/stream` (Next.js route).
3) Next.js proxies to `POST http://127.0.0.1:8002/chat/stream` (FastAPI SSE).
4) FastAPI calls OpenAI with:
   - system prompt
   - user message
   - tool schemas (from MCP server)
5) If OpenAI requests a tool call:
   - FastAPI calls MCP client
   - MCP client spawns the MCP server as a subprocess
   - MCP server executes AWS calls and returns results
6) FastAPI emits SSE events:
   - `trace` events for tool call + tool result
   - `final` event with final assistant answer
7) UI shows:
   - assistant output
   - tool trace panel updates in real time

---

## 5) Configuration (what to set and where)

### Backend (`services/api/.env`)
Most important variables:
- `DATABASE_URL` (MySQL)
- `OPENAI_API_KEY`
- `AUTH_DISABLED` (local dev only)
- `OIDC_*` (for Okta/Keycloak)

MCP subprocess configuration:
- `MCP_COMMAND` (default `python3`)
- `MCP_ARGS` (default `["-m","cloud_mcp_agent.server"]`)
- `MCP_CWD` (optional; can be blank)

AWS assume-role configuration (prod):
- `AWS_ALLOWED_ROLE_ARNS` (JSON list)
- `AWS_DEFAULT_ROLE_ARN` (optional)
- `AWS_ROLE_EXTERNAL_ID` (optional)

### Web (`apps/web/.env.local`)
- `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8002` (used for login URL building)
- `API_BASE=http://127.0.0.1:8002` (used by Next.js proxy routes server-side)

---

## 6) Database: schema + migrations

Tables:
- `users`
- `conversations`
- `messages`
- `tool_audit`
- `auth_nonces`
- `alembic_version`

Create DB:
```bash
mysql -h 127.0.0.1 -P 3307 -u root -p < support/database/01_create_database.sql
```

Run migrations:
```bash
cd services/api
source .venv/bin/activate
export DATABASE_URL='mysql+pymysql://root:...@127.0.0.1:3307/mcp-agen-db'
alembic -c alembic.ini upgrade head
```

---

## 7) Where to change code for common future updates

### Add a new AWS tool
1) Add function in `src/cloud_mcp_agent/providers/aws.py`
2) Expose it as an MCP tool in `src/cloud_mcp_agent/server.py`
3) Restart API (so MCP tool schema refreshes for OpenAI)

### Tighten tool security / policies
- `services/api/src/ide_platform_api/aws_policy.py`
- `services/api/src/ide_platform_api/routes.py`

### Change UI behavior / trace rendering
- `apps/web/app/page.tsx`

### Add RAG later
Recommended direction:
- Add ingestion + embeddings service in `services/`
- Store vectors in a vector store (OpenSearch / pgvector / etc.)
- Retrieve top-k and append context into the OpenAI prompt in `openai_orchestrator.py`

---

## 8) Local run commands (quick reference)

API:
```bash
cd services/api
source .venv/bin/activate
uvicorn ide_platform_api.main:app --host 0.0.0.0 --port 8002 --reload
```

Web:
```bash
cd apps/web
npm run dev
```

Open:
- UI: `http://localhost:3000`
- API health: `http://127.0.0.1:8002/health`

