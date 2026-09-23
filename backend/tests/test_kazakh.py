import httpx
import openai

from app.main import app
from app.services.assistant_service import get_kazakh_llm_client
from app.services.kazakh_service import is_kazakh
from tests.test_chat import FakeLLM, chat, llm_message, use_llm


def use_kazakh_llm(fake):
    app.dependency_overrides[get_kazakh_llm_client] = lambda: fake


def test_is_kazakh():
    assert is_kazakh("Бұл автомат қоймада бар ма?")
    assert not is_kazakh("Есть в наличии 200300290?")


def test_kazakh_question_reply_is_rewritten(client):
    use_llm(FakeLLM(llm_message("Есть 19 шт., цена 12 500 ₸.")))
    kazakh = FakeLLM(llm_message("Қоймада 19 дана бар, бағасы 12 500 ₸."))
    use_kazakh_llm(kazakh)
    body = chat(client, "Бұл автомат қоймада бар ма?")
    assert body["reply"] == "Қоймада 19 дана бар, бағасы 12 500 ₸."
    assert "Есть 19 шт." in kazakh.requests[0][-1].content


def test_russian_question_skips_kazakh_llm(client):
    use_llm(FakeLLM(llm_message("Есть 19 шт.")))
    kazakh = FakeLLM()
    use_kazakh_llm(kazakh)
    assert chat(client, "Есть в наличии?")["reply"] == "Есть 19 шт."
    assert kazakh.requests == []


def test_rules_mode_reply_is_rewritten(client):
    kazakh_reply = (
        "027230 DRX250 3ф 160А 25ka (1): Алматыда 19 дана, бағасы 71 000 ₸. Мысалы: «2 дана қос»."
    )
    use_kazakh_llm(FakeLLM(llm_message(kazakh_reply)))
    body = chat(client, "200300290 қоймада бар ма?")
    assert body["products"][0]["id"] == 2
    assert body["reply"] == kazakh_reply


def test_changed_numbers_keep_original(client):
    use_llm(FakeLLM(llm_message("Есть 19 шт.")))
    use_kazakh_llm(FakeLLM(llm_message("Қоймада 20 дана бар.")))
    assert chat(client, "Қоймада бар ма?")["reply"] == "Есть 19 шт."


def test_kazakh_llm_error_keeps_original(client):
    use_llm(FakeLLM(llm_message("Есть 19 шт.")))
    error = openai.APIConnectionError(request=httpx.Request("POST", "http://brev"))
    use_kazakh_llm(FakeLLM(error=error))
    assert chat(client, "Қоймада бар ма?")["reply"] == "Есть 19 шт."
