# Неделя 9, день 5 (день 10) — тюненая модель в сервисе недели 8

Сервис `week 8/day 1` (дайджест/статистика GitHub-репозитория) + классификация типа коммита локальной тюненой
моделью (GGUF под llama-server) и переключение версий моделей без перезапуска. Замеры и сравнение — [REPORT.md](REPORT.md),
регламент выкатки и отката — [ROLLOUT.md](ROLLOUT.md). Порт сервиса 5012 (`PORT`). GGUF и адаптеры в git не хранятся.

## Модули
| Файл | Роль |
|---|---|
| `app.py` | маршруты (из дня 8 + `/classify`, `/models`, `/models/activate`, `/models/rollback`) |
| `activity.py`, `digest.py`, `github_repo.py`, `notify.py` | без изменений (копия `week 8/day 1`) |
| `commit_types.py` | типы, промпты (`plain`/`prompt`), разбор ответа, метрики |
| `llm_client.py` | HTTP-клиент OpenAI-совместимого API (llama-server и DeepSeek), `is_healthy` |
| `classifier.py` | классификация коммитов выбранной моделью |
| `model_registry.py` | каталог версий, активная версия, стек отката, записи о проверке |
| `verification.py` | проверка модели перед выкаткой: прогон `data/eval.jsonl` и вердикт по порогам |
| `registry/models.json` | каталог версий (id, URL, режим, sha256) |
| `scripts/` | `merge_adapter.py`, `bench_gguf.py`, `serve.sh`, `verify_model.py`, `compare_live.py` |
| `test_day5.py`, `test_stats.py` | офлайн-проверки (без сети и моделей) |
| `out/` | замеры (`bench_*.json`) и сравнение на живых репозиториях (`live_compare.json`) |

## Эндпоинты
| Метод и путь | Что делает |
|---|---|
| `POST /classify` | тип коммитов репозитория (`repo`, `last`) или одного сообщения (`message`); `model` — разово другая версия |
| `GET /models` | версии, активная, онлайн ли, проверена ли |
| `POST /models/activate` | включить версию (нужна пройденная проверка и живой сервер модели) |
| `POST /models/rollback` | вернуть предыдущую активную версию |
| `/generate`, `/stats`, `/publish`, `/health` | как в дне 8 |

```bash
curl -X POST localhost:5012/classify -H 'Content-Type: application/json' \
     -d '{"message": "cache compiled templates to speed up rendering"}'
# {"model": "tuned-v1", "seconds": 0.11, "type": "perf"}
curl -X POST localhost:5012/models/activate -H 'Content-Type: application/json' -d '{"id": "tuned-v1"}'
# {"active": "tuned-v1", "history": ["deepseek-v4-flash"]}
curl -X POST localhost:5012/models/rollback
# {"active": "deepseek-v4-flash", "history": []}
```

## Запуск
```bash
# сервер: scripts/serve.sh start;  Mac: ssh -fN -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082 -L 8083:127.0.0.1:8083 ft-server
PORT=5012 python app.py
python scripts/verify_model.py tuned-v1       # проверка перед выкаткой, затем POST /models/activate
python test_day5.py
```
