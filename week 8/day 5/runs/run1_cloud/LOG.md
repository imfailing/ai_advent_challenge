| Задача | Профиль | Результат | Старт | Конец | Заметка |
|---|---|---|---|---|---|
| T01 | bug-fix | done | 1792760384 | 1792760397 | generate: get_json(force=True) or {}; тест на null для 3 маршрутов |
| T02 | bug-fix | done | 1792760403 | 1792760414 | get_commits: не-список -> RuntimeError про GitHub |
| T03 | bug-fix | done | 1792760414 | 1792760415 | URLError/TimeoutError -> RuntimeError «Не удалось связаться с GitHub» |
| T04 | bug-fix | done | 1792760423 | 1792760424 | пустой период -> «нет дат»; обновлён тест, фиксировавший баг |
| T05 | bug-fix | done | 1792760424 | 1792760455 | send_telegram: при 400 can't parse entities повтор без parse_mode |
| T06 | feature | done | 1792760455 | 1792760478 | top в /stats: дефолт 5, кламп 1..20, нечисловой -> 400 |
| T07 | feature | done | 1792760478 | 1792760487 |first_date/last_date в compute_stats (None без дат) |
| T08 | feature | done | 1792760487 | 1792760495 |фильтр author в /stats и compute_stats |
| T09 | feature | done | 1792760495 | 1792760505 |regex parse_repo допускает хвост /… ?… #… |
| T10 | feature | done | 1792760505 | 1792760525 |ratelimit.py (скользящее окно по IP), 429 на 11-й запрос /generate, test_ratelimit.py |
| T11 | refactor | done | 1792760525 | 1792760540 |_int_param — единственное место int() для last/top |
| T12 | refactor | done | 1792760540 | 1792760549 |SYSTEM_* перенесены в prompts.py |
| T13 | refactor | done | 1792760549 | 1792760564 |_load_commits в app.py, один вызов get_commits |
| T14 | test | done | 1792760564 | 1792760585 |test_activity.py, 8 проверок |
| T15 | test | done | 1792760585 | 1792760591 |test_stats_bounds.py, 8 проверок last |
| T16 | docs | done | 1792760591 | 1792760604 |curl для /generate и /publish; синхронизированы таблица API и список модулей |
| T17 | docs | done | 1792760604 | 1792760631 |docstring в 9 функций (app/digest/github_repo/notify), проверено ast-скриптом |
| T18 | docs | done | 1792760631 | 1792760631 | раздел «Ограничения и особенности», 5 пунктов |

