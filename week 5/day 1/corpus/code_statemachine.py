"""
Конечный автомат жизненного цикла задачи с ЯВНЫМИ переходами и ГЕЙТАМИ.

В отличие от простого автомата (day 3), здесь каждый переход защищён
условиями (gates), которые должны быть выполнены. Это не даёт «перепрыгнуть»
этап.

Этапы:
    planning → execution → validation → done

Переходы и их условия:
    planning   → execution    требует: план утверждён (plan_approved)
    execution  → validation    требует: реализация завершена (implementation_done)
    validation → execution     (возврат на доработку — без условий)
    validation → done          требует: валидация пройдена (validation_passed)

Любой другой переход (например planning → done или planning → validation)
НЕ существует в таблице переходов и отклоняется как «перепрыгивание этапа».
"""

STAGES = ["planning", "execution", "validation", "done"]

STAGE_LABELS = {
    "planning":   "Планирование",
    "execution":  "Выполнение",
    "validation": "Проверка",
    "done":       "Готово",
}

# Условия-гейты: какие булевы флаги должны быть выставлены.
GATES = {
    "plan_approved":       "План утверждён",
    "implementation_done": "Реализация завершена",
    "validation_passed":   "Валидация пройдена",
}

# Разрешённые переходы: (откуда, куда) -> список требуемых гейтов.
TRANSITIONS: dict[tuple[str, str], list[str]] = {
    ("planning",   "execution"):  ["plan_approved"],
    ("execution",  "validation"): ["implementation_done"],
    ("validation", "execution"):  [],                       # назад на доработку
    ("validation", "done"):       ["validation_passed"],
}

STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"
INITIAL_STAGE = "planning"


def is_stage(value: str) -> bool:
    return value in STAGES


def allowed_targets(stage: str) -> list[str]:
    """Все этапы, в которые в принципе можно перейти из stage."""
    return [to for (frm, to) in TRANSITIONS if frm == stage]


def check_transition(from_stage: str, to_stage: str,
                     conditions: dict) -> tuple[bool, str]:
    """
    Можно ли перейти from_stage → to_stage при текущих conditions.
    Возвращает (разрешено, причина_отказа).
    """
    if from_stage == to_stage:
        return True, ""

    key = (from_stage, to_stage)
    if key not in TRANSITIONS:
        # перехода нет в таблице — это «перепрыгивание этапа»
        targets = allowed_targets(from_stage)
        allowed = ", ".join(STAGE_LABELS.get(t, t) for t in targets) or "нет"
        return False, (
            f"переход «{STAGE_LABELS.get(from_stage, from_stage)}» → "
            f"«{STAGE_LABELS.get(to_stage, to_stage)}» не существует "
            f"(нельзя перепрыгивать этапы). Доступно из текущего этапа: {allowed}"
        )

    missing = [g for g in TRANSITIONS[key] if not conditions.get(g)]
    if missing:
        names = ", ".join(GATES[g] for g in missing)
        return False, f"не выполнены условия перехода: {names}"

    return True, ""


def missing_gates(from_stage: str, to_stage: str, conditions: dict) -> list[str]:
    """Список невыполненных гейтов для перехода (пусто, если переход валиден/без гейтов)."""
    key = (from_stage, to_stage)
    if key not in TRANSITIONS:
        return []
    return [g for g in TRANSITIONS[key] if not conditions.get(g)]


def is_terminal(stage: str) -> bool:
    return stage == "done"


def stage_index(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else -1
