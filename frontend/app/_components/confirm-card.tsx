import { formatPrice, type PendingAdd } from "@/lib/api";

export type PendingStatus = "open" | "busy" | "confirmed" | "rejected";

export function ConfirmCard({
  pending,
  status,
  onConfirm,
  onReject,
}: {
  pending: PendingAdd;
  status: PendingStatus;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const clamped = pending.qty < pending.requested_qty;
  const sum = pending.price === null ? null : pending.price * pending.qty;

  return (
    <div className="space-y-2 rounded-lg border-2 border-blue-200 bg-blue-50 p-3 text-sm">
      <p>
        Добавить в корзину <span className="font-medium">{pending.name}</span> ×{" "}
        <span className="font-semibold">{pending.qty} шт.</span>
        {sum !== null && <> на {formatPrice(sum)}</>}?
      </p>
      {clamped && (
        <p className="text-xs text-amber-800">
          Запрошено {pending.requested_qty} шт., в наличии только {pending.max_qty} шт.
        </p>
      )}
      {status === "confirmed" && <p className="font-medium text-emerald-700">✓ Добавлено</p>}
      {status === "rejected" && <p className="text-zinc-500">Отменено, корзина не изменилась</p>}
      {(status === "open" || status === "busy") && (
        <div className="flex gap-2">
          <button
            onClick={onConfirm}
            disabled={status === "busy"}
            className="rounded-md bg-blue-700 px-3 py-1.5 font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            Да, добавить
          </button>
          <button
            onClick={onReject}
            disabled={status === "busy"}
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 hover:bg-zinc-100 disabled:opacity-50"
          >
            Нет
          </button>
        </div>
      )}
    </div>
  );
}
