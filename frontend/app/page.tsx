import { Items } from "./items";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-12">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold">Hackathon 2026</h1>
        <p className="text-zinc-600">FastAPI + Next.js стартер. Пример CRUD ниже.</p>
      </header>
      <Items />
    </main>
  );
}
