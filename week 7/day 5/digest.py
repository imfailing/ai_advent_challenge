"""
AI-генератор дайджеста изменений.

Здесь участвует AI: сырые git-коммиты (машинные сообщения) DeepSeek превращает
в человекочитаемые release notes — группирует по типам, выделяет главное и
переписывает в понятный язык.
"""

import os

MODEL = "deepseek-v4-flash"

SYSTEM = (
    "Ты готовишь дайджест изменений (release notes) по коммитам git для читателя, "
    "который не смотрит код. Сгруппируй изменения и перепиши их понятным языком. "
    "Верни Markdown СТРОГО по шаблону:\n"
    "## 🔎 Главное\n<2–4 предложения — суть периода>\n\n"
    "## ✨ Новое\n- …\n## 🐞 Исправления\n- …\n## 📝 Документация\n- …\n"
    "## 🔧 Прочее\n- …\n"
    "В разделах — короткие пункты по сути (не копируй хэши и префиксы вроде "
    "'week7/day4:'). Пустой раздел — «— нет». Пиши на русском, дружелюбно и кратко."
)


def _commits_block(commits: list[dict]) -> str:
    lines = []
    for c in commits:
        body = f"\n    {c['body'][:300]}" if c["body"] else ""
        lines.append(f"- [{c['date']}] {c['subject']}{body}")
    return "\n".join(lines)


def generate(commits: list[dict], title: str = "Дайджест изменений",
             api_key: str | None = None) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com")
    user = (f"Коммиты ({len(commits)} шт.):\n\n{_commits_block(commits)}\n\n"
            f"Сделай дайджест по шаблону.")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}])
    body = resp.choices[0].message.content or ""

    dates = sorted({c["date"] for c in commits})
    period = f"{dates[0]} — {dates[-1]}" if dates else ""
    header = f"# 📰 {title}\n\n_Период: {period} · коммитов: {len(commits)}_\n\n"
    return header + body
