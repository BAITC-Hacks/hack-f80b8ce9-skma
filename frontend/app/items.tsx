"use client";

import { useEffect, useState } from "react";

import { api, type Item } from "@/lib/api";

export function Items() {
  const [items, setItems] = useState<Item[]>([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listItems().then(setItems).catch((e: Error) => setError(e.message));
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    try {
      const item = await api.createItem({ title });
      setItems((prev) => [...prev, item]);
      setTitle("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDelete(id: number) {
    await api.deleteItem(id);
    setItems((prev) => prev.filter((item) => item.id !== id));
  }

  return (
    <section className="space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Новый элемент"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2"
        />
        <button className="rounded-md bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-700">
          Добавить
        </button>
      </form>
      {error && <p className="text-sm text-red-600">Ошибка API: {error}</p>}
      <ul className="divide-y divide-zinc-200 rounded-md border border-zinc-200 bg-white">
        {items.length === 0 && <li className="px-4 py-3 text-zinc-500">Пока пусто</li>}
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between px-4 py-3">
            <span>{item.title}</span>
            <button
              onClick={() => handleDelete(item.id)}
              className="text-sm text-zinc-500 hover:text-red-600"
            >
              Удалить
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
