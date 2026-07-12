"""
Мини-набор из 10 контрольных вопросов по базе документов (corpus/).

Для каждого вопроса зафиксировано:
  question         — сам вопрос;
  expected         — ключевые факты, которые ДОЛЖНЫ быть в ответе
                     (проверяем вхождение, регистронезависимо);
  expected_sources — файлы, которые должны быть среди найденных чанков
                     (recall засчитывается, если найден хотя бы один);
  note             — что именно проверяем.

Вопросы намеренно про специфику ЭТОГО проекта — базовая модель без RAG
их знать не может, а с RAG (по корпусу) должна отвечать точно.
"""

EVAL = [
    {
        "question": "Какие три стратегии управления контекстом реализованы?",
        "expected": ["sliding window", "sticky facts", "branching"],
        "expected_sources": ["article_context_strategies.md", "code_context_agent.py"],
        "note": "перечислить все три стратегии",
    },
    {
        "question": "Что должно быть выполнено, чтобы перейти с этапа planning на execution в жизненном цикле задачи?",
        "expected": ["plan_approved", "план"],
        "expected_sources": ["code_statemachine.py", "article_task_lifecycle.md"],
        "note": "гейт plan_approved / утверждённый план",
    },
    {
        "question": "Назови три слоя памяти ассистента.",
        "expected": ["краткосрочная", "рабочая", "долговременная"],
        "expected_sources": ["article_memory_layers.md"],
        "note": "три типа памяти",
    },
    {
        "question": "Какой транспорт использует MCP при локальном запуске сервера?",
        "expected": ["stdio"],
        "expected_sources": ["code_mcp_server.py", "article_rag_overview.pdf"],
        "note": "транспорт stdio",
    },
    {
        "question": "Что делает инструмент save_to_file в MCP-пайплайне?",
        "expected": ["сохран", "файл"],
        "expected_sources": ["article_mcp_pipeline.md"],
        "note": "сохраняет результат (сводку) в файл",
    },
    {
        "question": "Какие категории инвариантов есть у ассистента?",
        "expected": ["архитектур", "стек", "бизнес"],
        "expected_sources": ["code_invariant_agent.py"],
        "note": "архитектура / техническое решение / стек / бизнес-правило",
    },
    {
        "question": "Что делает фоновый планировщик Scheduler на каждом тике?",
        "expected": ["метрик", "напомина", "сводк"],
        "expected_sources": ["code_scheduler.py", "code_store.py"],
        "note": "сбор метрики, напоминания, снапшот сводки",
    },
    {
        "question": "Из чего складывается стоимость запроса к модели?",
        "expected": ["токен", "стоимост"],
        "expected_sources": ["article_tokens_files.md"],
        "note": "входные/выходные токены × тариф",
    },
    {
        "question": "Что происходит при попытке перепрыгнуть этап задачи (например planning → done)?",
        "expected": ["отклон", "перепрыг"],
        "expected_sources": ["code_statemachine.py", "article_task_lifecycle.md"],
        "note": "переход отклоняется — нет ребра в таблице",
    },
    {
        "question": "Какими способами решается задача в стратегиях промптинга (week 1)?",
        "expected": ["пошагов", "эксперт", "прям"],
        "expected_sources": ["article_prompt_strategies.md"],
        "note": "прямой / пошагово / meta-prompt / эксперты",
    },
]
