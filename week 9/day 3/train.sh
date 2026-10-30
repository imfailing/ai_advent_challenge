#!/usr/bin/env bash
# Воспроизведение дня 8. Обучение и eval — на сервере с ROCm (окружение ~/ft-env, см. week 9/day 1/train.sh).
# Адаптеры дней 6 и 7 берутся из ../day 1/adapters и ../day 2/adapters (в git не хранятся).
set -euo pipefail

python facts.py                    # 40 выдуманных фактов → data/facts*.jsonl
python test_day3.py                # офлайн-проверка наборов и автопроверок

source ~/ft-env/bin/activate

# 1. Знания: база / база+факты в промпте / тюн / тюн+факты
python eval_knowledge.py base
python eval_knowledge.py base_facts
python train_lora.py --train data/facts_train.jsonl --valid data/facts_valid.jsonl \
    --out runs/facts --epochs 8 --batch 8 --lr 2e-4 --eval-steps 10 --max-len 128   # ~36 с
python eval_knowledge.py tuned runs/facts/final
python eval_knowledge.py tuned_facts runs/facts/final

# 2. Потери: 40 задач вне домена на базе и на трёх адаптерах
python eval_ood.py base
python eval_ood.py commit "../day 2/adapters"
python eval_ood.py pirate "../day 1/adapters"
python eval_ood.py facts runs/facts/final

# 3. Переобучение: 300 примеров дня 7, 15 эпох, чекпоинты каждые 20 шагов (~15 мин)
python train_lora.py --train "../day 2/data/train.jsonl" --valid "../day 2/data/valid.jsonl" \
    --out runs/overfit --epochs 15 --batch 16 --lr 2e-4 --limit 300 --eval-steps 10 --save-steps 20
for s in 20 60 140 285; do python eval_overfit.py ckpt$s runs/overfit/ckpt/checkpoint-$s; done
python eval_ood.py ckpt60 runs/overfit/ckpt/checkpoint-60
python eval_ood.py ckpt285 runs/overfit/ckpt/checkpoint-285

# 4. Стиль: база / база+промпт / тюн дня 6
python eval_style.py base
python eval_style.py base_prompt
python eval_style.py tuned "../day 1/adapters"
