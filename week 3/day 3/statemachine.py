"""
Конечный автомат состояния задачи.

Этапы (stages):
    planning → execution → validation → done

Переходы:
    planning   → execution
    execution  → validation
    validation → execution   (нашли проблему — назад на доработку)
    validation → done        (всё хорошо — завершаем)
    done       → (терминальное состояние)

Состояние задачи описывается тройкой:
    • stage           — текущий этап (из STAGES)
    • current_step    — что делается прямо сейчас (человекочитаемо)
    • expected_action — какое действие ожидается следующим

Статус (status) ортогонален этапу:
    • active  — задача в работе
    • paused  — пауза (этап заморожен, продвижение запрещено)

Пауза возможна на ЛЮБОМ этапе и не меняет stage — при возобновлении
работа продолжается ровно с того места.
"""

STAGES = ["planning", "execution", "validation", "done"]

STAGE_LABELS = {
    "planning":   "Планирование",
    "execution":  "Выполнение",
    "validation": "Проверка",
    "done":       "Готово",
}

# Разрешённые переходы между этапами.
TRANSITIONS: dict[str, list[str]] = {
    "planning":   ["execution"],
    "execution":  ["validation"],
    "validation": ["execution", "done"],
    "done":       [],
}

STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"

INITIAL_STAGE = "planning"


def is_stage(value: str) -> bool:
    return value in STAGES


def can_transition(from_stage: str, to_stage: str) -> bool:
    """Допустим ли прямой переход from_stage → to_stage."""
    if from_stage == to_stage:
        return True  # «остаться на этапе» всегда допустимо
    return to_stage in TRANSITIONS.get(from_stage, [])


def next_stage(from_stage: str) -> str | None:
    """Следующий этап по основному (прямому) пути."""
    forward = {
        "planning":   "execution",
        "execution":  "validation",
        "validation": "done",
        "done":       None,
    }
    return forward.get(from_stage)


def is_terminal(stage: str) -> bool:
    return stage == "done"


def stage_index(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else -1
