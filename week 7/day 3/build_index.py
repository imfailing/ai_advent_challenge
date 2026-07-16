"""Индексация документации продукта (FAQ + доки) → SQLite-индекс."""

import chunking
import index_store
from doc_loader import load_docs
from embedder import Embedder

STRATEGY = "structural"


def main() -> None:
    docs = load_docs()
    chunks = chunking.chunk_corpus(docs, STRATEGY)
    print(f"Документов: {len(docs)}, чанков: {len(chunks)} — считаю эмбеддинги…")
    embeddings = Embedder().embed([c["text"] for c in chunks])
    stats = index_store.build(chunks, embeddings, STRATEGY)
    print(f"Индекс: {stats['chunks']} чанков → index.db")


if __name__ == "__main__":
    main()
