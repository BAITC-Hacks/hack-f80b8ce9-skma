---
name: add-frontend-page
description: Add a new Next.js page or UI feature wired to the backend. Use when the user asks for a new page, screen, form, or UI component.
---

# Add a frontend page

Follow `frontend/AGENTS.md`.

## Steps
1. Create `frontend/app/<route>/page.tsx` as a Server Component with the layout and headings.
2. Put interactive parts (forms, state, fetches from the browser) in a separate
   `"use client"` component next to the page, like `frontend/app/items.tsx`.
3. Call the backend only through `frontend/lib/api.ts`; add missing typed functions there.
4. Show loading, empty and error states.
5. Style with Tailwind; keep the look consistent with `app/page.tsx`
   (`max-w-2xl`, zinc palette, `rounded-md`).
6. Link the page from the home page or navigation if the user should reach it.
7. Verify: `make typecheck && make lint`, then open the page with `make dev` running.
