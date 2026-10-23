| Задача | Профиль | Результат | Старт | Конец | Заметка |
|---|---|---|---|---|---|
| T01 | bug-fix | done | 1792761161 | 1792761176 | _json_body() в app.py: null/не-объект -> {}; тест test_null_body.py |
| T02 | bug-fix | done | 1792761182 | 1792761197 | get_commits: проверка isinstance(list) -> RuntimeError про GitHub; тест в test_github_repo.py |
| T03 | bug-fix | done | 1792761197 | 1792761205 | get_commits: URLError/TimeoutError -> RuntimeError «Не удалось связаться с GitHub: …»; тест |
| T04 | bug-fix | done | 1792761208 | 1792761214 | digest.generate: период «нет дат» вместо пустого; обновлён test_digest_unit.py (старый assert фиксировал баг) |
| T05 | bug-fix | done | 1792761224 | 1792761229 | notify: при HTTP 400 «can't parse entities» повтор без parse_mode (_post/_error_body); тесты |
| T06 | feature | done | 1792761229 | 1792761256 | параметр top в /stats (1..20, дефолт 5), activity.compute_stats(top=); тесты |
| T07 | feature | done | 1792761261 | 1792761262 | first_date/last_date в compute_stats и /stats; тест |
| T08 | feature | done | 1792761269 | 1792761275 | фильтр author в /stats и activity.compute_stats; тесты |
| T09 | feature | done | 1792761285 | 1792761291 | parse_repo: regex понимает /tree,/issues,/pull,?,#,/,.git; тесты |
| T10 | feature | done | 1792761305 | 1792761311 | новый ratelimit.py (скользящее окно по IP), 429 JSON в /generate; test_ratelimit.py. Лимит per-process (при нескольких workers gunicorn не общий) |
| T11 | refactor | done | 1792761311 | 1792761325 | _clamped_int() в app.py — единственное приведение к int для last/top; поведение прежнее |
| T13 | refactor | done | 1792761325 | 1792761339 | _load_commits() в app.py используется /generate и /stats; get_commits( в app.py — 1 раз |
| T12 | refactor | done | 1792761339 | 1792761345 | SYSTEM_NEUTRAL/SYSTEM_TOXIC вынесены в prompts.py, digest их импортирует |
| T14 | tester | done | 1792761346 | 1792761377 | test_activity.py: 7 проверок (пусто, ничьи, без даты/автора, top, author) |
| T15 | tester | done | 1792761377 | 1792761395 | test_stats_bounds.py: 9 проверок last (0,1,100,101,'7','abc',-5, без last, JSON-ошибка) |
| T16 | docs-sync | done | 1792761395 | 1792761406 | README: curl для /generate и /publish с реалистичным телом (токены — плейсхолдеры) |
| T17 | docs-sync | done | 1792761406 | 1792761426 | добавлены русские docstring 9 функциям (app, digest, github_repo, notify); проверено ast-скриптом |
| T18 | docs-sync | done | 1792761426 | 1792761433 | README: раздел «Ограничения и особенности» (5 пунктов) |
