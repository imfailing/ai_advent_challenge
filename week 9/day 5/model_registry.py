"""
Реестр моделей и переключатель активной модели без перезапуска сервиса.

`registry/models.json` — каталог версий (в git), `registry/state.json` — какая версия активна и стек предыдущих
для отката, `registry/verified.json` — записи о пройденной проверке перед выкаткой. Переключение — атомарная
запись state.json под блокировкой; процесс сервиса читает файл на каждый запрос, поэтому подмена мгновенна.
Без Flask и без сети (кроме проверки /health у llama-server).
"""

import json
import os
import threading
from pathlib import Path

import llm_client

REGISTRY_DIR = Path(__file__).parent / "registry"
DEFAULT_ACTIVE = "deepseek-v4-flash"
_lock = threading.Lock()


def _read(name: str, default: dict) -> dict:
    path = REGISTRY_DIR / name
    return json.loads(path.read_text("utf-8")) if path.exists() else default


def _write(name: str, data: dict) -> None:
    """Атомарная запись: во временный файл, затем rename."""
    path = REGISTRY_DIR / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def models() -> dict[str, dict]:
    """Каталог моделей: id → описание."""
    return _read("models.json", {})


def state() -> dict:
    """{'active': id, 'history': [id, ...]} — активная версия и стек для отката."""
    return _read("state.json", {"active": DEFAULT_ACTIVE, "history": []})


def active_id() -> str:
    """Идентификатор активной модели."""
    return state()["active"]


def get(model_id: str) -> dict:
    """Описание модели по id; ValueError, если такой нет."""
    catalog = models()
    if model_id not in catalog:
        raise ValueError(f"Неизвестная модель: {model_id}")
    return {"id": model_id, **catalog[model_id]}


def active() -> dict:
    """Описание активной модели."""
    return get(active_id())


def verified(model_id: str) -> dict | None:
    """Запись о проверке перед выкаткой (или None)."""
    return _read("verified.json", {}).get(model_id)


def record_verification(model_id: str, record: dict) -> None:
    """Сохранить результат проверки модели (читается при активации)."""
    with _lock:
        data = _read("verified.json", {})
        data[model_id] = record
        _write("verified.json", data)


def activate(model_id: str, force: bool = False) -> dict:
    """Сделать модель активной. Без force требуется пройденная проверка и живой llama-server.

    Прежняя активная версия кладётся в стек отката. ValueError — модель нельзя включать (текст по-русски).
    """
    model = get(model_id)
    if not force:
        record = verified(model_id)
        if model["kind"] != "deepseek" and not (record and record.get("passed")):
            raise ValueError(f"Модель {model_id} не прошла проверку перед выкаткой (scripts/verify_model.py).")
        if model["kind"] == "llama" and not llm_client.is_healthy(model["url"]):
            raise ValueError(f"Сервер модели {model_id} не отвечает ({model['url']}).")
    with _lock:
        st = state()
        if st["active"] != model_id:
            st = {"active": model_id, "history": [*st["history"], st["active"]][-10:]}
            _write("state.json", st)
    return st


def rollback() -> dict:
    """Вернуть предыдущую активную версию (из стека); ValueError, если откатываться некуда."""
    with _lock:
        st = state()
        if not st["history"]:
            raise ValueError("Нет предыдущей версии для отката.")
        st = {"active": st["history"][-1], "history": st["history"][:-1]}
        _write("state.json", st)
    return st
