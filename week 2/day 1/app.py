"""
Flask-приложение — только UI и маршрутизация.
Вся логика LLM-вызовов спрятана в LLMAgent.
"""

from flask import Flask, jsonify, render_template, request

from agent import LLMAgent

app = Flask(__name__)
agent = LLMAgent()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Пустой запрос"}), 400

    response = agent.ask(user_message)
    return jsonify({
        "answer": response.answer,
        "model": response.model,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "elapsed_sec": response.elapsed_sec,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
