import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import Depends
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from openai import OpenAIError

from app.core.config import settings
from app.schemas.cart import PendingAdd
from app.schemas.chat import ChatRequest, ChatResponse, SpecLine, UploadResponse
from app.schemas.product import Analog, ProductCard
from app.services.agent_graph import build_chat_graph, run_chat_graph
from app.services.attachment_service import spec_context, summarize
from app.services.cart_service import CartError, CartService, CartServiceDep
from app.services.catalog_service import CatalogService, CatalogServiceDep
from app.services.kazakh_service import is_kazakh, rewrite_in_kazakh
from app.services.search_service import SearchService, SearchServiceDep

logger = logging.getLogger(__name__)

TERMS_PATH = Path(__file__).resolve().parents[2] / "data" / "terms.md"
REJECTED_TEXT = "Хорошо, не добавляю. Корзина не изменилась."

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
    last_product_id: int | None = None
    attachment_context: str = ""  # last uploaded spec, for the LLM's next turns


class SessionStore:
    """Per-session context in process memory. LLM chat history is in the checkpointer."""

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
        llm: BaseChatModel | None,
        sessions: SessionStore,
        checkpointer: BaseCheckpointSaver,
        kazakh_llm: BaseChatModel | None = None,
    ) -> None:
        self.catalog = catalog
        self.search = search
        self.carts = carts
        self.llm = llm
        self.sessions = sessions
        self.checkpointer = checkpointer
        self.kazakh_llm = kazakh_llm

    async def reply(self, data: ChatRequest) -> ChatResponse:
        cart = await self.carts.ensure(data.cart_id)
        session = self.sessions.get(data.session_id)
        turn = Turn()

        text: str | None = None
        if self.llm is not None:
            try:
                text = await self._answer_llm(data, cart.id, session, turn)
            except (OpenAIError, GraphRecursionError, httpx.HTTPError) as exc:
                # Keep the demo alive: answer with rules. A failed run can leave unanswered
                # tool calls in the thread, so the LLM history starts over.
                logger.warning("LLM failed, using rule-based answer: %s", exc)
                await self.checkpointer.adelete_thread(data.session_id)
                turn = Turn()
        if text is None:
            text = await self._answer_without_llm(data.message, cart.id, session, turn)
        if self.kazakh_llm is not None and is_kazakh(data.message):
            text = await rewrite_in_kazakh(self.kazakh_llm, data.message, text)

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

    async def attach(
        self,
        session_id: str,
        cart_id: str | None,
        filename: str,
        lines: list[SpecLine],
        skipped: int,
    ) -> UploadResponse:
        """Answer for an uploaded spec; its rows stay in the session for follow-up questions."""
        cart = await self.carts.ensure(cart_id)
        session = self.sessions.get(session_id)
        session.attachment_context = spec_context(filename, lines)
        cart_state = await self.carts.get(cart.id)
        return UploadResponse(
            reply=summarize(filename, lines, skipped),
            cart_id=cart.id,
            cart_url=f"/cart/{cart.id}" if cart_state and cart_state.items else None,
            filename=filename,
            spec=lines,
            skipped_rows=skipped,
        )

    async def _confirm(self, cart_id: str, pending_id: str) -> str:
        try:
            cart, added = await self.carts.confirm(cart_id, pending_id)
        except CartError as exc:
            if exc.status_code == 409:
                return "К сожалению, этого товара уже нет в наличии. Корзина не изменилась."
            raise
        return f"Добавил в корзину ({added} шт.). В корзине позиций: {len(cart.items)}."

    async def _answer_without_llm(
        self, message: str, cart_id: str, session: Session, turn: Turn
    ) -> str:
        pending = await self.carts.latest_pending(cart_id)
        if pending and is_confirmation(message):
            return await self._confirm(cart_id, pending.id)
        if pending and is_rejection(message):
            await self.carts.reject(cart_id, pending.id)
            return REJECTED_TEXT
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

    # --- LLM mode: LangGraph (see agent_graph.py) --------------------------------------

    def _tools(self, cart_id: str, turn: Turn) -> list[BaseTool]:
        """LangChain tools bound to this request's cart; results also fill `turn` (UI cards)."""

        async def run(name: str, **args: Any) -> str:
            result = await self._run_tool(name, args, cart_id, turn)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

        @tool
        async def search_products(query: str, limit: int = 5) -> str:
            """Поиск товаров по артикулу ekt.kz (например 200300285_), коду производителя
            (027228) или описанию («автомат Legrand 3P 160А»). Возвращает product_id, цену,
            остаток (stock) и кратность (min_qty)."""
            return await run("search_products", query=query, limit=limit)

        @tool
        async def get_product(product_id: int) -> str:
            """Карточка товара: цена, остаток по складам, характеристики, сертификат."""
            return await run("get_product", product_id=product_id)

        @tool
        async def find_analogs(product_id: int) -> str:
            """Аналоги в наличии для товара, с обоснованием выбора (поле reason)."""
            return await run("find_analogs", product_id=product_id)

        @tool
        async def get_purchase_terms() -> str:
            """Условия покупки ekt.kz: оплата, доставка, минимальная партия, возврат, контакты."""
            return await run("get_purchase_terms")

        @tool
        async def propose_add_to_cart(product_id: int, qty: int) -> str:
            """Предложить клиенту добавить товар в корзину. НЕ меняет корзину: клиент
            подтверждает сам. Количество ограничивается остатком."""
            return await run("propose_add_to_cart", product_id=product_id, qty=qty)

        return [search_products, get_product, find_analogs, get_purchase_terms, propose_add_to_cart]

    async def _answer_llm(
        self, data: ChatRequest, cart_id: str, session: Session, turn: Turn
    ) -> str:
        assert self.llm is not None
        pending_ids: list[str] = []

        async def guard(text: str) -> Literal["confirm", "reject", "agent"]:
            pending = await self.carts.latest_pending(cart_id)
            if pending and is_confirmation(text):
                pending_ids.append(pending.id)
                return "confirm"
            if pending and is_rejection(text):
                pending_ids.append(pending.id)
                return "reject"
            return "agent"

        async def confirm() -> str:
            return await self._confirm(cart_id, pending_ids[-1])

        async def reject() -> str:
            await self.carts.reject(cart_id, pending_ids[-1])
            return REJECTED_TEXT

        context = session.attachment_context
        if session.attachment_context:
            context += (
                "\nПозиции из спецификации добавляй в корзину по одной через "
                "propose_add_to_cart: одновременно открыто только одно предложение."
            )
        if session.last_product_id:
            context += f"\n\nПоследний показанный товар: product_id={session.last_product_id}."
        graph = build_chat_graph(
            self.llm,
            self._tools(cart_id, turn),
            guard=guard,
            confirm=confirm,
            reject=reject,
            checkpointer=self.checkpointer,
            context=context,
        )
        return await run_chat_graph(graph, data.session_id, data.message)

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
def get_llm_client() -> BaseChatModel | None:
    """Any OpenAI-compatible chat API (OpenAI, build.nvidia.com, own NIM). None = rules only."""
    if not settings.openai_api_key:
        return None
    extra: dict[str, Any] = {}
    if settings.openai_reasoning_effort:
        extra["reasoning_effort"] = settings.openai_reasoning_effort
    return ChatOpenAI(
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=1,
        **extra,
    )


