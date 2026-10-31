#!/usr/bin/env bash
# Воспроизведение дня 6: данные → LoRA-обучение → сравнение на 20 запросах.
# Запускалось на сервере 192.168.1.4 (AMD Ryzen AI Max+ 395, Radeon 8060S gfx1151, ROCm 7.13).
# Параметры обучения зафиксированы в train.py (CONFIG) и в out/run_info.json.
set -euo pipefail

# окружение: uv venv --python 3.12 ~/llm-env
# uv pip install --index-url https://repo.amd.com/rocm/whl/gfx1151/ torch torchvision torchaudio
# uv pip install transformers peft trl datasets accelerate
source ~/llm-env/bin/activate

python prepare_data.py     # data/train.jsonl (2000), data/valid.jsonl (100)
python train.py            # ~22 мин, адаптер → adapters/, логи → out/
python eval_compare.py     # 20 запросов, база vs тюн → out/results.json
