FROM repository.ncr.ntnu.no/python:3.13-alpine
COPY --from=repository.ncr.ntnu.no/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy poetry config and install dependencies
COPY pyproject.toml .
COPY uv.lock .

# Copy application code
COPY . .

RUN uv sync

# Run application
CMD ["/app/.venv/bin/fastapi", "run", "container_lock/main.py"]
