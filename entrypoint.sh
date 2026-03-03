#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────
# entrypoint.sh — Start Next.js + FastAPI in a single container
# ─────────────────────────────────────────────────────────

export PYTHONUNBUFFERED=1

cleanup() {
    echo "[entrypoint] Shutting down..."
    kill "$FASTAPI_PID" "$NEXTJS_PID" 2>/dev/null || true
    wait "$FASTAPI_PID" "$NEXTJS_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# 1) Start FastAPI (merge stderr into stdout for Cloud Run logging)
echo "[entrypoint] Starting FastAPI on :8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info 2>&1 &
FASTAPI_PID=$!

# 2) Start Next.js
echo "[entrypoint] Starting Next.js on :3000..."
PORT=3000 HOSTNAME=0.0.0.0 NODE_ENV=production node server.js 2>&1 &
NEXTJS_PID=$!

# Wait for either to exit — if one dies, tear down the other
wait -n "$FASTAPI_PID" "$NEXTJS_PID"
EXIT_CODE=$?
echo "[entrypoint] Process exited ($EXIT_CODE), tearing down..."
cleanup
