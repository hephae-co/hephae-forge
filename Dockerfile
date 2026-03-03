# ───────────────────────────────────────────────────────────
# Multi-stage Dockerfile: Next.js (port 3000) + FastAPI (port 8000)
# Uses entrypoint.sh to run both processes in a single container.
# ───────────────────────────────────────────────────────────

# --- Stage 1: Node.js dependencies ---
FROM node:20-bookworm-slim AS node-deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# --- Stage 2: Next.js build ---
FROM node:20-bookworm-slim AS nextjs-builder
WORKDIR /app
COPY --from=node-deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Stage 3: Combined runner (Playwright base for browser + gRPC compat) ---
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Install Node.js 20
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python deps system-wide (--break-system-packages for PEP 668)
# This creates proper console scripts (uvicorn, pytest, etc.) in PATH
COPY pyproject.toml ./
RUN pip install --no-cache-dir --break-system-packages ".[dev]"

# Copy Next.js standalone build
COPY --from=nextjs-builder /app/public ./public
RUN mkdir -p .next
COPY --from=nextjs-builder /app/.next/standalone ./
COPY --from=nextjs-builder /app/.next/static ./.next/static

# Copy Python backend
COPY backend/ ./backend/

# Copy entrypoint
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY .env.local* ./

EXPOSE 3000
EXPOSE 8000
ENV PORT=3000

CMD ["./entrypoint.sh"]
