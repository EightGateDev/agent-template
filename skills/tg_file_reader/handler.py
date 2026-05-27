#!/usr/bin/env python3
"""Read file content from Telegram (PDFs, DOCX, images, text files).

Usage: python handler.py <file_id> [file_name]
Env:   TELEGRAM_BOT_TOKEN
"""
import sys
import os
import json
import tempfile
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _tg_get_file_path(file_id: str) -> str:
    url = f"{TG_API}/getFile?file_id={urllib.parse.quote(file_id)}"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
    if not data.get("ok"):
        raise RuntimeError(f"getFile failed: {data}")
    return data["result"]["file_path"]


def _download(file_path: str, dest: str) -> None:
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    urllib.request.urlretrieve(url, dest)


def _read_pdf(path: str) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(pages).strip()
    except ImportError:
        pass
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        return "\n\n".join(p.get_text() for p in doc).strip()
    except ImportError:
        return "[PDF reading requires pypdf or PyMuPDF. Run: pip install pypdf]"


def _read_docx(path: str) -> str:
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return "[DOCX reading requires python-docx. Run: pip install python-docx]"


def _read_text(path: str) -> str:
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return "[Could not decode text file]"


def read_file(file_id: str, filename: str = "") -> str:
    if not BOT_TOKEN:
        return "TELEGRAM_BOT_TOKEN not set."
    try:
        tg_path = _tg_get_file_path(file_id)
        ext = os.path.splitext(tg_path)[1].lower() or os.path.splitext(filename)[1].lower()
        with tempfile.NamedTemporaryFile(suffix=ext or ".bin", delete=False) as tmp:
            tmp_path = tmp.name
        _download(tg_path, tmp_path)

        if ext in (".pdf",):
            content = _read_pdf(tmp_path)
        elif ext in (".docx",):
            content = _read_docx(tmp_path)
        elif ext in (".txt", ".csv", ".md", ".json", ".log", ".py", ".js", ".ts", ".yaml", ".yml", ".toml"):
            content = _read_text(tmp_path)
        elif ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            size = os.path.getsize(tmp_path)
            content = f"[Image file: {filename or tg_path}, {size} bytes. Use vision capabilities to analyze.]"
        else:
            size = os.path.getsize(tmp_path)
            content = f"[Binary file: {filename or tg_path}, {size} bytes, type: {ext or 'unknown'}]"

        os.unlink(tmp_path)
        return content[:8000]  # cap output
    except Exception as e:
        return f"File read error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: handler.py <file_id> [filename]", file=sys.stderr)
        sys.exit(1)
    file_id = sys.argv[1]
    filename = sys.argv[2] if len(sys.argv) > 2 else ""
    print(read_file(file_id, filename))
