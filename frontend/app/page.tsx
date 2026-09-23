import { ChatWidget } from "@/app/_components/chat-widget";

const CATEGORIES = [
  "Низковольтная аппаратура",
  "Светотехника",
  "Кабельно-проводниковая продукция",
  "Электроустановочные изделия",
  "Щитовое оборудование",
  "Автоматизация",
];

export default function Home() {
  return (
    <>
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <p className="text-xl font-bold text-blue-800">Электрокомплект</p>
          <p className="text-sm text-zinc-500">+7 (727) 346-88-88</p>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-10 px-4 py-10">
        <section className="space-y-3">
          <h1 className="text-3xl font-semibold sm:text-4xl">Электротехническая продукция</h1>
          <p className="max-w-2xl text-zinc-600">
            Прототип ИИ-консультанта для ekt.kz: спросите о наличии и характеристиках товара,
            подберите аналог, узнайте условия покупки и добавьте товар в корзину прямо из чата.
          </p>
        </section>
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {CATEGORIES.map((name) => (
            <div
              key={name}
              className="rounded-lg border border-zinc-200 bg-white px-4 py-6 text-sm font-medium"
            >
              {name}
            </div>
          ))}
        </section>
      </main>
      <ChatWidget />
    </>
  );
}
