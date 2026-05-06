FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install MCP server package from repo root
COPY pyproject.toml /mcp/pyproject.toml
COPY src /mcp/src
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir /mcp

# Install API package
COPY services/api/pyproject.toml /api/pyproject.toml
COPY services/api/README.md /api/README.md
COPY services/api/src /api/src
RUN pip install --no-cache-dir /api

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "ide_platform_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
