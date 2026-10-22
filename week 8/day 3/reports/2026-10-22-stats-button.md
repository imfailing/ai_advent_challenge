# Отчёт проверки: кнопка «📊 Статистика» (UI поверх /stats)
Вердикт: ✅ можно мержить

## Изменения (что затронуто)
Единственное отличие от базы (diff с base3/day3): `templates/index.html` — кнопка `#stats-btn`, блок `#stats-box`, JS `stats()`
(POST `/stats`, рендер `#stats-authors`, `#stats-days`, `#stats-busiest`, статус «Статистика · <repo> · коммитов: N»).
Бэкенд `/stats` и `activity.py` уже были (покрыты `test_stats.py`); остальные новые файлы — только тесты.

## Обновление сценариев
- Добавлен `S6` в `smoke/SCENARIOS.md` (3 шага: пустой репозиторий -> ошибка; успех octo/demo без ключа DeepSeek, проверка авторов/дней/самого активного дня, `#out` не тронут; `ghost/none` -> ошибка и скрытие `#stats-box`).
- Существующие S1–S5 не менялись: их ожидания не затронуты (изменение только добавило элементы). `smoke_server.py` менять не пришлось: заглушка `fake_get_commits` уже даёт Ann×2/Bob×1 и 2 дня.

## Уровень 1 — код-тесты: 5 PASS / 0 FAIL, ruff: All checks passed!, ~0.8 с
test_github_repo 8, test_notify 5, test_digest_unit 6, test_app_routes 7, test_stats 7. Новых тестов не потребовалось
(логика `/stats` покрыта `test_stats.py`). Интеграционный `test_digest.py` не запускался (сеть/ключ).

## Уровень 2 — UI smoke: 6 сценариев — 6 PASS / 0 FAIL
| Сценарий | Результат | Скриншоты (`smoke/screenshots/`) |
|---|---|---|
| S1 валидация | PASS | S1_01_initial, S1_02_empty_repo, S1_03_no_key |
| S2 успешный анализ | PASS | S2_02_form, S2_03_result |
| S3 ошибки | PASS | S3_01_not_found, S3_02_ai_error |
| S4 Telegram | PASS | S4_01_result, S4_02_no_tg, S4_03_published |
| S5 токены | PASS | S5_01_entered, S5_02_after_reload, S5_03_cleared |
| S6 статистика (новый) | PASS | S6_01_initial, S6_02_empty_repo, S6_03_result, S6_04_not_found |

## Что упало
Ничего.

## Не проверено / замечания
- Реальные GitHub/DeepSeek/Telegram, мобильная вёрстка, интеграционный `test_digest.py`.
- S1–S5 проверены по DOM через JS (значения полей и клики через `.click()`), нативные клики мышью — только в S6; визуальная проверка нативным скриншотом — по финальному состоянию S6.
- Ошибки консоли (400/500) — ожидаемые ответы сценариев ошибок.
