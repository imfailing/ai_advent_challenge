"""
Проверка сервиса:
  • доступ к модели по сети (health + chat через HTTP);
  • стабильность при НЕСКОЛЬКИХ параллельных запросах;
  • базовые ограничения: rate limit (429) и max context (413);
  • аутентификация (401 без ключа, когда включена).

Поднимает сервис на реальном порту (в отдельном потоке) и ходит по HTTP —
имитируя сетевой доступ. Нужен запущенный Ollama.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# сконфигурируем сервис ДО импорта: строгие лимиты, чтобы проверить их быстро
os.environ["API_KEYS"] = "test-key"
os.environ["RATE_LIMIT"] = "5"
os.environ["RATE_WINDOW"] = "60"
os.environ["MAX_INPUT_CHARS"] = "500"

import config as cfg          # noqa: E402
import service                # noqa: E402

BASE = f"http://127.0.0.1:{cfg.PORT}"
KEY = "test-key"


def _req(path, method="GET", body=None, key=KEY):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def start_server():
    t = threading.Thread(
        target=lambda: service.app.run(host="127.0.0.1", port=cfg.PORT,
                                       threaded=True, use_reloader=False),
        daemon=True)
    t.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/v1/health", timeout=2)
            return
        except Exception:
            time.sleep(0.2)


def main() -> None:
    start_server()

    # 1. доступ по сети: health
    st, body = _req("/v1/health", key=None)
    h = json.loads(body)
    assert st == 200 and h["ollama_up"], f"health: {st} {body[:120]}"
    print(f"✅ доступ по сети: /v1/health ok, модель {h['model']}, лимиты {h['limits']['rate_limit']}")

    # 2. auth: без ключа — 401
    st, _ = _req("/v1/chat", "POST", {"message": "привет"}, key=None)
    assert st == 401, f"ожидался 401, получен {st}"
    print("✅ аутентификация: без ключа → 401")

    # 3. простой чат по сети
    st, body = _req("/v1/chat", "POST", {"message": "Ответь одним словом: столица Италии?"})
    assert st == 200, f"chat: {st}"
    answer = "".join(json.loads(l)["token"] for l in body.splitlines()
                     if l.strip() and "token" in json.loads(l))
    assert answer.strip(), "пустой ответ"
    print(f"✅ чат по сети: «{answer.strip()[:40]}»")

    # 4. max context: слишком длинный вход → 413
    st, body = _req("/v1/chat", "POST", {"message": "a" * 600})
    assert st == 413, f"ожидался 413, получен {st}"
    print(f"✅ max context: {600} симв > лимита {cfg.MAX_INPUT_CHARS} → 413")

    # 5. стабильность при нескольких ПАРАЛЛЕЛЬНЫХ запросах
    #    (используем разные ключи-IP? нет — один ключ; поэтому сначала проверим
    #     параллелизм на коротких запросах в пределах лимита)
    time.sleep(1)
    os.environ  # noop
    service.limiter.__init__(100, 60)   # временно ослабим лимит для теста параллелизма
    def one(i):
        s, b = _req("/v1/chat", "POST", {"message": f"Скажи число {i} и всё."})
        ok = s == 200 and any("token" in json.loads(l) for l in b.splitlines() if l.strip())
        return ok
    with ThreadPoolExecutor(max_workers=5) as ex:
        res = list(ex.map(one, range(5)))
    assert all(res), f"часть параллельных запросов упала: {res}"
    print(f"✅ стабильность: 5 параллельных запросов — все успешны ({sum(res)}/5)")

    # 6. rate limit: вернём строгий лимит и превысим его
    service.limiter.__init__(3, 60)
    codes = [_req("/v1/chat", "POST", {"message": "hi"})[0] for _ in range(6)]
    assert 429 in codes, f"rate limit не сработал: {codes}"
    n_ok = codes.count(200)
    print(f"✅ rate limit: лимит 3/мин → {n_ok} прошло, потом 429 (коды: {codes})")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — сервис готов к деплою на VPS")


if __name__ == "__main__":
    main()
