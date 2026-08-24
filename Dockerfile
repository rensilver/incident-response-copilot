FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

RUN uv venv /opt/venv && uv pip install --python /opt/venv/bin/python --no-cache .

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src ./src

ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "incident_copilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