@lru_cache
def get_kazakh_llm_client() -> BaseChatModel | None:
    """Kazakh model for the hybrid mode (OpenAI-compatible vLLM on Brev). None = off."""
    if not settings.kazakh_llm_base_url:
        return None
    return ChatOpenAI(
        model=settings.kazakh_llm_model,
        base_url=settings.kazakh_llm_base_url,
        api_key=settings.kazakh_llm_api_key,
        timeout=settings.kazakh_llm_timeout_seconds,
        max_retries=0,
        temperature=0.2,
    )


session_store = SessionStore()
checkpointer = InMemorySaver()


def get_session_store() -> SessionStore:
    return session_store


def get_checkpointer() -> BaseCheckpointSaver:
    return checkpointer


def get_assistant_service(
    catalog: CatalogServiceDep,
    search: SearchServiceDep,
    carts: CartServiceDep,
    llm: Annotated[BaseChatModel | None, Depends(get_llm_client)],
    sessions: Annotated[SessionStore, Depends(get_session_store)],
    saver: Annotated[BaseCheckpointSaver, Depends(get_checkpointer)],
    kazakh_llm: Annotated[BaseChatModel | None, Depends(get_kazakh_llm_client)],
) -> AssistantService:
    return AssistantService(catalog, search, carts, llm, sessions, saver, kazakh_llm)


AssistantServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]
