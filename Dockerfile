FROM python:3.12-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
# Live package lives under Part 2 checkpoint (see [tool.uv.build-backend] module-root).
COPY blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/src \
  ./blog/if-the-analyst-could-create-an-api/part-02-model-crud-ui/checkpoint/src
COPY model ./model
COPY data ./data
RUN uv sync --frozen --no-dev \
  && mkdir -p /app/var \
  && uv run bldgts bootstrap

ENV BLDGTS_DB_PATH=/app/var/timeseries.sqlite
ENV BLDGTS_BOOTSTRAP_ON_STARTUP=true
ENV PORT=8080

EXPOSE 8080
# Render injects PORT; default 8080 for local/compose.
CMD ["sh", "-c", "exec uv run bldgts serve --host 0.0.0.0 --port ${PORT:-8080}"]
