# Week 9 / Day 2 — свой датасет: классификация git-коммита в JSON

Датасет из 48 репозиториев с Conventional Commits, LoRA-тюн Qwen2.5-1.5B, сравнение с промптингом.
Итоги и таблицы — [REPORT.md](REPORT.md): tuned 69,2 % против 26,9 % у базы с промптом на 104 коммитах.

| Файл | Что |
|---|---|
| `collect.py` | сбор коммитов через `github_repo.get_commits`, метка из префикса → `data/raw.jsonl` |
| `build_dataset.py` | чистка тела, удаление ручного `removed.json`, дедупликация, сплит по репозиториям, баланс |
| `github_repo.py` | копия клиента GitHub REST из `week 8/day 1` (только чтение) |
| `test_dataset.py` | проверки датасета без сети: формат, утечки, баланс |
| `eval_model.py` | оценка `base_plain` / `base_prompt` / `tuned` → `out/eval_<режим>.json` |
| `train.py` | LoRA (peft + transformers Trainer), лучший чекпоинт по eval loss |
| `train.sh` | воспроизведение всего конвейера |
| `data/` | `raw`, `train`, `valid`, `eval`, `review_sample`, `removed.json` |
| `adapters/`, `out/` | адаптер (≈70 МБ, **не в git**, лежит на сервере), метрики и ответы; `out/v1/` — первый прогон |

## Запуск

Сбор и датасет — локально (нужен доступ к GitHub API, ≤60 запросов/час без токена):

```bash
cd "week 9/day 2" && python collect.py && python build_dataset.py && python test_dataset.py
```

Обучение и eval — на машине с GPU и PyTorch (в дне 6–7 — AMD Radeon 8060S, ROCm), см. `train.sh`:

```bash
python eval_model.py base_prompt && python train.py && python eval_model.py tuned
```

Пример ответа `tuned` на вход `Commit message:\nbump dependency x to 2.1`: `{"type": "chore"}`.
