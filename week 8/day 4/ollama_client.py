"""
Клиент локального Ollama (только stdlib) с замером скорости.

chat() возвращает текст/вызовы инструментов и метрики: время до первого токена,
токены/с генерации, токены промпта — из служебных полей Ollama (prompt_eval_count, eval_count, *_duration).
"""

import json
import time
import urllib.request

HOST = "http://localhost:11434"


def chat(model: str, messages: list[dict], options: dict | None = None,
         tools: list[dict] | None = None, timeout: int = 600) -> dict:
    """Один запрос /api/chat (stream=false). options — temperature, top_p, num_ctx, num_predict…"""
    body: dict = {"model": model, "messages": messages, "stream": False,
                  "options": options or {}, "keep_alive": "10m"}
    if tools:
        body["tools"] = tools
    if "qwen3" in model or "deepseek-r1" in model:
        body["think"] = False   # без цепочки рассуждений: сравниваем на равных, скорость честная
    req = urllib.request.Request(f"{HOST}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    wall = time.perf_counter() - t0
    ev, ev_dur = data.get("eval_count", 0), data.get("eval_duration", 0) or 1
    pe, pe_dur = data.get("prompt_eval_count", 0), data.get("prompt_eval_duration", 0) or 1
    return {
        "message": data["message"],
        "wall_s": round(wall, 2),
        "prompt_tokens": pe,
        "gen_tokens": ev,
        "gen_tps": round(ev / (ev_dur / 1e9), 1),          # скорость генерации, ток/с
        "prefill_tps": round(pe / (pe_dur / 1e9), 1),      # скорость чтения промпта, ток/с
        "load_s": round(data.get("load_duration", 0) / 1e9, 2),
        "ttft_s": round((data.get("load_duration", 0) + pe_dur) / 1e9, 2),  # до первого токена
    }
