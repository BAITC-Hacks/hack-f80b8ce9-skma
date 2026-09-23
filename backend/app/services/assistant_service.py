import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends
from openai import AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.schemas.cart import PendingAdd
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.product import Analog, ProductCard
from app.services.cart_service import CartError, CartService, CartServiceDep
from app.services.catalog_service import CatalogService, CatalogServiceDep
from app.services.search_service import SearchService, SearchServiceDep

logger = logging.getLogger(__name__)

TERMS_PATH = Path(__file__).resolve().parents[2] / "data" / "terms.md"
MAX_TOOL_ROUNDS = 5
HISTORY_LIMIT = 20

SYSTEM_PROMPT = """Ты — консультант интернет-магазина электротехники ekt.kz (ТОО «Электрокомплект»).
Отвечай на языке клиента (русский или казахский), коротко и по делу.

Правила:
- Цены, остатки, характеристики и условия называй ТОЛЬКО из результатов инструментов.
  Если данных нет — так и скажи. Никогда не выдумывай числа.
- Для поиска товара вызывай search_products, для подробностей — get_product.
- Если товара нет в наличии (stock = 0), сразу вызови find_analogs и объясни, почему
  предложен аналог (поле reason).
- Сертификатов в базе пока нет: если спрашивают, скажи, что сертификата в базе нет, и
  предложи уточнить у менеджера.
- Об оплате, доставке, минимальной партии — вызывай get_purchase_terms. Кратность товара
  (min_qty) есть в карточке.
- Добавить в корзину ты можешь только ПРЕДЛОЖИТЬ через propose_add_to_cart. Корзина
  меняется, только когда клиент нажмёт «Да, добавить». Не говори, что товар уже добавлен.
- Не запрашивай платёжные данные.
- Карточки товаров клиент видит под твоим ответом, не перечисляй все характеристики."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Поиск товаров по артикулу, коду производителя или названию.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Артикул или описание товара"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Карточка товара: цена, остаток по складам, характеристики.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_analogs",
            "description": "Аналоги в наличии для товара, с обоснованием.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_purchase_terms",
            "description": "Условия покупки: оплата, доставка, минимальная партия, возврат.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_add_to_cart",
            "description": (
                "Предложить клиенту добавить товар в корзину. НЕ меняет корзину: клиент "
                "должен подтвердить кнопкой. Количество ограничивается остатком."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "qty": {"type": "integer", "minimum": 1},
                },
                "required": ["product_id", "qty"],
            },
        },
    },
]

CONFIRM_WORDS = {"да", "ок", "окей", "давай", "добавь", "добавьте", "добавляй", "подтверждаю",
                 "согласен", "конечно", "иә", "ия", "yes"}  # fmt: skip
CONFIRM_FILLER = {"в", "корзину", "пожалуйста", "его", "их", "это", "так", "верно", "бери"}
REJECT_WORDS = {"нет", "отмена", "отмени", "отменить", "жоқ", "no"}
REJECT_FILLER = {"не", "надо", "нужно", "спасибо", "пока"}
TERMS_HINTS = ("оплат", "доставк", "услови", "парти", "минимальн", "самовывоз", "рассрочк",
               "возврат", "контакт", "телефон", "кратност", "төлем", "жеткіз")  # fmt: skip
ADD_HINTS = ("добав", "корзин", "положи", "беру", "закаж", "себетке", "қос")
ANALOG_HINTS = ("аналог", "замен", "похож", "вместо", "балама")


def words(text: str) -> list[str]:
    return re.findall(r"[\w-]+", text.lower().replace("ё", "е"))


def is_confirmation(text: str) -> bool:
    ws = words(text)
    return (
        0 < len(ws) <= 5
        and not any(c.isdigit() for c in text)
        and bool(set(ws) & CONFIRM_WORDS)
        and set(ws) <= CONFIRM_WORDS | CONFIRM_FILLER
    )


def is_rejection(text: str) -> bool:
    ws = words(text)
    return (
        0 < len(ws) <= 4
        and bool(set(ws) & REJECT_WORDS)
        and set(ws) <= REJECT_WORDS | REJECT_FILLER
    )


def compact(card: ProductCard) -> dict[str, Any]:
    return {
        "product_id": card.id,
        "article": card.article,
        "name": card.name,
        "price_kzt": card.price,
        "stock": card.stock,
        "min_qty": card.min_qty,
    }


def money(value: float | None) -> str:
    return f"{value:,.0f} ₸".replace(",", " ") if value is not None else "цена по запросу"


@dataclass
class Session:
    history: list[dict[str, str]] = field(default_factory=list)
    last_product_id: int | None = None


class SessionStore:
    """Chat history in process memory (per the spec, not persisted)."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, session_id: str) -> Session:
        return self._sessions.setdefault(session_id, Session())


@dataclass
class Turn:
    """What the tools returned during one reply: rendered as cards by the UI."""

    products: dict[int, ProductCard] = field(default_factory=dict)
    analogs: dict[int, Analog] = field(default_factory=dict)
    pending: PendingAdd | None = None


