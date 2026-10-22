"""
Офлайн-сервер для UI smoke-сценариев (порт 5012).

Запускает настоящее приложение (`app.py`, `templates/index.html`), но внешние вызовы
подменены детерминированными заглушками: GitHub API, DeepSeek и Telegram не нужны, сети нет.
Сверх этого даёт агенту два служебных маршрута для скриншотов:
  GET  /__smoke/shot.js   — подключает html2canvas и определяет window.__shot(name)
  POST /__smoke/shot      — сохраняет PNG (data URL) в smoke/screenshots/<name>.png

Особые входы (для сценариев ошибок):
  repo "ghost/none"        → «репозиторий не найден»
  ключ DeepSeek "bad-key"  → ошибка AI (500)
"""

import base64
import re
import sys
from pathlib import Path
from unittest import mock

from flask import jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402  (нужен sys.path выше)
import github_repo  # noqa: E402

SHOTS = Path(__file__).resolve().parent / "screenshots"
PORT = 5012

SHOT_JS = """
(async () => {
  if (!window.html2canvas) {
    await new Promise((ok, fail) => {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
      s.onload = ok; s.onerror = () => fail(new Error('html2canvas не загрузился'));
      document.head.appendChild(s);
    });
  }
  window.__shot = async (name) => {
    const canvas = await html2canvas(document.body, {backgroundColor: '#0f1117', scale: 1});
    const r = await fetch('/__smoke/shot', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, data: canvas.toDataURL('image/png')})});
    return (await r.json());
  };
  return 'shot ready';
})()
"""

FAKE_DIGEST = (
    "## 🔎 Главное\nТестовый период: добавлена статистика и исправлен баг.\n\n"
    "## ✨ Новое\n- Эндпоинт `/stats`\n- Модуль `activity.py`\n\n"
    "## 🐞 Исправления\n- `last` в `/generate` больше не даёт HTML 500\n"
)


def fake_get_commits(repo: str, last: int = 15, token: str = "") -> list[dict]:
    owner_repo = github_repo.parse_repo(repo)
    if owner_repo == "ghost/none":
        raise RuntimeError(
            f"Репозиторий {owner_repo} не найден или приватный (укажите GitHub-токен).")
    days = ["2026-10-20", "2026-10-21", "2026-10-21"]
    authors = ["Ann", "Ann", "Bob"]
    return [{"hash": f"c{i}", "date": days[i], "author": authors[i],
             "subject": f"feat: change {i}", "body": ""} for i in range(min(last, 3))]


def fake_generate(commits: list[dict], title: str = "", tone: str = "neutral",
                  api_key: str | None = None) -> str:
    if api_key == "bad-key":
        raise RuntimeError("401 Unauthorized: invalid api key")
    period = f"_Период: 2026-10-20 — 2026-10-21 · коммитов: {len(commits)}_"
    return f"# {title}\n\n{period}\n\n{FAKE_DIGEST}"


def fake_send_telegram(text: str, token: str = "", chat_id: str = "") -> dict:
    if not token or not chat_id:
        return {"status": "skipped",
                "reason": "не заданы токен бота и chat_id — публикация пропущена."}
    return {"status": "sent", "response": {"ok": True}}


@app_module.app.route("/__smoke/shot.js")
def shot_js():
    return SHOT_JS, 200, {"Content-Type": "application/javascript; charset=utf-8"}


@app_module.app.route("/__smoke/shot", methods=["POST"])
def shot():
    data = request.get_json(force=True)
    name = re.sub(r"[^\w.-]", "_", str(data.get("name") or "shot"))
    raw = str(data.get("data") or "").split(",", 1)[-1]
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    path.write_bytes(base64.b64decode(raw))
    return jsonify({"saved": str(path.name), "bytes": path.stat().st_size})


if __name__ == "__main__":
    with (mock.patch("github_repo.get_commits", fake_get_commits),
          mock.patch("digest.generate", fake_generate),
          mock.patch("app.send_telegram", fake_send_telegram)):
        app_module.app.run(host="127.0.0.1", port=PORT, threaded=True)
