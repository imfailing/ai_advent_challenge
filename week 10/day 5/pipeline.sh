#!/usr/bin/env bash
# Единая точка входа пайплайна: setup | test | gateway | loop [аргументы loop.py] | smoke
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3.13}"
VENV_PY="$PWD/venv/bin/python"

[ -f .env ] && { set -a; . ./.env; set +a; }   # необязательный файл с LLAMA_* (см. .env.example)

need_env() {
  for v in LLAMA_API_KEY LLAMA_BASE_URL; do
    [ -n "${!v:-}" ] || { echo "Не задана переменная $v (см. .env.example)" >&2; exit 1; }
  done
}

case "${1:-help}" in
  setup)
    "$PY" -m venv venv && ./venv/bin/pip install -q -r requirements.txt && echo "Окружение готово: $VENV_PY" ;;
  test)
    for t in test_input_guard test_output_guard test_gateway; do (cd gateway && "$VENV_PY" "$t.py" | tail -1); done
    (cd loop && "$VENV_PY" test_loop.py | tail -1) ;;
  gateway)
    need_env
    cd gateway && PORT="${PORT:-5013}" exec "$VENV_PY" app.py ;;
  loop)
    shift
    ruff_arg=(); [ -n "${RUFF:-}" ] && ruff_arg=(--ruff "$RUFF")
    cd loop && exec "$VENV_PY" loop.py --python "$VENV_PY" "${ruff_arg[@]}" --gateway-url "${GATEWAY_URL:-http://127.0.0.1:${PORT:-5013}/chat}" "$@" ;;
  smoke)   # быстрая проверка шлюза без модели: health + блокировка секрета (в модель ничего не уходит)
    base="http://127.0.0.1:${PORT:-5013}"
    curl -fsS "$base/health"; echo
    key="sk-""proj-Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7"
    curl -sS -w '\nHTTP %{http_code}\n' "$base/chat" -H 'Content-Type: application/json' -d "{\"prompt\": \"мой ключ $key\"}" ;;
  *)
    sed -n '2p' "$0"; echo "Подробности — в README.md" ;;
esac
