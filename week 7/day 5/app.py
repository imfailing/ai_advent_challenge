"""
Веб-сервис анализа удалённого GitHub-репозитория.

Вводишь GitHub-репозиторий → AI формирует дайджест изменений или 🐓 rooster-роаст
по коммитам → можно опубликовать в Telegram (если заданы токены).

Все токены (DeepSeek, GitHub, Telegram) задаются в интерфейсе и передаются в
запросе — из окружения ничего не читается. Работает только с УДАЛЁННЫМИ
репозиториями (GitHub REST API). Готов к деплою на VPS в Docker.
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
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)

    deepseek_key = (data.get("deepseek_key") or "").strip()
    if not deepseek_key:
        return jsonify({"error": "Укажите ключ DeepSeek API."}), 400

    repo = (data.get("repo") or "").strip()
    if not repo:
        return jsonify({"error": "Укажите GitHub-репозиторий (owner/repo или ссылку)."}), 400
    github_token = (data.get("github_token") or "").strip()
    tone = "toxic" if data.get("toxic") else "neutral"
    last = max(1, min(int(data.get("last") or 15), 100))

    try:
        commits = github_repo.get_commits(repo, last=last, token=github_token)
        label = github_repo.repo_label(repo)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    if not commits:
        return jsonify({"error": "Коммитов не найдено."}), 400

    title = (f"Роаст коммитов {label}" if tone == "toxic"
             else f"Дайджест изменений {label}")
    try:
        md = digest.generate(commits, title=title, tone=tone, api_key=deepseek_key)
    except Exception as e:
        return jsonify({"error": f"AI: {e}"}), 500
    _last_digest["md"] = md
    return jsonify({"digest": md, "commits": len(commits), "source": label, "tone": tone})


@app.route("/publish", methods=["POST"])
def publish():
    if not _last_digest["md"]:
        return jsonify({"error": "Сначала сгенерируйте результат."}), 400
    data = request.get_json(force=True) or {}
    token = (data.get("telegram_token") or "").strip()
    chat_id = (data.get("telegram_chat_id") or "").strip()
    return jsonify(send_telegram(_last_digest["md"], token=token, chat_id=chat_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5011)))
