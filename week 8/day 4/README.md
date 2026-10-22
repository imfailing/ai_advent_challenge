# Week 8 / Day 4 — Local Boost: локальная LLM как код-ассистент

Ollama + Continue.dev в VS Code, правила Дня 1 в системном промпте, сравнение с облачным ассистентом.
Итоги и таблицы — [REPORT.md](REPORT.md).

| Путь | Что |
|---|---|
| `continue/config.yaml` | конфиг Continue (копия в `~/.continue/config.yaml`): чат 14b/7b, автокомплит 1.5b, эмбеддинги, правила в системном промпте |
| `rules_local.md` | сжатая версия `CLAUDE.md` для локальных моделей |
| `ollama_client.py`, `sandbox.py` | клиент Ollama с замером скорости; песочница (python/ruff/тесты) |
| `task_feature.py`, `task_agent.py`, `bench.py` | задача 1 (генерация фичи) и задача 2 (агентный Bug Fix), прогон |
| `run_matrix.sh`, `run_agent_round.sh`, `run_tuning.sh`, `run_repeats.sh` | воспроизведение замеров (`PY=<python3.13> RUFF=<ruff>`) |
| `autocomplete_probe.py` | замер FIM-автокомплита |
| `fixtures/` | исходные состояния проекта для задач |
| `results/` | JSON всех прогонов (+ `round1…round4_agent_*` — раунды агентной задачи) |
