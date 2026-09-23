import { formatPrice, type Analog, type ProductCard as Product } from "@/lib/api";

export function ProductCard({ product }: { product: Product | Analog }) {
  const specs = Object.entries(product.specs)
    .filter(([key]) => key !== "Артикул производителя")
    .slice(0, 4);
  const stores = Object.entries(product.stores).slice(0, 3);
  const reason = "reason" in product ? product.reason : null;

  return (
    <article className="space-y-2 rounded-lg border border-zinc-200 bg-white p-3 text-sm shadow-sm">
      <div className="flex gap-3">
        {product.image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image}
            alt=""
            className="h-14 w-14 shrink-0 rounded object-contain"
            loading="lazy"
          />
        )}
        <div className="min-w-0 space-y-0.5">
          <p className="font-medium leading-snug">{product.name}</p>
          <p className="text-xs text-zinc-500">Артикул: {product.article}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold">{formatPrice(product.price)}</span>
        {product.in_stock ? (
          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-700">
            В наличии: {product.stock} шт.
          </span>
        ) : (
          <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs font-medium text-red-700">
            Нет в наличии
          </span>
        )}
        {product.min_qty > 1 && (
          <span className="text-xs text-zinc-500">Кратность: {product.min_qty}</span>
        )}
      </div>

      {stores.length > 0 && (
        <p className="text-xs text-zinc-500">
          {stores.map(([name, qty]) => `${name}: ${qty}`).join(" · ")}
        </p>
      )}

      {specs.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs">
          {specs.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-zinc-500">{key}</dt>
              <dd className="truncate">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {reason && (
        <p className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">
          <span className="font-medium">Почему этот аналог: </span>
          {reason}
        </p>
      )}

      <div className="flex gap-3 text-xs">
        {product.certificate_url ? (
          <a href={product.certificate_url} target="_blank" className="text-blue-700 underline">
            Сертификат
          </a>
        ) : (
          <span className="text-zinc-400">Сертификата в базе нет</span>
        )}
        {product.url && (
          <a href={product.url} target="_blank" className="text-blue-700 underline">
            На сайте ekt.kz
          </a>
        )}
      </div>
    </article>
  );
}
