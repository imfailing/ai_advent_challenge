# Неделя 9, день 4 — дистилляция: учитель (DeepSeek) → ученик (Qwen2.5-1.5B + LoRA)

Письмо клиента → JSON (`category`, `sentiment`, `product`, `order_id`, `amount_rub`, `action_required`, `summary`).
Результаты и выводы — в [REPORT.md](REPORT.md). Адаптер (~70 МБ) лежит на сервере `runs/student/final`, в git не хранится.

## Модули
| Файл | Роль |
|---|---|
| `schema.py` | поля, допустимые значения, промпт задачи, разбор и проверка ответа, точность по полям |
| `teacher.py` | клиент DeepSeek на urllib: вызов с замером токенов/времени, параллельный прогон |
| `gen_emails.py` | генерация писем учителем под случайные «задания» (эталон по построению) |
| `build_split.py` | чистка, дедупликация, разбиение на тест (100) и пул |
| `label_teacher.py` | ответы учителя на тест и пул → `out/teacher_*.json` |
| `review_test.py` | ручная правка эталона теста → `data/test_final.jsonl` (80) |
| `build_train.py` | фильтр ответов учителя → `data/train.jsonl`, `valid.jsonl`, `train_stats.json` |
| `train_lora.py`, `common.py` | LoRA-обучение (с system-сообщением) и загрузка модели/замер задержки |
| `eval_student.py` | прогон ученика на тесте с задержкой каждого запроса (`MERGE=1` — слить адаптер) |
| `compare.py` | сравнение трёх вариантов: качество, скорость, стоимость → `out/compare.json` |
| `test_day4.py` | офлайн-проверка схемы, фильтра, наборов и метрик |
| `train.sh` | порядок запуска |

## Запуск
```bash
export DEEPSEEK_API_KEY=...        # только для gen_emails.py и label_teacher.py
python gen_emails.py 800 && python build_split.py && python label_teacher.py test && python label_teacher.py pool
python review_test.py && python build_train.py && python test_day4.py
# на сервере с ROCm:  ./train.sh   (затем MERGE=1 python eval_student.py tuned_merged runs/student/final)
python compare.py
```

## Результат (тест 80 писем)
Все 6 полей верны: ученик до 26,3% → после 86,3%, учитель 88,7%. Задержка: 3,0 с против 1,2 с у API.
Цена запроса: ≈ $0,0000084 (энергия, допущение) против $0,000085 (API).
