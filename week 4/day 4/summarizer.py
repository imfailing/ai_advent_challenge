"""
Детерминированный суммаризатор для инструмента summarize.

Без LLM — чтобы MCP-сервер был самодостаточным. Делает экстрактивную сводку:
первые N предложений + статистика + топ ключевых слов. Этого достаточно,
чтобы продемонстрировать «обработку» данных в середине пайплайна.
"""

import re
from collections import Counter

_STOP = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "о", "из",
    "ему", "для", "или", "быть", "уже", "их", "это", "этот", "эта", "эти",
    "the", "a", "an", "of", "to", "and", "or", "is", "for", "in", "on",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def summarize(text: str, max_sentences: int = 3) -> dict:
    """
    Сжать текст. Возвращает:
      summary        — первые max_sentences предложений;
      sentence_count — всего предложений;
      word_count     — всего слов;
      keywords       — топ-5 значимых слов по частоте.
    """
    sentences = _sentences(text)
    words     = _words(text)
    keywords  = [w for w, _ in Counter(
        w for w in words if w not in _STOP and len(w) > 2
    ).most_common(5)]
    summary = " ".join(sentences[:max_sentences])
    return {
        "summary":        summary,
        "sentence_count": len(sentences),
        "word_count":     len(words),
        "keywords":       keywords,
    }
