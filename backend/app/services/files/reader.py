"""File Intelligence (M05) — read, store, and index files.

Read:    PDF / TXT / MD / code files → plain text
Store:   Cloudflare R2 when configured, local data/files/ otherwise
Index:   chunks → embeddings → vector memory (searchable forever)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.core.memory.manager import memory
from app.core.memory.store import new_id, now_iso, store

log = logging.getLogger("files.reader")

DATA_FILES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "files"

_TEXT_SUFFIXES = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".csv",
                  ".yaml", ".yml", ".html", ".css", ".sh", ".sql", ".log", ".xml"}


def read_text(content: bytes, filename: str) -> str:
    """Extract plain text from a file's raw bytes."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(content)
    if suffix in _TEXT_SUFFIXES:
        return content.decode("utf-8", errors="replace")
    # last try: utf-8
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _read_pdf(content: bytes) -> str:
    import io

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001
        log.exception("pdf read failed")
        return ""


def _r2_client():
    import boto3

    from app.config.settings import settings

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


async def store_file(content: bytes, filename: str) -> dict:
    """Save the raw file (R2 if configured, else local) and return storage info."""
    from app.config.settings import settings

    file_id = new_id()
    if settings.r2_ready:
        key = f"uploads/{file_id}-{filename}"
        _r2_client().put_object(Bucket=settings.r2_bucket, Key=key, Body=content)
        location = {"backend": "r2", "key": key}
    else:
        DATA_FILES_DIR.mkdir(parents=True, exist_ok=True)
        path = DATA_FILES_DIR / f"{file_id}-{filename}"
        path.write_bytes(content)
        location = {"backend": "local", "path": str(path)}
    return {"file_id": file_id, "filename": filename, "size": len(content), **location}


_CHUNK_RE = re.compile(r"\n{2,}")
_CHUNK_SIZE = 1200


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE) -> list[str]:
    text = text.strip()
    if not text:
        return []
    # split on paragraph boundaries first, then hard-split long ones
    chunks: list[str] = []
    for para in _CHUNK_RE.split(text):
        while len(para) > chunk_size:
            cut = para.rfind(". ", 0, chunk_size)
            cut = cut if cut > chunk_size // 2 else chunk_size
            chunks.append(para[:cut].strip())
            para = para[cut:]
        if para.strip():
            chunks.append(para.strip())
    return chunks


async def index_file(filename: str, text: str, max_chunks: int = 40) -> dict:
    """Chunk + embed the file into long-term memory so it's searchable."""
    chunks = chunk_text(text)[:max_chunks]
    for i, chunk in enumerate(chunks):
        await memory.remember(
            f"[file:{filename} chunk {i + 1}/{len(chunks)}] {chunk}",
            kind="file",
        )
    doc = {
        "filename": filename, "chars": len(text), "chunks_indexed": len(chunks),
        "created_at": now_iso(),
    }
    store.put("files", filename, doc)
    return doc


async def search_files(query: str, limit: int = 5) -> list[dict]:
    hits = await memory.search(query, limit=limit)
    return [h for h in hits if h.get("meta", {}).get("kind") == "file"]
