# ====================================================================
# REDOPS-AI - MULTI-STAGE DOCKER BUILD
# Full Multi-Language Environment: Python 3.12, Go 1.22, Cython, C-Tools
# ====================================================================

FROM python:3.12-slim-bookworm

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    TERM=xterm-256color \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install system dependencies, C compiler for Cython, and Go runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    curl \
    git \
    golang-go \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and project definitions
COPY pyproject.toml* setup.py* ./

# Install Python packages required for Swarm, Cython, FastAPI, and Rich TUI
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    websockets \
    pydantic \
    rich \
    prompt_toolkit \
    cython \
    setuptools \
    dnspython \
    httpx

# Copy source code and skills ecosystem
COPY . /app/

# Build Cython extensions (if setup script exists)
RUN if [ -f cython_core/setup.py ]; then \
        python cython_core/setup.py build_ext --inplace || true; \
    fi

# Expose ports: 8000 (FastAPI & Web Cockpit), 9090 (Go Micro-Daemon)
EXPOSE 8000 9090

# Default command launches interactive REPL
CMD ["python", "run.py", "--mode", "cli"]
