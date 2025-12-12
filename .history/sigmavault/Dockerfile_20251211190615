# =============================================================================
# ΣVAULT Docker Container - Multi-Stage Production Build
# =============================================================================
# 
# This Dockerfile creates an optimized container for running ΣVAULT
# with FUSE support for virtual filesystem mounting.
#
# Build: docker build -t sigmavault:latest .
# Run:   docker run --privileged --cap-add SYS_ADMIN --device /dev/fuse sigmavault
#
# For development:
#   docker build --target development -t sigmavault:dev .
#   docker run -it -v $(pwd):/app sigmavault:dev bash
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Base Python with FUSE dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS base

# Labels
LABEL org.opencontainers.image.title="ΣVAULT"
LABEL org.opencontainers.image.description="Cryptographic vault with dimensional scattering"
LABEL org.opencontainers.image.authors="ΣVAULT Team"
LABEL org.opencontainers.image.source="https://github.com/sigmavault/sigmavault"
LABEL org.opencontainers.image.licenses="AGPLv3"

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # ΣVAULT specific
    SIGMAVAULT_LOG_LEVEL=INFO \
    SIGMAVAULT_CONTAINER=docker

# Install system dependencies for FUSE
RUN apt-get update && apt-get install -y --no-install-recommends \
    fuse3 \
    libfuse3-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /etc/fuse

# Configure FUSE to allow non-root access
RUN echo 'user_allow_other' >> /etc/fuse.conf

# Create non-root user for security
RUN groupadd --gid 1000 sigmavault \
    && useradd --uid 1000 --gid 1000 --create-home sigmavault \
    && mkdir -p /vault /mnt/sigmavault \
    && chown -R sigmavault:sigmavault /vault /mnt/sigmavault

# -----------------------------------------------------------------------------
# Stage 2: Development image with all dev dependencies
# -----------------------------------------------------------------------------
FROM base AS development

# Install dev tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    vim \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements*.txt ./
COPY pyproject.toml setup.py setup.cfg ./

# Install all dependencies including dev
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e ".[dev,test]"

# Copy source code
COPY . .

# Development runs as root for flexibility
USER root

# Default command for development
CMD ["bash"]

# -----------------------------------------------------------------------------
# Stage 3: Builder - Install production dependencies
# -----------------------------------------------------------------------------
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only what's needed for dependency installation
COPY requirements.txt pyproject.toml setup.py setup.cfg ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

# Copy source code
COPY sigmavault/ ./sigmavault/

# Install the package
RUN pip install . --no-deps

# -----------------------------------------------------------------------------
# Stage 4: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM base AS production

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the installed package
COPY --from=builder /opt/venv/lib/python3.11/site-packages/sigmavault* /opt/venv/lib/python3.11/site-packages/

# Set working directory
WORKDIR /app

# Create vault data directory
RUN mkdir -p /app/data /app/config \
    && chown -R sigmavault:sigmavault /app

# Switch to non-root user
USER sigmavault

# Volume for persistent vault data
VOLUME ["/vault", "/app/config"]

# Expose API port (if running server mode)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from sigmavault.core import Vault; print('healthy')" || exit 1

# Default command
CMD ["python", "-m", "sigmavault"]

# -----------------------------------------------------------------------------
# Stage 5: Test runner
# -----------------------------------------------------------------------------
FROM development AS test

# Install test dependencies
RUN pip install pytest pytest-cov pytest-asyncio hypothesis

# Run tests by default
CMD ["python", "-m", "pytest", "-v", "--cov=sigmavault", "--cov-report=term-missing"]
