# Container Lock Service

## Description
Enforces exclusive container usage per IP address in QEMU Scale-to-Zero Lab environment.

## Installation
```bash
cd container-lock
uv sync
```

## Usage
```bash
# Start the service
uv run uvicorn container_lock.main:app --host 127.0.0.1 --port 8000
```

## Docker
```bash
# Build and run with Docker
docker build -t container-lock .
docker run -p 8000:8000 container-lock
