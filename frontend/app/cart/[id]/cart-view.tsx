"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChatWidget } from "@/app/_components/chat-widget";
import { api, ApiError, formatPrice, type Cart } from "@/lib/api";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; cart: Cart };

export function CartView({ cartId }: { cartId: string }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    api
      .getCart(cartId)
      .then((cart) => active && setState({ status: "ready", cart }))
      .catch((error: unknown) => {
        if (!active) return;
        const message =
          error instanceof ApiError && error.status === 404
            ? "Корзина не найдена. Возможно, ссылка устарела."
            : "Не удалось загрузить корзину.";
        setState({ status: "error", message });
      });
    return () => {
      active = false;
    };
  }, [cartId, reload]);

  return (
    <>
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Корзина</h1>
        <Link href="/" className="text-sm text-blue-700 underline">
          ← На главную
        </Link>
      </header>

      {state.status === "loading" && <p className="text-zinc-500">Загружаем корзину…</p>}

      {state.status === "error" && (
        <div className="space-y-2">
          <p className="text-red-700">{state.message}</p>
          <button
            onClick={() => {
              setState({ status: "loading" });
              setReload((n) => n + 1);
            }}
            className="text-sm underline"
          >
            Повторить
          </button>
        </div>
      )}

      {state.status === "ready" && state.cart.items.length === 0 && (
        <p className="text-zinc-600">Корзина пуста. Спросите консультанта о товаре.</p>
      )}

      {state.status === "ready" && state.cart.items.length > 0 && (
        <section className="space-y-4">
          <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white">
            {state.cart.items.map((item) => (
              <li
                key={item.product_id}
                className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="font-medium">{item.name}</p>
                  <p className="text-xs text-zinc-500">Артикул: {item.article}</p>
                </div>
                <div className="flex shrink-0 gap-4 text-sm sm:text-right">
                  <span>
                    {item.qty} шт. × {formatPrice(item.price)}
                  </span>
                  <span className="font-semibold">
                    {formatPrice(item.price === null ? null : item.price * item.qty)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-lg">
              Итого: <span className="font-semibold">{formatPrice(state.cart.total)}</span>
            </p>
            <a
              href="https://ekt.kz/"
              target="_blank"
              className="rounded-md bg-blue-700 px-5 py-2.5 text-center font-medium text-white hover:bg-blue-800"
            >
              Оформить заказ на ekt.kz
            </a>
          </div>
          <p className="text-xs text-zinc-500">
            Прототип: оформление заказа выполняется на сайте ekt.kz. Цены и остатки проверены при
            добавлении в корзину.
          </p>
        </section>
      )}

      <ChatWidget />
    </>
  );
}
