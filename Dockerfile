# Multi-stage production container for ORION Autonomous AI Execution Platform
FROM python:3.12-slim AS runtime

# System metadata
LABEL maintainer="ORION Engineering Team" \
      version="1.0.0" \
      description="Autonomous AI Execution Platform — Mission Command Center"

# Install git and essential security tooling
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Security: Create non-privileged user and workspace
RUN groupadd -g 1000 orion && \
    useradd -u 1000 -g orion -m -s /bin/bash orion && \
    mkdir -p /app /workspace && \
    chown -R orion:orion /app /workspace

WORKDIR /app

# Copy application source code
COPY --chown=orion:orion pyproject.toml /app/
COPY --chown=orion:orion src/ /app/src/

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

# Built-in health check using standard library urllib
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

ENTRYPOINT ["python", "-m", "orion"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workspace", "/workspace"]
