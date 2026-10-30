#!/usr/bin/env bash
# Воспроизведение дня 7: сбор данных → датасет → базовая линия → LoRA → сравнение.
# Обучение и eval — на сервере 192.168.1.4 (AMD Radeon 8060S gfx1151, ROCm 7.13), окружение ~/ft-env
# (см. week 9/day 1/train.sh). Сбор данных (шаги 1–2) — локально, нужен только доступ к GitHub API.
set -euo pipefail

python collect.py          # data/raw.jsonl (48 репозиториев × ≤100 коммитов, метка из префикса)
python build_dataset.py    # train/valid/eval.jsonl: дедупликация, eval по репозиториям, баланс
python test_dataset.py     # формат, утечка, баланс

source ~/ft-env/bin/activate
python eval_model.py base_plain    # база без инструкций
python eval_model.py base_prompt   # база + проработанный промпт
python train.py                    # ~10 мин, адаптер → adapters/, логи → out/
python eval_model.py tuned         # дообученная модель, вход как в base_plain
