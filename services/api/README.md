# ide-platform-api (FastAPI)

This service is the **team backend** for the Next.js web IDE:

- OIDC login (Okta/Keycloak)
- OpenAI tool-calling loop
- MCP stdio client (runs the repo’s Python MCP server)
- MySQL persistence (users/conversations/messages/audit)
- Per-user AWS STS AssumeRole (temporary creds injected into MCP subprocess env)

## Local dev

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ../../  # installs cloud-mcp-agent from repo root
pip install -e .
cp .env.example .env
uvicorn ide_platform_api.main:app --reload --port 8000
```

## Notes

- For local testing without SSO, set `AUTH_DISABLED=true` in `.env` (dev only).
- The MCP server command defaults to running `python -m cloud_mcp_agent.server`.
