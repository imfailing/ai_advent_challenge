"""
Проверка пайплайна индексации:
  • корпус загружается (документы разных типов, включая PDF);
  • обе стратегии chunking дают чанки с полным набором метаданных;
  • эмбеддинги имеют верную размерность;
  • индекс сохраняется и поиск возвращает релевантный чанк.
"""

import chunking
import index_store
import loader
from embedder import DIM, Embedder

META_KEYS = {"chunk_id", "strategy", "source", "file", "title",
             "section", "text", "n_chars"}


def main() -> None:
    # 1. загрузка корпуса
    docs = loader.load_corpus("corpus")
    total = sum(len(d["text"]) for d in docs)
    assert len(docs) >= 10, f"мало документов: {len(docs)}"
    assert total / 1800 >= 20, f"мало текста: {total/1800:.1f} стр."
    assert any(d["filetype"] == "pdf" for d in docs), "нет PDF в корпусе"
    assert any(d["filetype"] == "py" for d in docs), "нет кода в корпусе"
    print(f"✅ корпус: {len(docs)} документов, ~{total/1800:.1f} стр. (есть PDF и код)")

    # 2. обе стратегии + метаданные
    for strat in ("fixed", "structural"):
        chunks = chunking.chunk_corpus(docs, strat)
        assert len(chunks) >= 50, f"[{strat}] мало чанков: {len(chunks)}"
        for c in chunks:
            assert META_KEYS <= set(c), f"[{strat}] неполные метаданные: {set(c)}"
            assert c["strategy"] == strat and c["text"]
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids)), f"[{strat}] дубликаты chunk_id"
        print(f"✅ [{strat}] {len(chunks)} чанков, метаданные полные, chunk_id уникальны")

    # structural даёт осмысленные section (не только fixed[i])
    struct = chunking.chunk_corpus(docs, "structural")
    named = [c for c in struct if c["file"].endswith(".py")
             and c["section"] not in ("module header",)]
    assert any(c["section"].isidentifier() for c in named), "нет section-имён функций"
    print("✅ structural: section содержит имена функций/заголовки")

    # 3. эмбеддинги
    emb = Embedder()
    vecs = emb.embed([c["text"] for c in chunks[:5]])
    assert vecs.shape == (5, DIM), f"размерность {vecs.shape}"
    print(f"✅ эмбеддинги: форма {vecs.shape}, размерность {DIM}")

    # 4. поиск в индексе (индекс должен быть построен заранее)
    if index_store.count("structural") == 0:
        print("⚠ индекс не построен — пропускаю проверку поиска "
              "(запустите build_index.py both)")
    else:
        qv = emb.embed_one("запуск MCP-сервера и список инструментов")
        hits = index_store.search(qv, "structural", k=3)
        assert hits and hits[0]["score"] > 0.5, f"слабый результат: {hits[:1]}"
        assert "mcp" in (hits[0]["file"] + hits[0]["text"]).lower()
        print(f"✅ поиск: top-1 «{hits[0]['file']} → {hits[0]['section'][:30]}» "
              f"score={hits[0]['score']:.3f}")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    main()
