import { formatPrice, type SpecLine, type SpecStatus } from "@/lib/api";

const STATUS: Record<SpecStatus, { label: string; className: string }> = {
  in_stock: { label: "В наличии", className: "bg-emerald-50 text-emerald-700" },
  partial: { label: "Частично", className: "bg-amber-50 text-amber-800" },
  out_of_stock: { label: "Нет в наличии", className: "bg-red-50 text-red-700" },
  not_found: { label: "Не найдено", className: "bg-zinc-100 text-zinc-600" },
};

export function SpecTable({ lines, skipped }: { lines: SpecLine[]; skipped: number }) {
  return (
    <div className="space-y-2">
      <ol className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 bg-white text-sm">
        {lines.map((line) => {
          const status = STATUS[line.status];
          const product = line.product;
          return (
            <li key={line.row} className="space-y-1 px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs text-zinc-500">
                    Строка {line.row}: {line.query}
                  </p>
                  {product ? (
                    <p className="leading-snug font-medium">{product.name}</p>
                  ) : (
                    <p className="text-zinc-500">Нет такого товара в каталоге</p>
                  )}
                </div>
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${status.className}`}
                >
                  {status.label}
                </span>
              </div>
              {product && (
                <p className="text-xs text-zinc-600">
                  Арт. {product.article} · нужно {line.requested_qty} шт. · в наличии{" "}
                  {product.stock} шт. · {formatPrice(product.price)}
                </p>
              )}
              {line.analog && (
                <div className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">
                  <p>
                    <span className="font-medium">Аналог:</span> {line.analog.name} (арт.{" "}
                    {line.analog.article}, {formatPrice(line.analog.price)}, в наличии{" "}
                    {line.analog.stock} шт.)
                  </p>
                  <p className="text-amber-800">Почему: {line.analog.reason}</p>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {skipped > 0 && (
        <p className="text-xs text-zinc-500">Пропущено строк сверх лимита: {skipped}</p>
      )}
    </div>
  );
}
