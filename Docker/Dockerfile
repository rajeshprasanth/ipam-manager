# syntax=docker/dockerfile:1

# --------------------------------------------------------------------------- #
# Stage 1: build — install runtime dependencies into an isolated prefix.
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# --------------------------------------------------------------------------- #
# Stage 2: runtime — slim image with only the installed deps + application.
# --------------------------------------------------------------------------- #
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

WORKDIR /app

COPY --from=builder /install /install

COPY . .

COPY Docker/docker-entrypoint.sh /app/docker-entrypoint.sh

RUN groupadd --system app && useradd --system --gid app app \
    && mkdir -p /app/logs \
    && chown -R app:app /app \
    && chmod +x /app/docker-entrypoint.sh

# Container starts as root so the entrypoint can fix permissions on a
# bind-mounted logs/ directory (created root-owned by Compose), then drops to
# the unprivileged "app" user via setpriv before serving.
# USER app

EXPOSE 8076

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8076') + '/', timeout=4)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
