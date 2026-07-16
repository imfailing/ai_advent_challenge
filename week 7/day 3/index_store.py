"""
Хранилище индекса: SQLite (чанки + метаданные + эмбеддинги-BLOB) и
JSON-манифест (метаданные без векторов, для инспекции).

Поиск — косинусная близость на numpy (векторы L2-нормированы, поэтому
косинус = скалярное произведение). Для этого масштаба brute-force достаточно;
при желании эмбеддинги легко переложить в FAISS.
"""

import json
import sqlite3
from pathlib import Path

import numpy as np

DB_PATH = Path(__file__).parent / "index.db"


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id  TEXT PRIMARY KEY,
                strategy  TEXT NOT NULL,
                source    TEXT NOT NULL,
                file      TEXT NOT NULL,
                title     TEXT,
                section   TEXT,
                text      TEXT NOT NULL,
                n_chars   INTEGER NOT NULL,
                dim       INTEGER NOT NULL,
                embedding BLOB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_strategy ON chunks(strategy);
        """)


def build(chunks: list[dict], embeddings: np.ndarray, strategy: str) -> dict:
    """Сохранить чанки+эмбеддинги для стратегии. Возвращает статистику."""
    init_db()
    with _conn() as con:
        con.execute("DELETE FROM chunks WHERE strategy = ?", (strategy,))
        for c, vec in zip(chunks, embeddings):
            con.execute(
                "INSERT OR REPLACE INTO chunks"
                " (chunk_id, strategy, source, file, title, section, text, n_chars, dim, embedding)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (c["chunk_id"], strategy, c["source"], c["file"], c["title"],
                 c["section"], c["text"], c["n_chars"], vec.shape[0],
                 np.asarray(vec, dtype=np.float32).tobytes()),
            )
        con.commit()

    # JSON-манифест без векторов
    manifest = [{k: c[k] for k in
                 ("chunk_id", "strategy", "source", "file", "title", "section", "n_chars")}
                for c in chunks]
    out = Path(__file__).parent / f"index_{strategy}.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    sizes = [c["n_chars"] for c in chunks]
    return {
        "strategy":   strategy,
        "chunks":     len(chunks),
        "avg_chars":  round(sum(sizes) / len(sizes)) if sizes else 0,
        "min_chars":  min(sizes) if sizes else 0,
        "max_chars":  max(sizes) if sizes else 0,
        "json":       str(out.name),
    }


def _load(strategy: str) -> tuple[list[dict], np.ndarray]:
    with _conn() as con:
        rows = con.execute(
            "SELECT chunk_id, file, section, text, embedding, dim FROM chunks"
            " WHERE strategy = ? ORDER BY rowid", (strategy,),
        ).fetchall()
    meta, vecs = [], []
    for r in rows:
        meta.append({"chunk_id": r["chunk_id"], "file": r["file"],
                     "section": r["section"], "text": r["text"]})
        vecs.append(np.frombuffer(r["embedding"], dtype=np.float32))
    return meta, (np.vstack(vecs) if vecs else np.zeros((0, 384), dtype=np.float32))


def search(query_vec: np.ndarray, strategy: str, k: int = 3) -> list[dict]:
    """top-k чанков по косинусной близости для стратегии."""
    meta, mat = _load(strategy)
    if len(meta) == 0:
        return []
    q = np.asarray(query_vec, dtype=np.float32)
    q = q / (np.linalg.norm(q) or 1.0)
    scores = mat @ q                      # векторы уже нормированы
    order = np.argsort(-scores)[:k]
    return [{**meta[i], "score": float(scores[i])} for i in order]


def count(strategy: str) -> int:
    with _conn() as con:
        return con.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE strategy = ?", (strategy,)
        ).fetchone()["n"]
