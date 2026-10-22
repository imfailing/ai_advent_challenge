#!/usr/bin/env bash
# Повторы ключевых конфигураций, чтобы отделить эффект параметров от случайного разброса.
cd "$(dirname "$0")"
PY="${PY:-python3}"; RUFF="${RUFF:-ruff}"
run() { "$PY" bench.py feature "$1" --ruff "$RUFF" "${@:2}" 2>&1 | tail -2 | head -1 | cut -c1-80; }
for i in 2 3 4; do run qwen2.5-coder:7b --tag _r$i; done
for i in 2 3; do run qwen2.5-coder:7b --rules none --tag _r$i; done
for i in 2 3; do run qwen2.5-coder:14b --tag _r$i; done
for i in 2; do run qwen2.5-coder:14b --rules none --tag _r$i; done
for i in 2; do run qwen2.5-coder:14b --temperature 0.4 --tag _r$i; done
