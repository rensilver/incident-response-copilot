FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.12.5

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src

RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --python /usr/local/bin/python3 \
    --locked --no-dev --no-editable --no-cache

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY backend/src ./src

ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "incident_copilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
