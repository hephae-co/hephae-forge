# ───────────────────────────────────────────────────────────
# Multi-stage Dockerfile: Next.js (port 3000) + FastAPI (port 8000)
# Uses supervisord to run both processes in a single container.
# ───────────────────────────────────────────────────────────

# --- Stage 1: Node.js dependencies (all deps needed for build) ---
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

# --- Stage 3: Python dependencies ---
FROM python:3.12-slim-bookworm AS python-deps
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir --target=/pylibs ".[dev]"

# --- Stage 4: Combined runner (Playwright base for browser support) ---
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PYTHONPATH=/app:/pylibs
ENV PATH="/pylibs/bin:$PATH"

# Install Node.js 20 + supervisord
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl supervisor && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create app user (use high GID/UID to avoid conflicts with base image)
RUN addgroup --system --gid 1099 appuser && \
    adduser --system --uid 1099 --ingroup appuser appuser

# Copy Python libraries
COPY --from=python-deps /pylibs /pylibs

# Copy Next.js standalone build
COPY --from=nextjs-builder /app/public ./public
RUN mkdir -p .next && chown appuser:appuser .next
COPY --from=nextjs-builder --chown=appuser:appuser /app/.next/standalone ./
COPY --from=nextjs-builder --chown=appuser:appuser /app/.next/static ./.next/static

# Copy Python backend
COPY --chown=appuser:appuser backend/ ./backend/

# Copy supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy test runner scripts and pytest config
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser pyproject.toml ./

# Copy .env.local if it exists (non-fatal if missing)
COPY --chown=appuser:appuser .env.local* ./

USER appuser

# Cloud Run sends traffic to PORT (default 3000)
EXPOSE 3000
EXPOSE 8000
ENV PORT=3000

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
