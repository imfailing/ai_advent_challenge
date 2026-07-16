"""
Проверка AI-ревьюера:
  • индекс доков+кода собран;
  • по diff извлекаются изменённые файлы;
  • RAG находит релевантный контекст (конвенции/соседний код);
  • ревью содержит все 3 раздела и ловит очевидный баг.

Нужен DEEPSEEK_API_KEY и построенный индекс (python build_index.py).
"""

import index_store
import reviewer
from embedder import Embedder
from rerank import Reranker

SAMPLE_DIFF = """diff --git a/svc/agent.py b/svc/agent.py
--- a/svc/agent.py
+++ b/svc/agent.py
@@ -1,3 +1,8 @@
 class Agent:
+    API_KEY = "sk-hardcoded-secret"          # ключ в коде
+    def ask(self, history):
+        avg = sum(m["tokens"] for m in history) / len(history)  # ZeroDivision + KeyError
+        return avg
"""


def main() -> None:
    assert index_store.count("structural") > 100, "индекс не построен: python build_index.py"
    print(f"✅ индекс доков+кода: {index_store.count('structural')} чанков")

    files = reviewer.changed_files(SAMPLE_DIFF)
    assert files == ["svc/agent.py"], files
    print(f"✅ изменённые файлы из diff: {files}")

    emb, rr = Embedder(), Reranker()
    chunks = reviewer.retrieve_context(SAMPLE_DIFF, files, emb, rr)
    assert chunks, "RAG не вернул контекст"
    print(f"✅ RAG-контекст: {len(chunks)} чанков из {sorted({c['file'] for c in chunks})[:3]}")

    text = reviewer.review(SAMPLE_DIFF, files, reviewer._context(chunks))
    low = text.lower()
    assert "потенциальные баги" in low and "архитектур" in low and "рекомендаци" in low, \
        "нет обязательных разделов ревью"
    print("✅ ревью содержит разделы: баги / архитектура / рекомендации")

    # очевидные проблемы должны быть замечены
    assert any(k in low for k in ["zerodivision", "делен", "пуст", "len(history)"]), \
        "не замечено деление на ноль"
    assert any(k in low for k in ["ключ", "секрет", "hardcod", "api_key"]), \
        "не замечен хардкод ключа"
    print("✅ ревьюер поймал деление на ноль и хардкод ключа")
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — AI-ревью работает")


if __name__ == "__main__":
    main()
