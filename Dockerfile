FROM python:3.11-slim

RUN pip install --no-cache-dir uv==0.12.6
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY agents ./agents
COPY experiments ./experiments
RUN uv sync --locked --no-dev --no-editable \
    && useradd --uid 10001 --create-home worker
ENV PATH="/app/.venv/bin:$PATH" \
    LAB_ROOT="/app" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1" \
    LANGSMITH_TRACING="false"
USER 10001:10001
CMD ["systems-lab", "gateway"]
