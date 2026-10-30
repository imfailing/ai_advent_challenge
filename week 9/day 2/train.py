"""
LoRA-обучение Qwen2.5-1.5B-Instruct на датасете «классификация git-коммита в JSON» (bf16, ROCm).
Лосс считается только по ответу ассистента. Пишет out/loss_log.json, сохраняет адаптер в adapters/
и параметры/время в out/run_info.json.
"""

import json
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ROOT = Path(__file__).parent
ADAPTER_DIR = ROOT / "adapters"
OUT_DIR = ROOT / "out"
MAX_LEN = 384
CONFIG = {
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "learning_rate": 2e-4,
    "epochs": 3,
    "batch_size": 16,
    "seed": 42,
}


def load_jsonl(path: Path) -> list[dict]:
    """Прочитать jsonl-файл."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def encode(example: dict, tok: AutoTokenizer) -> dict:
    """Токенизировать диалог; токены промпта в labels маскируются значением -100."""
    user, assistant = example["messages"]
    prompt = tok.apply_chat_template(
        [user], tokenize=False, add_generation_prompt=True
    )
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    answer_ids = tok(assistant["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
    ids = (prompt_ids + answer_ids)[:MAX_LEN]
    labels = ([-100] * len(prompt_ids) + answer_ids)[:MAX_LEN]
    return {"input_ids": ids, "labels": labels}


class Collator:
    """Паддинг батча до максимальной длины."""

    def __init__(self, pad_id: int) -> None:
        self.pad_id = pad_id

    def __call__(self, batch: list[dict]) -> dict:
        n = max(len(b["input_ids"]) for b in batch)
        ids = [b["input_ids"] + [self.pad_id] * (n - len(b["input_ids"])) for b in batch]
        labels = [b["labels"] + [-100] * (n - len(b["labels"])) for b in batch]
        mask = [[1] * len(b["input_ids"]) + [0] * (n - len(b["input_ids"])) for b in batch]
        return {
            "input_ids": torch.tensor(ids),
            "labels": torch.tensor(labels),
            "attention_mask": torch.tensor(mask),
        }


class LossLogger(TrainerCallback):
    """Накапливает train/eval loss по шагам."""

    def __init__(self) -> None:
        self.log: list[dict] = []

    def on_log(self, args, state, control, logs=None, **kwargs) -> None:
        if logs and ("loss" in logs or "eval_loss" in logs):
            self.log.append({"step": state.global_step, **logs})


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.bfloat16)
    model = get_peft_model(model, LoraConfig(
        r=CONFIG["lora_r"], lora_alpha=CONFIG["lora_alpha"], lora_dropout=CONFIG["lora_dropout"],
        target_modules=CONFIG["target_modules"], task_type="CAUSAL_LM",
    ))
    model.print_trainable_parameters()

    train = [encode(e, tok) for e in load_jsonl(ROOT / "data" / "train.jsonl")]
    valid = [encode(e, tok) for e in load_jsonl(ROOT / "data" / "valid.jsonl")]
    OUT_DIR.mkdir(exist_ok=True)
    logger = LossLogger()
    args = TrainingArguments(
        output_dir=str(OUT_DIR / "ckpt"), num_train_epochs=CONFIG["epochs"],
        per_device_train_batch_size=CONFIG["batch_size"], per_device_eval_batch_size=16,
        learning_rate=CONFIG["learning_rate"], lr_scheduler_type="cosine", warmup_steps=15,
        bf16=True, logging_steps=5, eval_strategy="steps", eval_steps=25,
        save_strategy="no", report_to="none", seed=CONFIG["seed"],
        remove_unused_columns=False,
    )
    trainer = Trainer(model=model, args=args, train_dataset=train, eval_dataset=valid,
                      data_collator=Collator(tok.pad_token_id), callbacks=[logger])
    start = time.time()
    trainer.train()
    seconds = round(time.time() - start, 1)
    model.save_pretrained(ADAPTER_DIR)

    info = {
        "model": MODEL, "device": torch.cuda.get_device_name(0), "torch": torch.__version__,
        "train_examples": len(train), "valid_examples": len(valid), "max_len": MAX_LEN,
        "train_seconds": seconds,
        "peak_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        **CONFIG,
    }
    (OUT_DIR / "loss_log.json").write_text(json.dumps(logger.log, indent=1), encoding="utf-8")
    (OUT_DIR / "run_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))  # noqa: T201


if __name__ == "__main__":
    main()
