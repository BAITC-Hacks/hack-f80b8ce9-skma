"""LangGraph chat graph for the ekt.kz assistant.

    START → guard ─┬─ confirm ──────────────▶ END   "да" to the open add-to-cart proposal
                   ├─ reject ───────────────▶ END   "нет" to it
                   └─ agent ⇄ tools ────────▶ END   LLM with catalog/cart tools

The guard runs in code, not in the LLM: only a short explicit "да" to the latest proposal
changes the cart. The LLM itself can only *propose* an addition (propose_add_to_cart).
Chat history is kept by the checkpointer per thread (= chat session_id).
"""

from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

SYSTEM_PROMPT = """Ты — консультант интернет-магазина электротехники ekt.kz (ТОО «Электрокомплект»).
Отвечай на языке клиента (русский или казахский), коротко и по делу: 1–4 предложения.

Правила:
- Цены, остатки, характеристики и условия называй ТОЛЬКО из результатов инструментов.
  Если данных нет — так и скажи. Никогда не выдумывай числа, артикулы и сроки.
- Товар ищи через search_products; если клиент назвал артикул или код — тоже через него.
  Подробности (склады, характеристики) — get_product.
- Если товара нет в наличии (stock = 0), сразу вызови find_analogs и объясни, почему
  предложен лучший аналог (поле reason).
- Сертификатов в базе пока нет: если спрашивают, так и скажи и предложи уточнить у менеджера.
- Оплата, доставка, минимальная партия, возврат, контакты — get_purchase_terms. Кратность
  товара (min_qty) есть в данных товара.
- Добавить в корзину ты можешь только ПРЕДЛОЖИТЬ через propose_add_to_cart (количество
  ограничится остатком). Корзина меняется, только когда клиент нажмёт «Да, добавить» или
  ответит «да». Никогда не говори, что товар уже добавлен.
- Не запрашивай платёжные и личные данные.
- Клиент видит карточки товаров под твоим ответом: не перечисляй все характеристики,
  не вставляй ссылки и таблицы."""

# Keep the last N messages of the thread (starting on a human turn, so tool calls stay paired).
HISTORY_MESSAGES = 30
RECURSION_LIMIT = 14  # about 6 agent ⇄ tools rounds


class ChatState(MessagesState):
    route: str


Guard = Callable[[str], Awaitable[Literal["confirm", "reject", "agent"]]]
Action = Callable[[], Awaitable[str]]


def build_chat_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    *,
    guard: Guard,
    confirm: Action,
    reject: Action,
    checkpointer: BaseCheckpointSaver,
    context: str = "",
) -> CompiledStateGraph:
    model = llm.bind_tools(tools)
    system = SystemMessage(SYSTEM_PROMPT + context)

    async def guard_node(state: ChatState) -> dict:
        last = state["messages"][-1]
        text = last.content if isinstance(last, HumanMessage) else ""
        return {"route": await guard(str(text))}

    async def confirm_node(state: ChatState) -> dict:
        return {"messages": [AIMessage(await confirm())]}

    async def reject_node(state: ChatState) -> dict:
        return {"messages": [AIMessage(await reject())]}

    async def agent_node(state: ChatState) -> dict:
        history: list[AnyMessage] = trim_messages(
            state["messages"],
            max_tokens=HISTORY_MESSAGES,
            token_counter=len,
            strategy="last",
            start_on="human",
        )
        return {"messages": [await model.ainvoke([system, *history])]}

    graph = StateGraph(ChatState)
    graph.add_node("guard", guard_node)
    graph.add_node("confirm", confirm_node)
    graph.add_node("reject", reject_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", lambda s: s["route"], ["confirm", "reject", "agent"])
    graph.add_edge("confirm", END)
    graph.add_edge("reject", END)
    graph.add_conditional_edges("agent", tools_condition, ["tools", END])
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)


async def run_chat_graph(graph: CompiledStateGraph, thread_id: str, message: str) -> str:
    result = await graph.ainvoke(
        {"messages": [HumanMessage(message)]},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT},
    )
    last = result["messages"][-1]
    text = last.text if isinstance(last, AIMessage) else ""
    return text.strip() or "Уточните, пожалуйста, запрос."
