"""
AI-генератор дайджеста изменений.

Здесь участвует AI: сырые git-коммиты (машинные сообщения) DeepSeek превращает
в человекочитаемые release notes — группирует по типам, выделяет главное и
переписывает в понятный язык.
"""

MODEL = "deepseek-v4-flash"

SYSTEM_NEUTRAL = (
    "Ты готовишь дайджест изменений (release notes) по коммитам git для читателя, "
    "который не смотрит код. Сгруппируй изменения и перепиши их понятным языком. "
    "Верни Markdown СТРОГО по шаблону:\n"
    "## 🔎 Главное\n<2–4 предложения — суть периода>\n\n"
    "## ✨ Новое\n- …\n## 🐞 Исправления\n- …\n## 📝 Документация\n- …\n"
    "## 🔧 Прочее\n- …\n"
    "В разделах — короткие пункты по сути (не копируй хэши и префиксы вроде "
    "'week7/day4:'). Пустой раздел — «— нет». Пиши на русском, дружелюбно и кратко."
)

# «Токсичный» роаст: язвительный разбор КОДА и коммитов в жанре savage code review.
# Жжём по коду и коммит-сообщениям, а не по авторам как людям.
SYSTEM_TOXIC = (
    "Ты — брутальный код-ревьюер-циник, который РОАСТИТ коммиты в жанре "
    "'savage code review'. Твой стиль: язвительный, саркастичный, беспощадный, "
    "с чёрным юмором про качество коммитов, «гениальные» сообщения коммитов, "
    "отсутствие тестов, полотна изменений и прочий инженерный грех. "
    "Не стесняйся драмы и гипербол — жги.\n\n"
    "ЖЁСТКИЕ ПРАВИЛА (не нарушать даже в шутку):\n"
    "- нападай на КОД, коммиты и инженерные решения, а НЕ на авторов как людей;\n"
    "- никаких оскорблений по признакам личности (пол, раса, религия, "
    "национальность, внешность, ориентация и т.п.), угроз и травли;\n"
    "- не выдумывай факты — только то, что видно в коммитах.\n\n"
    "Верни Markdown СТРОГО по шаблону:\n"
    "## 🔥 Вердикт\n<2–4 предложения беспощадного вердикта по периоду>\n\n"
    "## 💀 Разбор коммитов\n- <язвительный панч по каждому заметному изменению>\n\n"
    "## 🧯 Что бы сделал нормальный инженер\n- <ядовитые, но по делу советы>\n\n"
    "## ⭐ Оценка\n<оценка из 10 с саркастичным обоснованием>\n"
    "Пиши на русском, коротко и хлёстко."
)


def _commits_block(commits: list[dict]) -> str:
    lines = []
    for c in commits:
        body = f"\n    {c['body'][:300]}" if c["body"] else ""
        lines.append(f"- [{c['date']}] {c['subject']}{body}")
    return "\n".join(lines)


def generate(commits: list[dict], title: str = "Дайджест изменений",
             tone: str = "neutral", api_key: str | None = None) -> str:
    """tone: 'neutral' — обычный дайджест; 'toxic' — язвительный роаст коммитов."""
    from openai import OpenAI
    if not (api_key or "").strip():
        raise ValueError("Не задан ключ DeepSeek API.")
    client = OpenAI(api_key=api_key.strip(),
                    base_url="https://api.deepseek.com")
    system = SYSTEM_TOXIC if tone == "toxic" else SYSTEM_NEUTRAL
    # немного «жара» в токсичном режиме
    temperature = 0.9 if tone == "toxic" else 0.4
    verb = "Разнеси эти коммиты по шаблону." if tone == "toxic" else "Сделай дайджест по шаблону."
    user = f"Коммиты ({len(commits)} шт.):\n\n{_commits_block(commits)}\n\n{verb}"
    resp = client.chat.completions.create(
        model=MODEL, temperature=temperature,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    body = resp.choices[0].message.content or ""

    dates = sorted(d for d in {c["date"] for c in commits} if d)
    period = f"{dates[0]} — {dates[-1]}" if dates else ""
    emoji = "🔥" if tone == "toxic" else "📰"
    header = f"# {emoji} {title}\n\n_Период: {period} · коммитов: {len(commits)}_\n\n"
    return header + body
