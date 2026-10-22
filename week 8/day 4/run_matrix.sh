#!/usr/bin/env bash
# Основной прогон: обе задачи на каждой модели (температура 0.1, контекст 16k, короткие правила).
# Запуск: PY=<python3.13> RUFF=<путь к ruff> ./run_matrix.sh
cd "$(dirname "$0")"
PY="${PY:-python3}"; RUFF="${RUFF:-ruff}"
for m in qwen2.5-coder:7b qwen2.5-coder:14b deepseek-coder-v2:16b qwen3:8b gemma3:12b; do
  for t in feature agent; do
    "$PY" bench.py "$t" "$m" --ruff "$RUFF" 2>&1 | tail -2
  done
done
