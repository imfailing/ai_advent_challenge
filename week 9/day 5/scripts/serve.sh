#!/usr/bin/env bash
# Запуск llama-server для версий из registry/models.json (на сервере, GPU ROCm). Слушают только 127.0.0.1;
# с Mac доступны через SSH-туннель: ssh -fN -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 ft-server
# Использование: scripts/serve.sh start|stop|status
set -euo pipefail
MODELS="$HOME/models"
SERVER="$HOME/llm/llama/llama-server"
declare -A PORTS=( [8081]="base-Q8_0.gguf" [8082]="tuned-v1-Q8_0.gguf" [8083]="tuned-v1-Q4_K_M.gguf" )

case "${1:-status}" in
  start)
    for port in "${!PORTS[@]}"; do
      curl -sf "http://127.0.0.1:$port/health" >/dev/null && { echo "уже запущен: $port"; continue; }
      setsid nohup "$SERVER" -m "$MODELS/${PORTS[$port]}" --port "$port" -ngl 99 -c 4096 --no-webui \
        > "$HOME/models/serve-$port.log" 2>&1 < /dev/null &
    done ;;
  stop) pkill -f "llama-server -m $MODELS" || true ;;
  status)
    for port in "${!PORTS[@]}"; do
      curl -sf "http://127.0.0.1:$port/health" >/dev/null && echo "$port ${PORTS[$port]}: ok" || echo "$port ${PORTS[$port]}: нет"
    done ;;
esac
