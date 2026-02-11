# Build stage
FROM python:3.10-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Create wheels for all dependencies, preferring CPU-only versions for PyTorch
# We add torch explicitly here to ensure the CPU version is picked up if referenced
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Install system runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install all wheels
RUN pip install --no-cache /wheels/*

COPY . .

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Pre-download model during build to avoid runtime timeout/OOM
RUN python scripts/download_model.py

EXPOSE 8000

# Use shell form to expand variable
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
