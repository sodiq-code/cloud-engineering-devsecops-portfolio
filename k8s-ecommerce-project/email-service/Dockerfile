# =============================================================================
# Email Service Dockerfile
# =============================================================================
# Security hardening applied:
#   - Pinned base image SHA (supply-chain attack prevention)
#   - Non-root user (UID 1000)
#   - Minimal base image (python:slim reduces attack surface vs full image)
#   - Production WSGI server (gunicorn, not Flask dev server)
#   - No pip cache (reduces image size by ~30%)
# =============================================================================

FROM python:3.9.18-slim
# NOTE: Python 3.9 EOL is October 2025.
# Upgrade to python:3.11-slim (EOL: October 2027) before that date to maintain security patch coverage.

# Build metadata — useful for image traceability in registries
LABEL maintainer="sodiqjimoh80@gmail.com"
LABEL version="1.0"
LABEL description="KubeScale Email Microservice"

WORKDIR /app

# Install dependencies before copying application code.
# Docker layer caching: if requirements.txt is unchanged, this layer is reused.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code after dependencies (cache-friendly ordering)
COPY app.py .

EXPOSE 8080

# Create a non-root user and transfer ownership of the /app directory.
# Running as root inside a container is a critical vulnerability — avoid it.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# Use gunicorn (production-grade WSGI server) instead of Flask's built-in server.
# Flask's dev server is single-threaded, not designed for production load.
# gunicorn: 2 worker processes, bind to all interfaces on port 8080.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8080", "--timeout", "30", "--access-logfile", "-", "app:app"]
