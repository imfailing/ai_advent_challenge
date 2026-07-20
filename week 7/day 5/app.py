"""
Веб-интерфейс сервиса AI-дайджеста.

Выбираешь диапазон коммитов → AI формирует дайджест → можно опубликовать в
Telegram (если заданы токены). Работает на реальной git-истории репозитория.
"""

import os

from flask import Flask, jsonify, render_template, request

import digest
import gitlog
from notify import send_telegram

app = Flask(__name__)

_last_digest = {"md": ""}   # последний сгенерированный дайджест (для публикации)


@app.route("/")
def index():
    return render_template("index.html", branch=_branch())


def _branch() -> str:
    try:
        return gitlog.current_branch()
    except Exception:
        return "—"


@app.route("/health")
def health():
    return jsonify({
        "branch": _branch(),
        "repo": str(gitlog.REPO_ROOT),
        "deepseek": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "telegram": bool(os.environ.get("TELEGRAM_BOT_TOKEN")
                         and os.environ.get("TELEGRAM_CHAT_ID")),
    })


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    mode = data.get("mode", "last")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        return jsonify({"error": "Не задан DEEPSEEK_API_KEY."}), 503
    try:
        if mode == "since":
            commits = gitlog.get_commits(since=(data.get("since") or "7 days ago"))
        elif mode == "range":
            rng = (data.get("range") or "").strip()
            if not rng:
                return jsonify({"error": "Укажите диапазон base..head"}), 400
            commits = gitlog.get_commits(rev_range=rng)
        else:
            commits = gitlog.get_commits(last=int(data.get("last") or 15))
    except Exception as e:
        return jsonify({"error": f"git: {e}"}), 400

    if not commits:
        return jsonify({"error": "Коммитов в диапазоне нет."}), 400
    try:
        md = digest.generate(commits, title=data.get("title") or "Дайджест изменений")
    except Exception as e:
        return jsonify({"error": f"AI: {e}"}), 500
    _last_digest["md"] = md
    return jsonify({"digest": md, "commits": len(commits)})


@app.route("/publish", methods=["POST"])
def publish():
    if not _last_digest["md"]:
        return jsonify({"error": "Сначала сгенерируйте дайджест."}), 400
    res = send_telegram(_last_digest["md"])
    return jsonify(res)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5011)))
