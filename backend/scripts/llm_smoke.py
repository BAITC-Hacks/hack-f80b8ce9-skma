"""Run the real LangGraph assistant (real catalog tools, real LLM) on demo questions and
print answers, tool calls and timing. Compare models by passing several names.

Usage: .venv/bin/python -m scripts.llm_smoke [model ...]   (or `make llm-smoke MODELS="a b"`)
Cart tools are not exercised here: the cart needs the database.
"""

import asyncio
import sys
import time
import uuid

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from app.core.config import settings
from app.services.agent_graph import build_chat_graph, run_chat_graph
from app.services.assistant_service import AssistantService, SessionStore, Turn
from app.services.catalog_service import catalog_service
from app.services.search_service import SearchService

QUESTIONS = [
    "Есть в наличии 200300285_?",
    "А есть что-то похожее на 150100218_? Его нет в наличии",
    "Какие условия доставки по Алматы и минимальная партия?",
    "Нужен диф автомат 16А 30мА",
]


async def no_route(_: str) -> str:
    return "agent"


async def unused() -> str:
    raise RuntimeError("cart actions are not part of the smoke test")


async def check(model: str) -> None:
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is empty: the chat runs in rule-based mode")
        return
    llm = ChatOpenAI(
        model=model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        **({"reasoning_effort": settings.openai_reasoning_effort}
           if settings.openai_reasoning_effort else {}),
    )  # fmt: skip
    service = AssistantService(
        catalog_service, SearchService(catalog_service), None, llm, SessionStore(), InMemorySaver()
    )  # type: ignore[arg-type]
    print(f"\n=== {model} ===")
    for question in QUESTIONS:
        turn = Turn()
        saver = InMemorySaver()
        graph = build_chat_graph(
            llm, service._tools("smoke", turn), guard=no_route, confirm=unused, reject=unused,
            checkpointer=saver,
        )  # fmt: skip
        thread = str(uuid.uuid4())
        started = time.monotonic()
        answer = await run_chat_graph(graph, thread, question)
        elapsed = time.monotonic() - started
        state = await graph.aget_state({"configurable": {"thread_id": thread}})
        calls = [
            f"{c['name']}({', '.join(f'{k}={v}' for k, v in c['args'].items())})"
            for m in state.values["messages"]
            if isinstance(m, AIMessage)
            for c in m.tool_calls
        ]
        print(f"\n> {question}\n  {elapsed:.1f}s  tools: {'; '.join(calls) or '—'}")
        print("  " + answer.replace("\n", "\n  "))


async def main(models: list[str]) -> None:
    for model in models:
        await check(model)
    await catalog_service.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or [settings.openai_model]))
