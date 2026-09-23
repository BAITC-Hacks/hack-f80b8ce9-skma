---
name: run-and-verify
description: Install, run and verify the whole project works (backend, frontend, tests). Use before demos, before finishing a task, or when the user says something is broken.
---

# Run and verify

1. `make install` (skip if `backend/.venv` and `frontend/node_modules` exist and deps didn't change).
2. `make check` — ruff, eslint, tsc, pytest. Fix failures before continuing.
3. Start the stack in the background: `make dev`.
4. Smoke test:
   - `curl -s localhost:8000/api/health` → `{"status":"ok"}`
   - `curl -s localhost:3000/api/health` → same (proves the Next.js proxy works)
   - `curl -s -o /dev/null -w '%{http_code}' localhost:3000` → `200`
5. Exercise the feature you changed through the API (curl) or the page.
6. Stop the servers and report exactly what passed and what failed.

## Common problems
- Port busy: `lsof -i :8000` / `lsof -i :3000` and stop the old process.
- `ModuleNotFoundError` in backend: run `make install-backend`.
- Frontend shows API error: backend isn't running or `BACKEND_URL` in `frontend/.env.local` is wrong.
