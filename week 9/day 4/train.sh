#!/usr/bin/env bash
# Воспроизведение дня 9. Данные/учитель — локально (нужен DEEPSEEK_API_KEY), обучение и ученик — на сервере с ROCm.
set -euo pipefail

# --- локально ---
# python gen_emails.py 800            # письма под случайные задания (учитель пишет тексты)
# python build_split.py               # чистка, дедупликация, тест 100 / пул
# python label_teacher.py test        # ответы учителя на тест
# python label_teacher.py pool        # ответы учителя на пул (материал для обучения)
# python review_test.py               # ручная правка эталона → data/test_final.jsonl (80)
# python build_train.py               # фильтр ответов учителя → data/train.jsonl, valid.jsonl

# --- на сервере ---
source ~/ft-env/bin/activate
python eval_student.py base                                    # ученик до обучения
python train_lora.py --train data/train.jsonl --valid data/valid.jsonl --out runs/student \
    --epochs 3 --batch 8 --lr 2e-4 --eval-steps 20 --max-len 768
python eval_student.py tuned runs/student/final                # ученик после обучения
