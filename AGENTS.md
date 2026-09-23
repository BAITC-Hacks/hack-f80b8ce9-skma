# AGENTS.md

Hackathon project: FastAPI backend + Next.js frontend. Speed matters, but the demo must work.

## Layout
- `backend/` — FastAPI app (Python 3.10+). See `backend/AGENTS.md`.
- `frontend/` — Next.js App Router, TypeScript, Tailwind v4. See `frontend/AGENTS.md`.
- `.agents/skills/` — reusable Codex skills for this repo.
- `Makefile` — single entry point for all commands. Prefer `make <target>` over ad-hoc commands.

## Commands
- Install: `make install`
- Run both apps: `make dev` (backend :8000, frontend :3000)
- Tests: `make test`
- Lint / format: `make lint`, `make format`
- Full check before finishing a task: `make check`

## Working rules
- Keep changes small and focused on the task. Don't refactor unrelated code.
- Match existing structure and naming; add new code next to similar code.
- Every new backend endpoint gets at least one test in `backend/tests/`.
- When the API shape changes, update `frontend/lib/api.ts` types in the same change.
- Never commit secrets. New config goes into `.env.example` with a placeholder value.
- Don't add dependencies without a clear need; if you add one, put it in
  `backend/pyproject.toml` or `frontend/package.json`, never install globally.
- Before saying a task is done, run `make check` and report the result honestly.
  If something fails and you can't fix it, say what failed.

## Definition of done
1. Code compiles, `make check` passes.
2. The feature is reachable from the UI or documented in Swagger (`/docs`).
3. README is updated if setup steps or env vars changed.
