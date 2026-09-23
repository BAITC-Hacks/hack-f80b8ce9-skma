"use client";

export function AssistantBanner() {
  return (
    <section className="rounded-2xl bg-blue-800 px-6 py-14 text-center text-white shadow-lg">
      <p className="text-sm font-medium tracking-wide text-blue-100">Электрокомплект · ekt.kz</p>
      <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">ИИ-ассистент</h1>
      <p className="mx-auto mt-3 max-w-xl text-blue-100">
        Наличие, характеристики, аналоги и корзина — в одном чате на сайте.
      </p>
      <button
        type="button"
        onClick={() => window.dispatchEvent(new Event("ekt-open-assistant"))}
        className="mt-8 inline-flex items-center justify-center rounded-full bg-white px-8 py-3 text-lg font-semibold text-blue-800 shadow hover:bg-blue-50"
      >
        Запустить ИИ-ассистента
      </button>
    </section>
  );
}
