"""Embedded-text PDF ingestion. Scanned pages require explicit manual recovery."""

import hashlib
import io
import re

MAX_BYTES = 20 * 1024 * 1024
MAX_TEXT = 1_000_000
EXTRACTOR_VERSION = "embedded-fields-3"


def form_regions(pages):
    """Keep party/assessment boundaries across page breaks in consolidated forms."""
    scope = "proposal"
    for page in pages:
        lines = []
        for line in page["text"].splitlines():
            heading = line.strip().rstrip(":").lower()
            next_scope = scope
            if re.fullmatch(r"technical assessment(?:\s*[-–—].*)?", heading):
                next_scope = "assessment"
            elif scope != "assessment":
                if re.fullmatch(r"project lead and organi[sz]ation information|principal investigator", heading):
                    next_scope = "lead"
                elif re.fullmatch(r"team members(?: information|\s*#\d+)|contact person and team members", heading):
                    next_scope = "team"
                elif re.fullmatch(r"previous .+ allocations\s*#\d+", heading):
                    next_scope = "allocation_history"
                elif heading in {"ai factory selection", "partitions", "code details and feasibility",
                                  "code details, development and data management", "ethics self-assessment",
                                  "data consent", "eligibility confirmation and data consent"}:
                    next_scope = "proposal"
            if next_scope != scope:
                if lines:
                    yield {"page": page["page"], "text": "\n".join(lines), "scope": scope}
                lines = []
                scope = next_scope
            lines.append(line)
        if lines:
            yield {"page": page["page"], "text": "\n".join(lines), "scope": scope}


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
    headings = re.compile(r"^(?:project summary(?: \(abstract\))?|ai factory selection|code\(s\) used|"
                          r"code details(?: and feasibility| #\d+)?|description of the code|scalability and performance|"
                          r"work\s?plan|ethics(?: self-assessment)?|privacy & data governance|"
                          r"resources|organi[sz]ation(?: details)?|submission details)$", re.I)
    for page in pages:
        page.setdefault("status", "OK" if len(page["text"].strip()) >= 20 else "PARSE_ERROR")
    previous_scope = None
    for page in form_regions(pages):
        if page["scope"] != previous_scope:
            section = "Previous allocations" if page["scope"] == "allocation_history" else "Unclassified"
        previous_scope = page["scope"]
        buffer = ""

        def flush():
            nonlocal buffer
            if buffer.strip():
                chunks.append({"id": f"ev-{len(chunks) + 1}", "page": page["page"],
                               "section": section, "text": buffer.strip(), "scope": page["scope"]})
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
