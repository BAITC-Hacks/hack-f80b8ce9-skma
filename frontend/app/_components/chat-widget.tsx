"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ConfirmCard, type PendingStatus } from "@/app/_components/confirm-card";
import { ProductCard } from "@/app/_components/product-card";
import { api, ApiError, type ChatResponse } from "@/lib/api";

type Message =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; text: string; data?: ChatResponse };

const SUGGESTIONS = [
  "Есть в наличии 200300285_?",
  "Автомат Legrand DRX250 160А",
  "Какие условия доставки и оплаты?",
];

const SESSION_KEY = "ekt_session_id";
const CART_KEY = "ekt_cart_id";

function storageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Private mode: the chat still works for this page view.
  }
}

function sessionId(): string {
  let id = storageGet(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    storageSet(SESSION_KEY, id);
  }
  return id;
}

function errorText(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) return "Товара уже нет в наличии.";
  if (error instanceof ApiError && error.status === 503) return "Каталог временно недоступен.";
  return "Не удалось связаться с сервером.";
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [cartUrl, setCartUrl] = useState<string | null>(null);
  const [pendingStatus, setPendingStatus] = useState<Record<string, PendingStatus>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, open]);

  function addAssistant(text: string, data?: ChatResponse) {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", text, data }]);
  }

  async function send(text: string, retry = false) {
    const message = text.trim();
    if (!message || loading) return;
    if (!retry) {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text: message }]);
      setInput("");
    }
    setLoading(true);
    setFailed(null);
    try {
      const data = await api.chat({
        session_id: sessionId(),
        message,
        cart_id: storageGet(CART_KEY),
      });
      storageSet(CART_KEY, data.cart_id);
      if (data.cart_url) setCartUrl(data.cart_url);
      if (data.pending) {
        setPendingStatus((prev) => ({ ...prev, [data.pending!.pending_id]: "open" }));
      }
      addAssistant(data.reply, data);
    } catch {
      setFailed(message);
    } finally {
      setLoading(false);
    }
  }

  async function resolvePending(pendingId: string, confirm: boolean) {
    const cartId = storageGet(CART_KEY);
    if (!cartId) return;
    setPendingStatus((prev) => ({ ...prev, [pendingId]: "busy" }));
    try {
      if (confirm) {
        const cart = await api.confirmAdd(cartId, pendingId);
        setCartUrl(`/cart/${cart.cart_id}`);
        addAssistant(`Готово! В корзине позиций: ${cart.items.length}.`);
      } else {
        await api.rejectAdd(cartId, pendingId);
      }
      setPendingStatus((prev) => ({ ...prev, [pendingId]: confirm ? "confirmed" : "rejected" }));
    } catch (error) {
      setPendingStatus((prev) => ({ ...prev, [pendingId]: "rejected" }));
      addAssistant(`${errorText(error)} Корзина не изменилась.`);
    }
  }

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-blue-700 px-5 py-3 font-medium text-white shadow-lg hover:bg-blue-800 sm:right-6 sm:bottom-6"
        >
          <span aria-hidden>💬</span> Консультант
        </button>
      )}

      {open && (
        <section
          aria-label="Чат с консультантом"
          className="fixed inset-0 z-50 flex flex-col bg-zinc-50 sm:inset-auto sm:right-6 sm:bottom-6 sm:h-[640px] sm:max-h-[calc(100vh-3rem)] sm:w-[420px] sm:rounded-xl sm:border sm:border-zinc-200 sm:shadow-2xl"
        >
          <header className="flex items-center justify-between gap-2 bg-blue-700 px-4 py-3 text-white sm:rounded-t-xl">
            <div>
              <p className="font-semibold">ИИ-консультант ekt.kz</p>
              <p className="text-xs text-blue-100">Наличие, аналоги, условия покупки</p>
            </div>
            <div className="flex items-center gap-3">
              {cartUrl && (
                <Link href={cartUrl} className="rounded bg-white/15 px-2 py-1 text-sm hover:bg-white/25">
                  🛒 Корзина
                </Link>
              )}
              <button onClick={() => setOpen(false)} aria-label="Закрыть чат" className="text-2xl leading-none">
                ×
              </button>
            </div>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <div className="space-y-3 text-sm text-zinc-600">
                <p>
                  Здравствуйте! Подскажу наличие и характеристики товара, подберу аналог и помогу
                  добавить товар в корзину. Спросите, например:
                </p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-full border border-blue-200 bg-white px-3 py-1 text-blue-800 hover:bg-blue-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) =>
              m.role === "user" ? (
                <p
                  key={m.id}
                  className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-blue-700 px-3 py-2 text-sm whitespace-pre-line text-white"
                >
                  {m.text}
                </p>
              ) : (
                <div key={m.id} className="space-y-2">
                  <p className="w-fit max-w-[90%] rounded-2xl rounded-bl-sm bg-white px-3 py-2 text-sm whitespace-pre-line shadow-sm">
                    {m.text}
                  </p>
                  {m.data?.products.map((p) => <ProductCard key={p.id} product={p} />)}
                  {m.data && m.data.analogs.length > 0 && (
                    <p className="text-xs font-medium tracking-wide text-zinc-500 uppercase">Аналоги</p>
                  )}
                  {m.data?.analogs.map((a) => <ProductCard key={a.id} product={a} />)}
                  {m.data?.pending && (
                    <ConfirmCard
                      pending={m.data.pending}
                      status={pendingStatus[m.data.pending.pending_id] ?? "open"}
                      onConfirm={() => resolvePending(m.data!.pending!.pending_id, true)}
                      onReject={() => resolvePending(m.data!.pending!.pending_id, false)}
                    />
                  )}
                  {m.data?.cart_url && !m.data.pending && (
                    <Link href={m.data.cart_url} className="inline-block text-sm text-blue-700 underline">
                      Перейти в корзину →
                    </Link>
                  )}
                </div>
              ),
            )}

            {loading && <p className="text-sm text-zinc-500">Консультант печатает…</p>}
            {failed && (
              <div className="flex items-center gap-3 text-sm text-red-700">
                <span>Не удалось получить ответ.</span>
                <button onClick={() => send(failed, true)} className="underline">
                  Повторить
                </button>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2 border-t border-zinc-200 bg-white p-3 sm:rounded-b-xl"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Артикул, название или вопрос…"
              maxLength={2000}
              className="min-w-0 flex-1 rounded-md border border-zinc-300 px-3 py-2 text-base sm:text-sm"
            />
            <button
              disabled={loading || !input.trim()}
              className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800 disabled:opacity-50"
            >
              →
            </button>
          </form>
        </section>
      )}
    </>
  );
}
