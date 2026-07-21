"""
Веб-сервис анализа удалённого GitHub-репозитория.

Вводишь GitHub-репозиторий → AI формирует дайджест изменений или 🔥 токсичный
роаст по коммитам → можно опубликовать в Telegram (если заданы токены).

Работает только с УДАЛЁННЫМИ репозиториями (GitHub REST API) — ни локального
git, ни CLI. Готов к деплою на VPS в Docker.
"""

import os

from flask import Flask, jsonify, render_template, request

import digest
import github_repo
from notify import send_telegram

app = Flask(__name__)

_last_digest = {"md": ""}   # последний результат (для публикации)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status":   "ok",
        "deepseek": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "github_token": bool(os.environ.get("GITHUB_TOKEN")),   # опц. (приватные/лимиты)
        "telegram": bool(os.environ.get("TELEGRAM_BOT_TOKEN")
                         and os.environ.get("TELEGRAM_CHAT_ID")),
    })


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return jsonify({"error": "Не задан DEEPSEEK_API_KEY."}), 503

    repo = (data.get("repo") or "").strip()
    if not repo:
        return jsonify({"error": "Укажите GitHub-репозиторий (owner/repo или ссылку)."}), 400
    tone = "toxic" if data.get("toxic") else "neutral"
    last = max(1, min(int(data.get("last") or 15), 100))

    try:
        commits = github_repo.get_commits(repo, last=last)
        label = github_repo.repo_label(repo)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    if not commits:
        return jsonify({"error": "Коммитов не найдено."}), 400

    default_title = (f"Роаст коммитов {label}" if tone == "toxic"
                     else f"Дайджест изменений {label}")
    title = (data.get("title") or "").strip() or default_title
    try:
        md = digest.generate(commits, title=title, tone=tone)
    except Exception as e:
        return jsonify({"error": f"AI: {e}"}), 500
    _last_digest["md"] = md
    return jsonify({"digest": md, "commits": len(commits), "source": label, "tone": tone})


@app.route("/publish", methods=["POST"])
def publish():
    if not _last_digest["md"]:
        return jsonify({"error": "Сначала сгенерируйте результат."}), 400
    return jsonify(send_telegram(_last_digest["md"]))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5011)))
