# Week 8 / Day 5 — Execution Loop

Пул из 18 задач, автономный цикл «взять → выполнить → закоммитить → следующая», независимая проверка и сравнение облака с локальной моделью.
Итоги — [REPORT.md](REPORT.md).

| Путь | Что |
|---|---|
| `TASKS.md` | пул задач (трекер): тип, описание, критерий «сделано» |
| `fixtures/base/` | исходное состояние проекта для песочницы |
| `harness/make_sandbox.sh` | создаёт песочницу (проект + правила + профили + пул) как отдельный git-репозиторий |
| `harness/LOOP.md` | инструкция цикла для ассистента |
| `harness/verify/check.py` | скрытые проверки критериев (T01–T18) |
| `harness/verify_run.py` | независимая проверка прогона по истории git: критерий + ruff + тесты на каждом коммите и на HEAD |
| `harness/local_loop.py` | тот же цикл на локальной модели (Ollama), протоколы v1/v2 |
| `runs/` | логи прогонов: `run1_cloud`, `run2_cloud`, `run3_local_v1`, `run4_local_v2` (verification, git-log, LOG, final.diff) |

Воспроизведение (из корня репозитория; пути к python/ruff — в `CLAUDE.local.md`):
```bash
"week 8/day 5/harness/make_sandbox.sh" /tmp/loop_demo
python "week 8/day 5/harness/verify_run.py" /tmp/loop_demo /tmp/loop_demo_out --python <python3.13> --ruff <ruff>
```
