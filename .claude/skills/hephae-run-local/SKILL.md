---
name: hephae-run-local
description: Run Hephae services locally — API (port 8080), web frontend (port 3000), admin (port 3001), or all. Handles venv setup, package installs, port cleanup, and health verification.
argument-hint: [api | web | admin | all]
user_invocable: true
---

# Run Local — Local Development Server Launcher

Starts Hephae services locally with the correct venv, packages, and ports.

## Input

| Arg | What It Starts | Port |
|-----|---------------|------|
| `api` or empty | Unified API (FastAPI + uvicorn) | 8080 |
| `web` | Customer-facing web frontend (Next.js) | 3000 |
| `admin` | Admin dashboard (Next.js) | 3001 |
| `all` | API + web + admin | 8080, 3000, 3001 |

Arguments: $ARGUMENTS

If no args, default to `api`.

---

## PHASE 1: VENV CHECK

The project uses a venv at `.venv/` in the repo root.

```bash
ls /Users/sarthak/Desktop/hephae/hephae-forge/.venv/bin/activate 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

**If MISSING:** Tell the user to create it first:
```bash
python3.13 -m venv .venv
```
Then proceed with package install.

---

## PHASE 2: PACKAGE CHECK + INSTALL (API only)

Only needed for `api` or `all`. Skip for `web`/`admin`.

### 2a. Check if packages are installed

```bash
source /Users/sarthak/Desktop/hephae/hephae-forge/.venv/bin/activate && python -c "import hephae_api" 2>/dev/null && echo "OK" || echo "MISSING"
```

### 2b. If MISSING — install all packages

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
source .venv/bin/activate
pip install -q -e lib/common -e lib/db -e lib/integrations -e agents -e apps/api
pip install -q google-cloud-run google-cloud-tasks google-cloud-scheduler google-generativeai pdfplumber
```

**Note:** pip may warn about dependency resolution complexity — this is expected, the install still succeeds.

### 2c. Verify import

```bash
source .venv/bin/activate && python -c "from hephae_api.main import app; print('Import OK')" 2>&1
```

If import fails, read the traceback — it will name the missing package. Install it and retry once.

---

## PHASE 3: KILL EXISTING PROCESSES

Before starting, clear the target port(s).

### For API (port 8080):
```bash
pkill -f "uvicorn hephae_api" 2>/dev/null; sleep 1
```

### For web (port 3000):
```bash
pkill -f "next dev.*3000" 2>/dev/null; sleep 1
```

### For admin (port 3001):
```bash
pkill -f "next dev.*3001" 2>/dev/null; sleep 1
```

---

## PHASE 4: START SERVICES

Run each service in the background using `run_in_background: true`.

### API

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
source .venv/bin/activate && uvicorn hephae_api.main:app --reload --port 8080 2>&1
```

Wait up to 15 seconds for this log line in the output:
```
INFO:     Application startup complete.
```

If the worker process crashes (look for `Traceback` or `ImportError` in the output), read the error and fix it — usually a missing package.

### Web

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge/apps/web
npm run dev -- --port 3000 2>&1
```

Wait for: `Ready in` or `Local: http://localhost:3000`

### Admin

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge/apps/admin
npm run dev -- --port 3001 2>&1
```

Wait for: `Ready in` or `Local: http://localhost:3001`

---

## PHASE 5: HEALTH VERIFICATION

### API health check:
```bash
curl -s http://127.0.0.1:8080/api/health
```

Expected: `{"status":"ok","service":"hephae-unified-api"}`

**If 403:** The API requires auth — use an identity token:
```bash
TOKEN=$(gcloud auth print-identity-token 2>/dev/null)
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/health
```

### Web health check:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```
Expected: `200`

### Admin health check:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001
```
Expected: `200`

---

## PHASE 6: REPORT

```
## Local Services Running

| Service | URL | Status |
|---------|-----|--------|
| API     | http://localhost:8080 | OK |
| Web     | http://localhost:3000 | OK |
| Admin   | http://localhost:3001 | OK |

Logs: background task IDs shown above — use TaskOutput to tail them.
```

---

## Common Issues

| Error | Fix |
|-------|-----|
| `ImportError: cannot import name 'X' from 'google.cloud'` | `pip install google-cloud-<name>` (e.g. `google-cloud-run`, `google-cloud-tasks`) |
| `Address already in use` | Run the pkill step again, wait 2s, retry |
| `ModuleNotFoundError: No module named 'hephae_api'` | Packages not installed — run Phase 2 |
| `[Errno 48]` on restart | Previous process still dying — `sleep 2` and retry |
| ADK `UserWarning: [EXPERIMENTAL] feature AGENT_CONFIG` | Expected warning, not an error — ignore |

## What NOT To Do

- Do NOT use `pip` directly — always `source .venv/bin/activate` first
- Do NOT skip the pkill step — port conflicts will cause cryptic failures
- Do NOT assume packages are installed if `hephae_api` import fails
- Do NOT start web/admin before verifying the API is up (if starting `all`)
