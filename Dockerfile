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

# --- Stage 3: Runner ---
FROM python:3.12-slim-bookworm AS runner
WORKDIR /app

# Install Node.js 20
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (standard pip — creates proper console scripts)
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

# Install Playwright Chromium + system deps (needed by 4 backend code paths)
RUN playwright install --with-deps chromium

# Copy Next.js standalone build
COPY --from=nextjs-builder /app/public ./public
RUN mkdir -p .next
COPY --from=nextjs-builder /app/.next/standalone ./
COPY --from=nextjs-builder /app/.next/static ./.next/static

# Copy Python backend
COPY backend/ ./backend/

# Copy entrypoint and supporting files
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY .env.local* ./

ENV NODE_ENV=production
EXPOSE 3000
EXPOSE 8000
ENV PORT=3000

CMD ["./entrypoint.sh"]
