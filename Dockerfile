# -----------------------------
# Stage 1: Builder
# -----------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
    && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*9

WORKDIR /app

# Copy only dependency files first
COPY requirements.txt ./

# Install dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# -----------------------------
# Stage 2: Final
# -----------------------------
FROM python:3.12-slim AS final

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /app

# Copy installed packages and app from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/app /app/app

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app && chown -R app:app /app
USER app

EXPOSE 8080

CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:8080", "-k", "uvicorn.workers.UvicornWorker", "--workers", "1"]