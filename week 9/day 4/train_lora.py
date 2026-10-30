"""
LoRA-обучение Qwen2.5-1.5B-Instruct на jsonl в формате messages ([system →] user → assistant); копия day 3 с поддержкой system.
Лосс — только по ответу ассистента. Логирует train/eval loss по шагам в <out>/loss_log.json,
сохраняет чекпоинты (адаптеры) каждые --save-steps шагов и финальный адаптер в <out>/final.
Пример: python train_lora.py --train data/facts_train.jsonl --valid data/facts_train.jsonl --out runs/facts
"""

import argparse
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
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    """Прочитать jsonl (первые limit строк)."""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [json.loads(line) for line in lines[:limit]]


def encode(example: dict, tok: AutoTokenizer, max_len: int) -> dict:
    """Токенизировать диалог; токены промпта (system + user) в labels маскируются значением -100."""
    *context, assistant = example["messages"]
    prompt = tok.apply_chat_template(context, tokenize=False, add_generation_prompt=True)
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    answer_ids = tok(assistant["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
    return {
        "input_ids": (prompt_ids + answer_ids)[:max_len],
        "labels": ([-100] * len(prompt_ids) + answer_ids)[:max_len],
    }


class Collator:
    """Паддинг батча до максимальной длины."""

    def __init__(self, pad_id: int) -> None:
        self.pad_id = pad_id

    def __call__(self, batch: list[dict]) -> dict:
        n = max(len(b["input_ids"]) for b in batch)
        pad = [n - len(b["input_ids"]) for b in batch]
        return {
            "input_ids": torch.tensor([b["input_ids"] + [self.pad_id] * p for b, p in zip(batch, pad, strict=True)]),
            "labels": torch.tensor([b["labels"] + [-100] * p for b, p in zip(batch, pad, strict=True)]),
            "attention_mask": torch.tensor([[1] * len(b["input_ids"]) + [0] * p
                                            for b, p in zip(batch, pad, strict=True)]),
        }


class LossLogger(TrainerCallback):
    """Накапливает train/eval loss по шагам."""

    def __init__(self) -> None:
        self.log: list[dict] = []

    def on_log(self, args, state, control, logs=None, **kwargs) -> None:
        if logs and ("loss" in logs or "eval_loss" in logs):
            self.log.append({"step": state.global_step, **logs})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--valid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=768)
    ap.add_argument("--limit", type=int, default=None, help="взять первые N обучающих примеров")
    ap.add_argument("--eval-steps", type=int, default=25)
    ap.add_argument("--save-steps", type=int, default=0, help="0 — чекпоинты не сохранять")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16)
    model = get_peft_model(model, LoraConfig(
        r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05,
        target_modules=TARGETS, task_type="CAUSAL_LM",
    ))
    train = [encode(e, tok, args.max_len) for e in load_jsonl(Path(args.train), args.limit)]
    valid = [encode(e, tok, args.max_len) for e in load_jsonl(Path(args.valid))]
    logger = LossLogger()
    targs = TrainingArguments(
        output_dir=str(out / "ckpt"), num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch, per_device_eval_batch_size=args.batch,
        learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=10, bf16=True,
        logging_steps=5, eval_strategy="steps", eval_steps=args.eval_steps,
        save_strategy="steps" if args.save_steps else "no", save_steps=args.save_steps or 500,
        save_total_limit=None, report_to="none", seed=args.seed, remove_unused_columns=False,
    )
    trainer = Trainer(model=model, args=targs, train_dataset=train, eval_dataset=valid,
                      data_collator=Collator(tok.pad_token_id), callbacks=[logger])
    start = time.time()
    trainer.train()
    seconds = round(time.time() - start, 1)
    model.save_pretrained(out / "final")
    info = {
        "train_examples": len(train), "valid_examples": len(valid), "train_seconds": seconds,
        "peak_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "device": torch.cuda.get_device_name(0), "torch": torch.__version__, **vars(args),
    }
    (out / "loss_log.json").write_text(json.dumps(logger.log, indent=1), encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info))  # noqa: T201


if __name__ == "__main__":
    main()
