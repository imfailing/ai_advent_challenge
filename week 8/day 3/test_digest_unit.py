"""Проверка digest._commits_block и digest.generate без сети (OpenAI подменён)."""
from unittest import mock

import digest

COMMITS = [
    {"hash": "a", "date": "2024-01-03", "subject": "feat: x", "body": "Б" * 400},
    {"hash": "b", "date": "2024-01-01", "subject": "fix: y", "body": ""},
]


def _fake_openai(content: str | None = "ТЕЛО"):
    cls = mock.MagicMock()
    cls.return_value.chat.completions.create.return_value.choices = [
        mock.MagicMock(message=mock.MagicMock(content=content))]
    return cls


def main() -> None:
    block = digest._commits_block(COMMITS)
    lines = block.split("\n")
    assert lines[0] == "- [2024-01-03] feat: x"
    assert lines[1] == "    " + "Б" * 300 and "Б" * 301 not in block
    assert lines[2] == "- [2024-01-01] fix: y" and len(lines) == 3
    assert digest._commits_block([]) == ""
    print("✅ _commits_block: формат, обрезка body до 300, пустой список")

    with mock.patch("openai.OpenAI", _fake_openai()) as cls:
        md = digest.generate(COMMITS, title="T", api_key="  key ")
    cls.assert_called_once_with(api_key="key", base_url="https://api.deepseek.com")
    kw = cls.return_value.chat.completions.create.call_args.kwargs
    assert kw["model"] == digest.MODEL and kw["temperature"] == 0.4
    assert kw["messages"][0]["content"] == digest.SYSTEM_NEUTRAL
    assert "Сделай дайджест" in kw["messages"][1]["content"]
    assert "(2 шт.)" in kw["messages"][1]["content"]
    assert md == "# 📰 T\n\n_Период: 2024-01-01 — 2024-01-03 · коммитов: 2_\n\nТЕЛО"
    print("✅ generate neutral: ключ, температура 0.4, промпт, заголовок и период")

    with mock.patch("openai.OpenAI", _fake_openai()) as cls:
        md = digest.generate(COMMITS, title="R", tone="toxic", api_key="k")
    kw = cls.return_value.chat.completions.create.call_args.kwargs
    assert kw["temperature"] == 0.9 and kw["messages"][0]["content"] == digest.SYSTEM_TOXIC
    assert "Разнеси" in kw["messages"][1]["content"] and md.startswith("# 🔥 R")
    print("✅ generate toxic: температура 0.9, токсичный промпт, 🔥")

    with mock.patch("openai.OpenAI", _fake_openai(None)):
        md = digest.generate([{"hash": "a", "date": "", "subject": "s", "body": ""}], api_key="k")
    assert md.endswith("_Период:  · коммитов: 1_\n\n")
    print("✅ generate: пустой content и коммиты без дат не падают")

    for key in (None, "", "   "):
        with mock.patch("openai.OpenAI", _fake_openai()) as cls:
            try:
                digest.generate(COMMITS, api_key=key)
            except ValueError as e:
                assert "ключ DeepSeek" in str(e)
            else:
                raise AssertionError(key)
            cls.assert_not_called()
    print("✅ generate без ключа -> ValueError, клиент не создаётся")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — digest (промпты, формат, ключ) без сети")


if __name__ == "__main__":
    main()
