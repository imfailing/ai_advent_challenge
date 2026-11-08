"""
Промпт генерации и разбор ответа модели в файлы решения.

Роль в цикле: собирает запрос «задача + контекст проекта (+ фидбек)», а из ответа достаёт ровно два
файла `solution.py` и `test_solution.py` по маркерам `=== FILE: имя ===` … `=== END ===`.
Другие имена файлов отбрасываются (защита от записи вне песочницы). Модуль чистый: без сети.
"""

import re

ALLOWED_FILES = ("solution.py", "test_solution.py")
_BLOCK = re.compile(r"=== FILE: ([\w./-]+) ===\n(.*?)\n=== END ===", re.DOTALL)

FORMAT_RULES = """Требования:
- Python 3.13, только стандартная библиотека (HTTP — через urllib), без внешних зависимостей.
- Тесты запускаются командой `python test_solution.py`: функция main() с assert и print("✅ …"),
  в конце `if __name__ == "__main__": main()`. Тесты не ходят в сеть и не пишут вне временной папки
  (внешние вызовы подменяй через unittest.mock.patch).
- Код должен проходить ruff.

Верни ровно два файла в таком формате (без markdown-ограждений и пояснений):
=== FILE: solution.py ===
<код>
=== END ===
=== FILE: test_solution.py ===
<код>
=== END ==="""


class FormatError(Exception):
    """Ответ модели не содержит оба файла решения."""


def build_prompt(task: str, context: dict[str, str], previous: dict[str, str] | None = None,
                 feedback: str | None = None) -> str:
    """Собрать промпт генерации; с `feedback` (и `previous`, если есть) — запрос на исправление."""
    files = "\n\n".join(f"--- {name} ---\n{text}" for name, text in context.items())
    parts = [f"Задача: {task}", f"Файлы проекта:\n{files}"]
    if previous:
        prev = "\n\n".join(f"=== FILE: {name} ===\n{text}\n=== END ===" for name, text in previous.items())
        parts.append(f"Предыдущая версия решения:\n{prev}")
    if feedback:  # фидбек нужен и без предыдущей версии: ответ мог быть заблокирован или неверного формата
        parts.append(f"Предыдущая попытка не принята. Замечания:\n{feedback}\nУчти их и верни оба файла целиком.")
    parts.append(FORMAT_RULES)
    return "\n\n".join(parts)


def parse_files(text: str) -> dict[str, str]:
    """Достать solution.py и test_solution.py из ответа; лишние имена игнорируются."""
    found = {name: body.strip("\n") + "\n" for name, body in _BLOCK.findall(text) if name in ALLOWED_FILES}
    missing = [n for n in ALLOWED_FILES if n not in found]
    if missing:
        raise FormatError("в ответе нет файлов: " + ", ".join(missing))
    return found
