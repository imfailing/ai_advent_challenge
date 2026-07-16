"""Индексация документации и кода проекта → SQLite-индекс (для ревью PR)."""

import chunking
import index_store
from embedder import Embedder
from project_loader import load_docs_and_code

STRATEGY = "structural"


def main() -> None:
    docs = load_docs_and_code()
    chunks = chunking.chunk_corpus(docs, STRATEGY)
    print(f"Документов: {len(docs)}, чанков: {len(chunks)} — считаю эмбеддинги…")
    embeddings = Embedder().embed([c["text"] for c in chunks])
    stats = index_store.build(chunks, embeddings, STRATEGY)
    print(f"Индекс: {stats['chunks']} чанков (ср. {stats['avg_chars']} симв.) → index.db")


if __name__ == "__main__":
    main()
