"""
MCP-сервер с инструментами для пайплайна:

    search → summarize → save_to_file
    (получить данные) (обработать)  (сохранить результат)

Каждый инструмент самостоятелен; пайплайн собирается тем, кто их вызывает
(агентом автоматически или тестом вручную), передавая выход одного на вход
следующего.
"""

from pathlib import Path

import corpus
import summarizer
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pipeline-server")

OUTPUT_DIR = Path(__file__).parent / "output"


@mcp.tool()
def search(query: str, limit: int = 5) -> list[dict]:
    """
    ШАГ 1 (получить данные). Найти документы по запросу.

    Параметры:
        query: поисковый запрос.
        limit: максимум документов (по умолчанию 5).
    Возвращает: список {id, title, text, score}.
    """
    return corpus.search(query, limit)


@mcp.tool()
def summarize(text: str, max_sentences: int = 3) -> dict:
    """
    ШАГ 2 (обработать). Сжать переданный текст в краткую сводку.

    Параметры:
        text:          текст для сжатия (например, объединённые тексты из search).
        max_sentences: сколько предложений оставить в сводке.
    Возвращает: {summary, sentence_count, word_count, keywords}.
    """
    return summarizer.summarize(text, max_sentences)


@mcp.tool()
def save_to_file(filename: str, content: str) -> dict:
    """
    ШАГ 3 (сохранить результат). Записать content в файл в папке output/.

    Параметры:
        filename: имя файла (без путей; небезопасные символы убираются).
        content:  что сохранить (например, сводку из summarize).
    Возвращает: {path, bytes, ok}.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe = Path(filename).name or "result.txt"   # убираем пути
    path = OUTPUT_DIR / safe
    data = content if content.endswith("\n") else content + "\n"
    path.write_text(data, encoding="utf-8")
    return {"path": str(path), "bytes": len(data.encode("utf-8")), "ok": True}


if __name__ == "__main__":
    mcp.run()
