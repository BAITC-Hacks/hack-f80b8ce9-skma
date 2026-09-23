import Image from "next/image";

import { AssistantBanner } from "@/app/_components/assistant-banner";
import { ChatWidget } from "@/app/_components/chat-widget";

const STEPS = [
  {
    title: "Откройте чат",
    image: "/guide/01-start.png",
    alt: "Стартовый экран чата с примерами вопросов",
    body: "Нажмите «Запустить ИИ-ассистента» в баннере или кнопку «Консультант» в правом нижнем углу. Ассистент поздоровается и предложит готовые вопросы: наличие по артикулу, поиск по названию и условия покупки. Скрепка внизу чата принимает спецификацию .csv, .xlsx или .docx — наличие проверяется по каждой строке.",
  },
  {
    title: "Узнайте наличие и характеристики",
    image: "/guide/02-stock.png",
    alt: "Ответ с карточкой автомата Legrand в наличии",
    body: "Напишите артикул или название, например «Есть в наличии 200300285_?». В ответе будет карточка: цена в тенге, общий остаток, склады, тип, номинал и ссылка на товар на ekt.kz. Если сертификата в базе нет, карточка скажет об этом прямо.",
  },
  {
    title: "Подберите аналог",
    image: "/guide/03-analogs.png",
    alt: "Товар отсутствует, ниже список аналогов в наличии",
    body: "Если остаток нулевой, ассистент так и напишет и предложит аналоги в наличии из той же серии. У каждого аналога есть пояснение, какие характеристики совпали. Аналог — подсказка, а не гарантия полной замены: перед заказом сверьте параметры.",
  },
  {
    title: "Спросите про доставку и оплату",
    image: "/guide/04-terms.png",
    alt: "Ответ об условиях доставки и оплаты",
    body: "Вопрос «Какие условия доставки и оплаты?» возвращает условия из справочника магазина: бесплатная доставка по Алматы свыше 15 000 ₸, пороги по городам, оплата для физлиц и юрлиц, срок доставки после согласования с менеджером.",
  },
  {
    title: "Добавьте товар в корзину",
    image: "/guide/05-cart.png",
    alt: "Предложение добавить две штуки с кнопками подтверждения",
    body: "Напишите «добавь 2 шт» после карточки нужного товара. Появится предложение с суммой и кнопками «Да, добавить» и «Нет». Позиция попадает в корзину только после подтверждения. Затем откройте «Корзину» в шапке чата и проверьте количество и итог. Если запросить больше, чем есть на складе, количество ограничится остатком.",
  },
] as const;

export default function Home() {
  return (
    <>
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <p className="text-xl font-bold text-blue-800">Электрокомплект</p>
          <p className="text-sm text-zinc-500">+7 (727) 346-88-88</p>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-10 px-4 py-10 pb-28">
        <AssistantBanner />
        <section className="space-y-8">
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold">Как пользоваться ИИ-ассистентом</h2>
            <p className="max-w-2xl text-zinc-600">
              Пять шагов: от первого вопроса до корзины. Скриншоты сняты с рабочего чата.
            </p>
          </div>
          <ol className="space-y-10">
            {STEPS.map((step, index) => (
              <li key={step.title} className="space-y-4 border-t border-zinc-200 pt-8">
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold">
                    {index + 1}. {step.title}
                  </h3>
                  <p className="max-w-2xl text-zinc-600">{step.body}</p>
                </div>
                <Image
                  src={step.image}
                  alt={step.alt}
                  width={420}
                  height={640}
                  className="mx-auto w-full max-w-sm rounded-xl border border-zinc-200 shadow-md"
                />
              </li>
            ))}
          </ol>
        </section>
      </main>
      <ChatWidget />
    </>
  );
}
