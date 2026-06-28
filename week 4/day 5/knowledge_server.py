"""
MCP-сервер №2 — База знаний. Поиск документов и их суммаризация.
Самодостаточен: корпус и суммаризатор внутри.
"""

import re
from collections import Counter

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("knowledge-server")

_DOCS = [
    {"id": "kb1", "title": "Лицензирование",
     "text": "Лицензии продаются пакетами по 10 рабочих мест. При расширении "
             "действует прогрессивная скидка: от 50 мест — 10%, от 100 — 20%. "
             "Лицензия активируется в течение суток после оплаты."},
    {"id": "kb2", "title": "Модуль аналитики",
     "text": "Модуль аналитики подключается отдельной лицензией. Требует "
             "тариф gold. Включает дашборды, экспорт отчётов и API доступ."},
    {"id": "kb3", "title": "Поддержка gold",
     "text": "Клиенты тарифа gold получают приоритетную поддержку 24/7 и "
             "персонального менеджера. SLA на ответ — 1 час."},
    {"id": "kb4", "title": "Оплата и счета",
     "text": "Счета выставляются помесячно. Возможна оплата по договору. "
             "Закрывающие документы приходят в течение 5 рабочих дней."},
]
_STOP = {"и", "в", "по", "на", "с", "для", "от", "до", "за", "из", "the", "a", "of"}


@mcp.tool()
def search_docs(query: str, limit: int = 3) -> list[dict]:
    """Найти документы в базе знаний по запросу. Возвращает {id, title, text}."""
    q = set(re.findall(r"\w+", query.lower()))
    scored = []
    for d in _DOCS:
        words = set(re.findall(r"\w+", (d["title"] + " " + d["text"]).lower()))
        score = len(q & words)
        if score:
            scored.append({**d, "score": score})
    scored.sort(key=lambda d: d["score"], reverse=True)
    return scored[:limit]


@mcp.tool()
def summarize(text: str, max_sentences: int = 2) -> dict:
    """Сжать текст: краткое содержание + ключевые слова."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    words = re.findall(r"\w+", text.lower())
    keywords = [w for w, _ in Counter(
        w for w in words if w not in _STOP and len(w) > 3).most_common(5)]
    return {"summary": " ".join(sents[:max_sentences]),
            "keywords": keywords, "sentence_count": len(sents)}


if __name__ == "__main__":
    mcp.run()
