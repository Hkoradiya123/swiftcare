# ── Stage 1: Build virtual environment with uv ───────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN uv venv /opt/venv

COPY swiftcare-contracts /contracts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv /contracts

COPY swiftcare-core/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv -r requirements.txt


# ── Stage 2: Runtime image ─────────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

RUN useradd -m -u 1000 appuser

COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
COPY --chown=appuser:appuser swiftcare-core/ /app/

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
