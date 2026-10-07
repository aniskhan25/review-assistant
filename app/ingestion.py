"""Embedded-text PDF ingestion. Scanned pages require explicit manual recovery."""

import hashlib
import io
import re

MAX_BYTES = 20 * 1024 * 1024
MAX_TEXT = 1_000_000
EXTRACTOR_VERSION = "embedded-fields-1"


def ingest_pdf(data):
    import pdfplumber

    if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
        raise ValueError("Expected a PDF of at most 20 MiB")
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if not 0 < len(pdf.pages) <= 100:
                raise ValueError("PDF must contain 1–100 pages")
            pages = []
            total = 0
            for number, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                total += len(text)
                if total > MAX_TEXT:
                    raise ValueError("Extracted text exceeds limit")
                pages.append({"page": number, "text": text,
                              "status": "OK" if len(text.strip()) >= 20 else "PARSE_ERROR"})
    except Exception as exc:
        raise ValueError("PARSE_ERROR: PDF is unreadable, encrypted, or exceeds limits") from exc
    return document(pages, "sha256:" + hashlib.sha256(data).hexdigest())


def document(pages, document_id=None):
    """Also used by text fixtures; actual uploads always go through ingest_pdf."""
    if document_id is None:
        body = "\f".join(p["text"] for p in pages)
        document_id = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    chunks = []
    section = "Unclassified"
    headings = re.compile(r"^(?:project summary|ai factory selection|code\(s\) used|"
                          r"code details.*|description of the code|scalability.*|"
                          r"work\s?plan|ethics|resources|organization|previous.*)$", re.I)
    for page in pages:
        page.setdefault("status", "OK" if len(page["text"].strip()) >= 20 else "PARSE_ERROR")
        buffer = ""

        def flush():
            nonlocal buffer
            if buffer.strip():
                chunks.append({"id": f"ev-{len(chunks) + 1}", "page": page["page"],
                               "section": section, "text": buffer.strip()})
            buffer = ""

        for line in page["text"].splitlines():
            if headings.fullmatch(line.strip().rstrip(":")):
                flush()
                section = line.strip().rstrip(":")
            if len(buffer) + len(line) > 900:
                flush()
            # Long unbroken paragraphs are split rather than silently dropped.
            for start in range(0, max(1, len(line)), 900):
                piece = line[start:start + 900]
                if len(buffer) + len(piece) > 900:
                    flush()
                buffer += piece + "\n"
        flush()
    return {"document_id": document_id, "pages": pages, "evidence": chunks,
            "extractor_version": EXTRACTOR_VERSION,
            "warnings": [f"Page {p['page']}: PARSE_ERROR; manual transcription required"
                         for p in pages if p["status"] != "OK"]}
