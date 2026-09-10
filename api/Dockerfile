# Build context is the repository root, so paths below start from there.

# Official Python on a trimmed Debian base. Matches requires-python in pyproject.
FROM python:3.11-slim

# Where every later command runs. Created if it does not exist.
WORKDIR /app

# Take the uv binary out of uv's published image instead of downloading an
# installer at build time. One layer, pinned version, no network script.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

# Manifests only. Copying these before the source keeps the install layer
# cached, so editing main.py does not reinstall every dependency.
# The workspace lock covers both members, so uv needs both manifests present.
COPY pyproject.toml uv.lock ./
COPY api/pyproject.toml api/
COPY ingest/pyproject.toml ingest/

# --frozen: install exactly what the lock says, fail if it is stale.
# --no-dev: leave ruff and pytest out of the production image.
# --package rag-api: only the API member, not ingest.
# Creates the virtualenv at /app/.venv.
RUN uv sync --frozen --no-dev --package rag-api

# Source code last, so a code change rebuilds only this small layer.
# Lands at /app/app, which is what makes the import path app.main resolve.
COPY api/app ./app

# Nothing activates a virtualenv in a container, and activation is mostly
# just this. Putting the venv first means uvicorn resolves to the one uv
# installed rather than a system Python with none of the packages.
ENV PATH="/app/.venv/bin:$PATH"

# Documentation only. Records the listening port, changes nothing at runtime.
EXPOSE 8000

# 0.0.0.0 is the part that matters: uvicorn defaults to localhost, which inside
# a container means the container itself, unreachable from Compose or Caddy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