class AssistantService:
    def __init__(
        self,
        catalog: CatalogService,
        search: SearchService,
        carts: CartService,
        llm: AsyncOpenAI | None,
        sessions: SessionStore,
    ) -> None:
        self.catalog = catalog
        self.search = search
        self.carts = carts
        self.llm = llm
        self.sessions = sessions

    async def reply(self, data: ChatRequest) -> ChatResponse:
        cart = await self.carts.ensure(data.cart_id)
        session = self.sessions.get(data.session_id)
        turn = Turn()

        pending = await self.carts.latest_pending(cart.id)
        if pending and is_confirmation(data.message):
            text = await self._confirm(cart.id, pending.id)
        elif pending and is_rejection(data.message):
            await self.carts.reject(cart.id, pending.id)
            text = "Хорошо, не добавляю. Корзина не изменилась."
        else:
            text = await self._answer(data.message, cart.id, session, turn)

        session.history += [
            {"role": "user", "content": data.message},
            {"role": "assistant", "content": text},
        ]
        session.history = session.history[-HISTORY_LIMIT:]
        if turn.products:
            session.last_product_id = list(turn.products)[-1]

        cart_state = await self.carts.get(cart.id)
        return ChatResponse(
            reply=text,
            products=list(turn.products.values())[:5],
            analogs=list(turn.analogs.values()),
            pending=turn.pending,
            cart_id=cart.id,
            cart_url=f"/cart/{cart.id}" if cart_state and cart_state.items else None,
        )

    async def _confirm(self, cart_id: str, pending_id: str) -> str:
        try:
            cart, added = await self.carts.confirm(cart_id, pending_id)
        except CartError as exc:
            if exc.status_code == 409:
                return "К сожалению, этого товара уже нет в наличии. Корзина не изменилась."
            raise
        return f"Добавил в корзину ({added} шт.). В корзине позиций: {len(cart.items)}."

    async def _answer(self, message: str, cart_id: str, session: Session, turn: Turn) -> str:
        if self.llm is not None:
            try:
                return await self._answer_llm(message, cart_id, session, turn)
            except OpenAIError as exc:
                # Keep the demo alive: fall back to the rule-based assistant.
                logger.warning("LLM failed, using rule-based answer: %s", exc)
                turn.products.clear()
                turn.analogs.clear()
                turn.pending = None
        return await self._answer_rules(message, cart_id, session, turn)

    # --- tools ---------------------------------------------------------------------

    async def _run_tool(self, name: str, args: dict[str, Any], cart_id: str, turn: Turn) -> Any:
        if name == "search_products":
            limit = min(int(args.get("limit") or 5), 10)
            entries = self.search.search(str(args.get("query", "")), limit)
            cards = await self.catalog.get_products([e.id for e in entries])
            for card in cards[:3]:
                turn.products[card.id] = card
            return [compact(c) for c in cards] or {"result": "ничего не найдено"}
        if name == "get_product":
            card = await self.catalog.get_product(int(args["product_id"]))
            if card is None:
                return {"error": "товар не найден"}
            turn.products[card.id] = card
            return {**compact(card), "stores": card.stores, "specs": card.specs,
                    "certificate_url": card.certificate_url}  # fmt: skip
        if name == "find_analogs":
            card = await self.catalog.get_product(int(args["product_id"]))
            if card is None:
                return {"error": "товар не найден"}
            analogs = await self.search.find_analogs(card)
            for analog in analogs:
                turn.analogs[analog.id] = analog
            return [{**compact(a), "reason": a.reason} for a in analogs] or {
                "result": "аналогов в наличии не найдено"
            }
        if name == "get_purchase_terms":
            return TERMS_PATH.read_text(encoding="utf-8")
        if name == "propose_add_to_cart":
            card = await self.catalog.get_product(int(args["product_id"]), fresh=True)
            if card is None:
                return {"error": "товар не найден"}
            try:
                turn.pending = await self.carts.propose(cart_id, card, int(args.get("qty") or 1))
            except CartError as exc:
                return {"error": exc.detail}
            return {
                "status": "ожидает подтверждения клиента, корзина НЕ изменена",
                "qty": turn.pending.qty,
                "requested_qty": turn.pending.requested_qty,
                "stock": card.stock,
            }
        return {"error": f"unknown tool {name}"}

    # --- LLM mode ------------------------------------------------------------------

    async def _answer_llm(self, message: str, cart_id: str, session: Session, turn: Turn) -> str:
        assert self.llm is not None
        context = ""
        if session.last_product_id:
            context = f"\nПоследний товар в диалоге: product_id={session.last_product_id}."
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT + context},
            *session.history,
            {"role": "user", "content": message},
        ]
        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.llm.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return (msg.content or "").strip() or "Уточните, пожалуйста, запрос."
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in msg.tool_calls
                    ],
                }
            )
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    result = await self._run_tool(call.function.name, args, cart_id, turn)
                except (ValueError, KeyError, TypeError) as exc:
                    result = {"error": f"bad arguments: {exc}"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        return "Не удалось подготовить ответ, попробуйте переформулировать вопрос."

    # --- rule-based mode (no LLM key or LLM failure) ---------------------------------

    async def _answer_rules(self, message: str, cart_id: str, session: Session, turn: Turn) -> str:
        text = message.lower().replace("ё", "е")

        if any(h in text for h in TERMS_HINTS) and not any(h in text for h in ADD_HINTS):
            return self._terms_answer(text)

        entries = self.search.search(message, 3)
        product_id = entries[0].id if entries else session.last_product_id

        if any(h in text for h in ADD_HINTS):
            if product_id is None:
                return "Какой товар добавить? Напишите артикул или название."
            qty_match = re.search(r"(\d+)\s*(шт|штук|pcs|дана)", text) or re.search(
                r"(?:добав\w*|положи|беру)\s+(\d{1,5})\b", text
            )
            qty = int(qty_match.group(1)) if qty_match else 1
            result = await self._run_tool(
                "propose_add_to_cart", {"product_id": product_id, "qty": qty}, cart_id, turn
            )
            if turn.pending is None:
                return f"Не получилось предложить добавление: {result.get('error')}."
            p = turn.pending
            note = (
                f" (запрошено {p.requested_qty}, в наличии только {p.max_qty})"
                if p.qty < p.requested_qty
                else ""
            )
            return f"Добавить в корзину «{p.name}» — {p.qty} шт.{note}? Подтвердите кнопкой ниже."

        if any(h in text for h in ANALOG_HINTS) and product_id is not None:
            card = await self.catalog.get_product(product_id)
            if card:
                turn.products[card.id] = card
                return await self._analogs_answer(card, turn)

        if not entries:
            return (
                "Не нашёл такой товар в каталоге. Уточните артикул или название, например: "
                "«автомат Legrand 3P 160А»."
            )

        exact = self.search.exact(message) or (entries[0] if len(entries) == 1 else None)
        if exact:
            card = await self.catalog.get_product(exact.id)
            if card is None:
                return "Товар найден в каталоге, но карточка сейчас недоступна."
            turn.products[card.id] = card
            if not card.in_stock:
                return await self._analogs_answer(card, turn)
            stores = ", ".join(f"{k} — {v}" for k, v in list(card.stores.items())[:4])
            cert = "Сертификата в базе нет — уточните у менеджера."
            return (
                f"«{card.name}» в наличии: {card.stock} шт. ({stores}). Цена {money(card.price)}. "
                f"{cert} Добавить в корзину? Напишите, например: «добавь 2 шт»."
            )

        cards = await self.catalog.get_products([e.id for e in entries])
        for card in cards:
            turn.products[card.id] = card
        return (
            f"Нашёл {len(cards)} подходящих товара — смотрите карточки ниже. Какой вас интересует?"
        )

    async def _analogs_answer(self, card: ProductCard, turn: Turn) -> str:
        analogs = await self.search.find_analogs(card)
        for analog in analogs:
            turn.analogs[analog.id] = analog
        head = (
            f"«{card.name}» сейчас нет в наличии."
            if not card.in_stock
            else f"Аналоги для «{card.name}»:"
        )
        if not analogs:
            return head + " Аналогов в наличии не нашёл — могу передать запрос менеджеру."
        best = analogs[0]
        return (
            f"{head} Подобрал аналоги в наличии ({len(analogs)}), лучший — «{best.name}», "
            f"{money(best.price)}. Почему именно он: {best.reason.rstrip('.')}. "
            "Остальные варианты и объяснения — в карточках ниже."
        )

    @staticmethod
    def _terms_answer(text: str) -> str:
        sections = TERMS_PATH.read_text(encoding="utf-8").split("\n## ")[1:]
        keys = {
            "Оплата": ("оплат", "рассрочк", "төлем"),
            "Доставка": ("доставк", "самовывоз", "жеткіз"),
            "Минимальная партия": ("парти", "минимальн", "кратност"),
            "Возврат и обмен": ("возврат", "обмен"),
            "Контакты": ("контакт", "телефон"),
        }
        chosen = [
            s for s in sections if any(h in text for h in keys.get(s.split("\n", 1)[0].strip(), ()))
        ]
        return "\n\n".join(chosen or sections[1:4]).strip()


@lru_cache
def get_llm_client() -> AsyncOpenAI | None:
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=1,
    )


session_store = SessionStore()


def get_session_store() -> SessionStore:
    return session_store


def get_assistant_service(
    catalog: CatalogServiceDep,
    search: SearchServiceDep,
    carts: CartServiceDep,
    llm: Annotated[AsyncOpenAI | None, Depends(get_llm_client)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
) -> AssistantService:
    return AssistantService(catalog, search, carts, llm, sessions)


AssistantServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]
