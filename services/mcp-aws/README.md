# services/mcp-aws

The AWS MCP server implementation lives in the repo root Python package:

- Python package: `cloud_mcp_agent`
- Source: [`../../src/cloud_mcp_agent`](../../src/cloud_mcp_agent)

This folder is a stable “service boundary” for Docker/ECS:

- Container command should run: `python -m cloud_mcp_agent.server`

The **team platform** (`services/api`) typically does not need a separate MCP container initially; it can spawn the MCP server via stdio.
