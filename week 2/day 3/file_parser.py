"""
Извлечение текстового содержимого из загружаемых файлов.

Поддерживаемые форматы:
  Текстовые: .txt, .md, .py, .js, .ts, .json, .csv, .yaml, .yml, .html, .xml
  PDF: .pdf (через pypdf)

Возвращает строку с содержимым или выбрасывает ValueError для неизвестных форматов.
"""

from pathlib import Path

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json",
    ".csv", ".yaml", ".yml", ".html", ".xml", ".sql",
}
MAX_FILE_SIZE = 512 * 1024  # 512 KB


def extract_text(filename: str, data: bytes) -> str:
    """
    Извлечь текст из байтов файла.

    Параметры
    ---------
    filename : str
        Имя файла (используется для определения формата).
    data : bytes
        Содержимое файла.

    Возвращает
    ----------
    str
        Извлечённый текст.
    """
    if len(data) > MAX_FILE_SIZE:
        raise ValueError(
            f"Файл слишком большой ({len(data) // 1024} KB). "
            f"Максимум — {MAX_FILE_SIZE // 1024} KB."
        )

    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(data)

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        return _extract_text(data)

    raise ValueError(
        f"Формат «{ext}» не поддерживается. "
        f"Поддерживаются: PDF и текстовые файлы "
        f"({', '.join(sorted(SUPPORTED_TEXT_EXTENSIONS))})."
    )


def _extract_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Не удалось определить кодировку файла.")


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        if not text:
            raise ValueError("PDF не содержит извлекаемого текста (возможно, сканированный).")
        return text
    except ImportError:
        raise ValueError("Для чтения PDF установите pypdf: pip install pypdf")
