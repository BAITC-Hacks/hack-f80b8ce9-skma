# Hackathon 2026

Стартовый шаблон: **FastAPI** (backend) + **Next.js** (frontend).

> Перед сдачей проекта перепишите этот README с помощью Codex-скилла `hackathon-readme`
> (попросите Codex: «сделай README для жюри»).

## Быстрый старт

Требования: Python 3.10+, Node.js 20+, make.

```bash
make install   # зависимости backend и frontend
make dev       # backend на :8000, frontend на :3000
```

- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

## Команды

| Команда        | Что делает                               |
| -------------- | ---------------------------------------- |
| `make dev`     | запустить backend и frontend вместе      |
| `make test`    | тесты backend (pytest)                   |
| `make lint`    | ruff + eslint                            |
| `make format`  | автоформатирование Python                |
| `make check`   | lint + typecheck + test                  |
| `make up`      | весь стек в Docker                       |

## Структура

```
backend/            FastAPI
  app/api/routes/   HTTP-эндпоинты
  app/schemas/      Pydantic-модели
  app/services/     бизнес-логика
  app/core/         настройки (.env)
  tests/            pytest
frontend/           Next.js (App Router, TypeScript, Tailwind)
  app/              страницы и компоненты
  lib/api.ts        типизированный клиент API
AGENTS.md           правила для Codex
.agents/skills/     скиллы для Codex
```

Frontend проксирует `/api/*` на backend (см. `frontend/next.config.ts`), поэтому CORS в dev не нужен.
