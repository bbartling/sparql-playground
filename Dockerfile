FROM python:3.12-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY model ./model
COPY data ./data
RUN uv sync --frozen --no-dev

ENV BRICKTS_DB_PATH=/app/var/timeseries.sqlite
ENV BRICKTS_BOOTSTRAP_ON_STARTUP=true

EXPOSE 8080
CMD ["uv", "run", "brickts", "serve", "--host", "0.0.0.0", "--port", "8080"]
