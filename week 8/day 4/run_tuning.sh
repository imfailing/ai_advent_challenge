#!/usr/bin/env bash
# Тюнинг на задаче генерации: правила (none/short/full), температура, размер контекста.
# Базовая точка: rules=short, temperature=0.1, num_ctx=16384.
cd "$(dirname "$0")"
PY="${PY:-python3}"; RUFF="${RUFF:-ruff}"
run() { "$PY" bench.py feature "$1" --ruff "$RUFF" "${@:2}" 2>&1 | tail -2 | head -1; }
for m in ${MODELS:-qwen2.5-coder:7b qwen2.5-coder:14b}; do
  for r in none full; do run "$m" --rules $r; done
  for t in 0 0.4 0.8; do run "$m" --temperature $t; done
  for c in 4096 8192 32768; do run "$m" --num-ctx $c; done
done
