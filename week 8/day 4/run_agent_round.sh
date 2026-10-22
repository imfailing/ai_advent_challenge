#!/usr/bin/env bash
# Агентная задача на моделях (цикл с текстовым протоколом, защитой от повторов и терпимой заменой).
# MODELS можно задать переменной: MODELS="qwen3:8b gemma3:12b" ./run_agent_round.sh
cd "$(dirname "$0")"
PY="${PY:-python3}"; RUFF="${RUFF:-ruff}"
for m in ${MODELS:-qwen2.5-coder:7b qwen2.5-coder:14b deepseek-coder-v2:16b qwen3:8b gemma3:12b}; do
  "$PY" bench.py agent "$m" --ruff "$RUFF" 2>&1 | tail -2
done
