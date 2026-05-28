# Stage 1: Build React UI with Bun
FROM oven/bun:1 AS ui-builder
WORKDIR /ui
COPY ui/package.json ui/bun.lock* ./
RUN bun install --frozen-lockfile
COPY ui/ ./
RUN bun run build

# Stage 2: Python runtime with WeasyPrint + FastAPI
FROM python:3.12-slim

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Copy built UI from stage 1
COPY --from=ui-builder /ui/dist ./ui/dist

EXPOSE 8000

CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
