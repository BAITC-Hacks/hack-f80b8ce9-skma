"""Check that the configured LLM calls tools, answers in Russian and is fast enough.

Usage: .venv/bin/python -m scripts.llm_smoke
"""

import asyncio
import time

from app.core.config import settings
from app.services.assistant_service import TOOLS, get_llm_client


async def main() -> None:
    client = get_llm_client()
    if client is None:
        print("OPENAI_API_KEY is empty: the chat runs in rule-based mode")
        return
    started = time.monotonic()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": "Есть в наличии автомат Legrand DRX250 160А?"}],
        tools=TOOLS,
        tool_choice="auto",
    )
    msg = response.choices[0].message
    print(f"model={settings.openai_model} time={time.monotonic() - started:.1f}s")
    print("tool_calls:", [(c.function.name, c.function.arguments) for c in msg.tool_calls or []])
    print("content:", msg.content)


if __name__ == "__main__":
    asyncio.run(main())
