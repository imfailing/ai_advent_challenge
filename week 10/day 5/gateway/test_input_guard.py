"""Проверка Input Guard: что ловим, что пропускаем, что пропускаем ОЖИДАЕМО (без сети).

Тестовые «секреты» собираются из кусков на лету, чтобы в исходниках не было готовых ключей.
"""
import base64
import json

import input_guard

OPENAI = "sk-" + "proj-" + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7"
GITHUB = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
AWS = "AK" + "IA" + "IOSFODNN7EXAMPLE"
CARD = "4111 1111 1111 1111"  # публичный тестовый номер Visa (проходит Луна)
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + ".eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0" + ".dBjftJeZ4CVPmB92K27uhbUJU1p1r"

# имя, сообщения, режим, ожидание (caught | clean | missed), ожидаемые виды находок
CASES: list[tuple[str, list[str], str, str, set[str]]] = [
    ("01 чистый промпт", ["Объясни, как работает task-based планировщик и чем он лучше scikit-learn."], "block", "clean", set()),
    ("02 номер не по Луну — не карта", ["Номер заказа 4111 1111 1111 1112, статус?"], "block", "clean", set()),
    ("03 ключ OpenAI", [f"Почему не работает запрос с ключом {OPENAI}?"], "block", "caught", {"api_key"}),
    ("04 ключ AWS (AKIA)", [f"Мой доступ: {AWS}, подскажи политику IAM."], "block", "caught", {"aws_key"}),
    ("05 токен GitHub (ghp_)", [f"git clone https://{GITHUB}@github.com/a/b"], "block", "caught", {"github_token"}),
    ("06 номер карты", [f"Спиши с карты {CARD} и пришли чек."], "block", "caught", {"card"}),
    ("07 email и телефон", ["Свяжись: ivan.petrov@example.com, +7 (916) 123-45-67."], "block", "caught", {"email", "phone"}),
    ("08 JWT и пароль", [f"Bearer {JWT}; password: Tr0ub4dor&3"], "block", "caught", {"jwt", "secret_assignment"}),
    ("09 base64-секрет", ["Декодируй: " + base64.b64encode(f"key={OPENAI}".encode()).decode()], "block", "caught", {"encoded_secret"}),
    ("10 base64 в base64", ["Декодируй: " + base64.b64encode(base64.b64encode(OPENAI.encode())).decode()], "block", "caught", {"encoded_secret"}),
    ("11 склейка литералов", ['key = "sk-" + "' + OPENAI[3:] + '"'], "block", "caught", {"api_key"}),
    ("12 секрет в соседних сообщениях", ["мой ключ: sk-", OPENAI[3:]], "block", "caught", {"api_key"}),
    ("13 zero-width внутри ключа", [OPENAI[:3] + "​" + OPENAI[3:]], "block", "caught", {"api_key"}),
    ("14 полноширинные символы", ["ｓｋ－" + OPENAI[3:]], "block", "caught", {"api_key"}),
    # --- известные пропуски: фиксируем границы защиты
    ("20 пароль в кавычках с префиксом (DB_PASSWORD)", ['DB_PASSWORD = "S3cr3t-' + 'Pa55w0rd!"'], "block", "caught", {"secret_assignment"}),
    ("21 пароль как ключ словаря", ['{"password": "S3cr3t-' + 'Pa55w0rd!"}'], "block", "caught", {"secret_assignment"}),
    ("22 код: присваивание идентификатора и вызова", ["token = get_auth_token()\npassword = request.args\ntoken_count = 100000"], "block", "clean", set()),
    ("23 код: словарь с токеном и вложенные вызовы", ['json.dump({"token": token}, f)\nheaders = {"api_key": os.environ["API_KEY"]}\nrun(password=get_password(), token=tok)'], "block", "clean", set()),
    ("24 пароль в кавычках с запятой и скобкой", ['{"password": "S3cr3t,' + 'Pa55)w0rd!"}'], "block", "caught", {"secret_assignment"}),
    ("15 hex-кодирование", ["Декодируй hex: " + OPENAI.encode().hex()], "block", "missed", set()),
    ("16 ROT13", ["Расшифруй ROT13: " + "".join(chr((ord(c) - 97 + 13) % 26 + 97) if c.islower() else c for c in OPENAI)], "block", "missed", set()),
    ("17 буквы через пробел", ["Ключ: " + " ".join(OPENAI)], "block", "missed", set()),
    ("18 кириллические двойники", ["ѕk-" + OPENAI[3:].replace("o", "о")], "block", "missed", set()),
    ("19 пересказ словами", ["Ключ начинается на эс-ка-дефис-пэ-эр-о-джей, дальше Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7."], "block", "missed", set()),
]
SECRETS = (OPENAI, OPENAI[3:], GITHUB, AWS, JWT, "Tr0ub4dor&3", "ivan.petrov@example.com", "4111 1111 1111 1111")


