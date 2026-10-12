# Multi-stage production container for ORION Autonomous AI Execution Platform
FROM python:3.12-slim AS runtime

# System metadata
LABEL maintainer="ORION Engineering Team" \
      version="1.0.0" \
      description="Autonomous AI Execution Platform — Mission Command Center"

# Install git and essential security tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl ca-certificates gosu && \
    rm -rf /var/lib/apt/lists/*

# Security: Create non-privileged user and workspace
RUN groupadd -g 1000 orion && \
    useradd -u 1000 -g orion -m -s /bin/bash orion && \
    mkdir -p /app /workspace && \
    chown -R orion:orion /app /workspace

WORKDIR /app

# Copy application source code and entrypoint
COPY --chown=orion:orion pyproject.toml /app/
COPY --chown=orion:orion src/ /app/src/
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    ORION_ENV=production \
    ORION_HOST=0.0.0.0 \
    ORION_PORT=8000 \
    ORION_WORKSPACE=/workspace

USER orion

EXPOSE 8000

# Graceful termination signal
STOPSIGNAL SIGTERM

# Built-in health check using standard library urllib respecting dynamic $PORT
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', os.environ.get('ORION_PORT', '8000')); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health')" || exit 1

# Start container with root entrypoint to ensure persistent volume ownership, dropping privileges to orion user via gosu
USER root

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
