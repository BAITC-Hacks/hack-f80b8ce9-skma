# Frontend rules (Next.js)

## Structure
- `app/` — App Router. Pages are `app/<route>/page.tsx`.
- Server Components by default; add `"use client"` only for state, effects or event handlers,
  and keep client components small (see `app/items.tsx`).
- `lib/api.ts` — the only place that calls the backend. Add typed functions there;
  types must mirror the Pydantic schemas in `backend/app/schemas/`.

## Conventions
- TypeScript strict; no `any`. Import via the `@/` alias.
- Styling: Tailwind utility classes only; no CSS modules or inline style objects.
- Backend is reached through the `/api/*` rewrite in `next.config.ts` — never hardcode
  `http://localhost:8000` in components.
- Handle loading and error states for every API call visible to the user.
- UI text is in Russian unless the task says otherwise.

## Checks
- `make typecheck`, `make lint`, `make build` must pass.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