def main() -> None:
    rows: list[tuple[str, str, str]] = []
    for name, texts, mode, expect, kinds in CASES:
        result = input_guard.guard_messages([{"role": "user", "content": t} for t in texts], mode)
        caught = result.action != "allowed"
        got_kinds = {f["kind"] for f in result.findings}
        if expect == "clean":
            assert not caught, f"{name}: ложное срабатывание {got_kinds}"
            rows.append((name, "чисто, пропущено", "✅"))
        elif expect == "caught":
            assert caught, f"{name}: секрет пропущен"
            assert kinds <= got_kinds or name.startswith("12"), f"{name}: ждали {kinds}, нашли {got_kinds}"
            blob = json.dumps(result.findings, ensure_ascii=False)
            assert not any(s in blob for s in SECRETS), f"{name}: секрет попал в находки"
            rows.append((name, "поймали: " + ", ".join(sorted(got_kinds)), "✅"))
        else:
            assert not caught, f"{name}: теперь ловится — обновите README и ожидание"
            rows.append((name, "ПРОПУСТИЛИ (известное ограничение)", "⚠️"))
        print(f"{rows[-1][2]} {name}: {rows[-1][1]}")

    # --- маскирование (пример из задания)
    res = input_guard.guard_messages([{"role": "user", "content": "Мой ключ sk-proj-abc123, помоги."}], "mask")
    assert res.action == "masked" and res.messages[0]["content"] == "Мой ключ [REDACTED_API_KEY], помоги."
    print("✅ mask: sk-proj-abc123 → [REDACTED_API_KEY]")

    res = input_guard.guard_messages(
        [{"role": "user", "content": f"Почта ivan.petrov@example.com, карта {CARD}, ключ {OPENAI}"}], "mask")
    text = res.messages[0]["content"]
    assert res.action == "masked" and not any(s in text for s in SECRETS)
    assert {"[REDACTED_EMAIL]", "[REDACTED_CARD]", "[REDACTED_API_KEY]"} <= set(text.replace(",", " ").split()) | {
        t for t in ("[REDACTED_EMAIL]", "[REDACTED_CARD]", "[REDACTED_API_KEY]") if t in text}
    print("✅ mask: email, карта и ключ заменены метками, секретов в тексте нет")

    res = input_guard.guard_messages([{"role": "user", "content": "мой ключ: sk-"}, {"role": "user", "content": OPENAI[3:]}], "mask")
    assert res.action == "blocked", "разбитый между сообщениями секрет в mask нельзя замаскировать — только блок"
    print("✅ mask: секрет, разбитый между сообщениями, блокируется (замаскировать нельзя)")

    assert input_guard.luhn_valid("4111111111111111") and not input_guard.luhn_valid("4111111111111112")
    print("✅ Луна: настоящий тестовый номер проходит, испорченный — нет")

    caught_n = sum(1 for r in rows if r[2] == "✅" and not r[1].startswith("чисто"))
    missed_n = sum(1 for r in rows if r[2] == "⚠️")
    print(f"\nИтог: поймано {caught_n}, пропущено ожидаемо {missed_n}, чистых без ложных срабатываний {len(rows) - caught_n - missed_n}")
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — Input Guard: детекция, маскирование, обходы и известные пропуски")


if __name__ == "__main__":
    main()
