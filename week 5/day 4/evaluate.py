"""
Проверка структурированных ответов на 10 контрольных вопросах:

  • есть ли ИСТОЧНИКИ в каждом ответе;
  • есть ли ЦИТАТЫ в каждом ответе;
  • ЗАЗЕМЛЕНЫ ли цитаты (реально ли они из найденных чанков);
  • совпадает ли СМЫСЛ ответа с цитатами (ожидаемый факт есть и в ответе,
    и подтверждён хотя бы одной заземлённой цитатой).

Плюс режим «не знаю»: на вопросах вне базы ассистент обязан вернуть know=false
и попросить уточнение.
"""

from eval_set import EVAL
from rag import Answer, RagAgent, RagConfig

OUT_OF_DOMAIN = [
    "Какая столица Австралии?",
    "Сколько стоит биткоин сегодня?",
    "Как приготовить борщ?",
]


def meaning_match(ans: Answer, expected: list[str]) -> bool:
    """Ожидаемый факт есть в ответе И подтверждён заземлённой цитатой."""
    a_low = ans.answer.lower()
    quotes = " ".join(q["text"].lower() for q in ans.quotes if q["grounded"])
    in_answer = any(kw.lower() in a_low for kw in expected)
    in_quotes = any(kw.lower() in quotes for kw in expected)
    return in_answer and in_quotes


def main() -> None:
    agent = RagAgent()
    cfg   = RagConfig()

    has_src = has_quo = grounded_ok = meaning_ok = 0
    print("КОНТРОЛЬНЫЕ ВОПРОСЫ (in-domain):")
    def short(text: str, n: int = 200) -> str:
        text = " ".join(text.split())
        return text if len(text) <= n else text[:n] + "…"

    for i, item in enumerate(EVAL, 1):
        r = agent.ask(item["question"], cfg)
        n_src   = len(r.sources)
        n_quo   = len(r.quotes)
        n_grnd  = sum(1 for q in r.quotes if q["grounded"])
        src_ok  = r.know and n_src > 0
        quo_ok  = r.know and n_quo > 0
        grnd_ok = r.know and n_grnd > 0
        mean_ok = meaning_match(r, item["expected"])

        has_src     += src_ok
        has_quo     += quo_ok
        grounded_ok += grnd_ok
        meaning_ok  += mean_ok
        print("\n" + "─" * 68)
        print(f"[{i:>2}/10] ❓ {item['question']}")
        print(f"  🤖 {short(r.answer) if r.know else '(не знаю: ' + short(r.clarification, 80) + ')'}")
        print(f"  📎 источники: " +
              (", ".join(f"{s['source']}→{(s.get('section') or '')[:22]}" for s in r.sources) or "—"))
        if r.quotes:
            print("  💬 цитаты:")
            for qt in r.quotes:
                print(f"     [{'✓' if qt['grounded'] else '✗'}] «{short(qt['text'], 90)}»")
        print(f"  ▸ источники {'✓' if src_ok else '✗'}({n_src})  "
              f"цитаты {'✓' if quo_ok else '✗'}({n_quo}, заземл. {n_grnd})  "
              f"смысл↔цитаты {'✓' if mean_ok else '✗'}")

    print("\nOUT-OF-DOMAIN (режим «не знаю»):")
    dont_know = 0
    for q in OUT_OF_DOMAIN:
        r = agent.ask(q, cfg)
        ok = (not r.know) and bool(r.clarification)
        dont_know += ok
        print(f"  • «{q[:34]}» → know={r.know} (score {r.top_score}) "
              f"{'✓ не знаю + уточнение' if ok else '✗'}")

    n = len(EVAL)
    print("\n" + "=" * 60)
    print("  ИТОГ")
    print("=" * 60)
    print(f"Источники есть:                 {has_src}/{n}")
    print(f"Цитаты есть:                    {has_quo}/{n}")
    print(f"Цитаты заземлены (из чанков):   {grounded_ok}/{n}")
    print(f"Смысл ответа ↔ цитаты:          {meaning_ok}/{n}")
    print(f"Режим «не знаю» (out-of-domain):{dont_know}/{len(OUT_OF_DOMAIN)}")


if __name__ == "__main__":
    main()
