"""
Две стратегии разбиения на чанки. Обе возвращают чанки с метаданными:

  {
    "chunk_id": "<filename>#<strategy>#<i>",  # стабильный идентификатор
    "strategy": "fixed" | "structural",
    "source":   путь к файлу,
    "file":     имя файла,
    "title":    заголовок документа,
    "section":  метка раздела (для fixed — 'fixed[i]', для structural — заголовок/функция),
    "text":     текст чанка,
    "n_chars":  длина,
  }

Стратегии:
  1. fixed_size  — окна фиксированного размера по символам с перекрытием.
  2. structural  — по структуре документа:
       markdown → по заголовкам (#/##/###);
       код (.py) → по top-level def/class;
       txt/pdf   → по абзацам (пустая строка-разделитель).
"""

import re

DEFAULT_SIZE    = 800
DEFAULT_OVERLAP = 150
STRUCT_MAX      = 1600   # мягкий предел для structural-чанка (чтобы не обрезался эмбеддером)


def _mk(doc: dict, strategy: str, i: int, section: str, text: str) -> dict:
    return {
        "chunk_id": f"{doc['filename']}#{strategy}#{i}",
        "strategy": strategy,
        "source":   doc["path"],
        "file":     doc["filename"],
        "title":    doc["title"],
        "section":  section,
        "text":     text.strip(),
        "n_chars":  len(text.strip()),
    }


# ------------------------------------------------------------------
# Стратегия 1 — фиксированный размер
# ------------------------------------------------------------------

def fixed_size(doc: dict, size: int = DEFAULT_SIZE,
               overlap: int = DEFAULT_OVERLAP) -> list[dict]:
    text  = doc["text"]
    step  = max(1, size - overlap)
    chunks, i, pos = [], 0, 0
    while pos < len(text):
        piece = text[pos:pos + size]
        if piece.strip():
            chunks.append(_mk(doc, "fixed", i, f"fixed[{i}]", piece))
            i += 1
        pos += step
    return chunks


# ------------------------------------------------------------------
# Стратегия 2 — по структуре
# ------------------------------------------------------------------

def _structural_markdown(doc: dict) -> list[dict]:
    lines = doc["text"].splitlines()
    chunks, i = [], 0
    section = doc["title"]
    buf: list[str] = []

    def flush():
        nonlocal i, buf
        body = "\n".join(buf).strip()
        if body:
            chunks.append(_mk(doc, "structural", i, section, body))
            i += 1
        buf = []

    for line in lines:
        m = re.match(r"^(#{1,3})\s+(.+)", line.strip())
        if m:
            flush()
            section = m.group(2).strip()
            buf = [line]
        else:
            buf.append(line)
    flush()
    return chunks


def _structural_python(doc: dict) -> list[dict]:
    lines = doc["text"].splitlines()
    # индексы строк, где начинается top-level def/class
    starts = [n for n, ln in enumerate(lines)
              if re.match(r"^(def|class|async def)\s+\w+", ln)]
    chunks, i = [], 0
    # преамбула до первого определения (импорты, docstring)
    if not starts or starts[0] > 0:
        head = "\n".join(lines[:starts[0]] if starts else lines).strip()
        if head:
            chunks.append(_mk(doc, "structural", i, "module header", head))
            i += 1
    for j, s in enumerate(starts):
        end = starts[j + 1] if j + 1 < len(starts) else len(lines)
        block = "\n".join(lines[s:end])
        name  = re.match(r"^(?:async def|def|class)\s+(\w+)", lines[s].strip())
        section = name.group(1) if name else f"block[{i}]"
        chunks.append(_mk(doc, "structural", i, section, block))
        i += 1
    return chunks


def _structural_paragraphs(doc: dict) -> list[dict]:
    paras = re.split(r"\n\s*\n", doc["text"])
    chunks, i = [], 0
    for p in paras:
        if p.strip():
            chunks.append(_mk(doc, "structural", i, f"para[{i}]", p))
            i += 1
    return chunks


def _split_oversized(chunks: list[dict], doc: dict) -> list[dict]:
    """Разбить слишком большие structural-чанки на части, сохранив section."""
    out, i = [], 0
    for c in chunks:
        text = c["text"]
        if len(text) <= STRUCT_MAX:
            out.append({**c, "chunk_id": f"{doc['filename']}#structural#{i}"})
            i += 1
            continue
        for pos in range(0, len(text), STRUCT_MAX):
            piece = text[pos:pos + STRUCT_MAX]
            if piece.strip():
                out.append(_mk(doc, "structural", i, c["section"], piece))
                i += 1
    return out


def structural(doc: dict) -> list[dict]:
    if doc["filetype"] == "md":
        chunks = _structural_markdown(doc)
    elif doc["filetype"] == "py":
        chunks = _structural_python(doc)
    else:
        chunks = _structural_paragraphs(doc)   # txt / pdf
    return _split_oversized(chunks, doc)


# ------------------------------------------------------------------
# Единая точка входа
# ------------------------------------------------------------------

STRATEGIES = {
    "fixed":      fixed_size,
    "structural": structural,
}


def chunk_document(doc: dict, strategy: str) -> list[dict]:
    if strategy not in STRATEGIES:
        raise ValueError(f"Неизвестная стратегия: {strategy!r}")
    return STRATEGIES[strategy](doc)


def chunk_corpus(docs: list[dict], strategy: str) -> list[dict]:
    out = []
    for doc in docs:
        out.extend(chunk_document(doc, strategy))
    return out
