"""
Проверка ассистента поддержки:
  • индекс документации продукта собран;
  • MCP-сервер отдаёт данные тикета (контекст пользователя);
  • ответ учитывает тариф из тикета (SSO на Pro → предложить Business);
  • ответ опирается на документацию (есть источники);
  • веб-эндпоинты /tickets и /ask работают.

Нужен DEEPSEEK_API_KEY и построенный индекс (python build_index.py).
"""

import app as flask_app
import index_store


def main() -> None:
    assert index_store.count("structural") >= 8, "индекс не построен: python build_index.py"
    print(f"✅ индекс документации продукта: {index_store.count('structural')} чанков")

    c = flask_app.app.test_client()
    assert c.get("/").status_code == 200

    # список тикетов (для UI)
    tks = c.get("/tickets").get_json()
    assert any(t["id"] == "T-1002" for t in tks), "тикеты не отдаются"
    print(f"✅ /tickets: {len(tks)} тикетов")

    # пример: SSO-вопрос по тикету Pro-пользователя
    r = c.post("/ask", json={"message": "Почему не работает авторизация через SSO?",
                             "ticket_id": "T-1002"}).get_json()
    assert r.get("ticket") and r["ticket"]["user"]["plan"] == "Pro", "контекст тикета не подтянут"
    assert r["sources"], "нет источников из документации"
    low = r["answer"].lower()
    assert "business" in low, "ответ не учёл, что SSO только на Business"
    assert "pro" in low or "тариф" in low
    print("✅ T-1002 (Pro, SSO): ответ учёл тариф → SSO на Business, есть источники")

    # пример из задания: «Почему не работает авторизация?» по тикету Free
    r = c.post("/ask", json={"message": "Почему не работает авторизация?",
                             "ticket_id": "T-1004"}).get_json()
    assert r["ticket"]["user"]["plan"] == "Free"
    low = r["answer"].lower()
    assert "устройств" in low or "free" in low or "тариф" in low
    print("✅ T-1004 (Free): ответ учёл ограничение тарифа (устройства/синхронизация)")

    # без тикета — просто по документации
    r = c.post("/ask", json={"message": "Не приходит код при входе, что делать?"}).get_json()
    assert r["sources"] and not r["ticket"]
    print("✅ без тикета: ответ по документации (2FA), источники есть")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — ассистент поддержки работает")


if __name__ == "__main__":
    main()
