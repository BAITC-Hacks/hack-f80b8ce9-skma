"""Hybrid mode: the main LLM (Qwen) answers and calls tools; a Kazakh model rewrites the
final reply into good Kazakh when the client writes in Kazakh.

The Kazakh model (Sherkala-8B on Brev via vLLM) has no tool calling, so it never sees the
catalog: it only rewrites finished text. If it drops or changes a number, the original is kept.
"""

import logging
import re

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from openai import OpenAIError

logger = logging.getLogger(__name__)

# Letters that Kazakh Cyrillic has and Russian does not.
KAZAKH_LETTERS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")

REWRITE_PROMPT = """Сен ekt.kz электр тауарлары дүкенінің кеңесшісісің.
Кеңесшінің жауабын сауатты, табиғи қазақ тілінде қайта жаз.
Ережелер:
- Барлық сандарды, бағаларды, артикулдарды, тауар атауларын және брендтерді өзгертпе.
- Жаңа ақпарат қоспа, ештеңені алып тастама.
- Тек жауап мәтінін қайтар, түсініктемесіз."""


def is_kazakh(text: str) -> bool:
    return any(c in KAZAKH_LETTERS for c in text)


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


async def rewrite_in_kazakh(llm: BaseChatModel, question: str, answer: str) -> str:
    """Kazakh version of `answer`, or `answer` itself if the model fails or changes numbers."""
    try:
        result = await llm.ainvoke(
            [
                SystemMessage(REWRITE_PROMPT),
                HumanMessage(f"Клиенттің сұрағы:\n{question}\n\nКеңесшінің жауабы:\n{answer}"),
            ]
        )
    except (OpenAIError, httpx.HTTPError) as exc:
        logger.warning("Kazakh LLM failed, keeping the original reply: %s", exc)
        return answer
    text = result.text.strip()
    if not text or numbers(text) != numbers(answer):
        logger.warning("Kazakh LLM changed numbers or returned nothing, keeping the original")
        return answer
    return text
