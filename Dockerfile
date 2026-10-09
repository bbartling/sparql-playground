FROM python:3.12-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY model ./model
COPY data ./data
RUN uv sync --frozen --no-dev \
  && mkdir -p /app/var \
  && uv run brickts bootstrap

ENV BRICKTS_DB_PATH=/app/var/timeseries.sqlite
ENV BRICKTS_BOOTSTRAP_ON_STARTUP=true
ENV PORT=8080

EXPOSE 8080
# Render injects PORT; default 8080 for local/compose.
CMD ["sh", "-c", "exec uv run brickts serve --host 0.0.0.0 --port ${PORT:-8080}"]
