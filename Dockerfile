FROM python:3.11-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image.
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date.
WORKDIR /app
RUN uv sync --no-dev --locked

# Don't write .pyc files at runtime (the container runs on a read-only root fs).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Run as a non-root uid (matches the chart's pod securityContext).
USER 65532:65532

EXPOSE 8080

# Invoke the synced venv directly — no `uv run` so nothing is written at runtime.
CMD ["python", "main.py"]
