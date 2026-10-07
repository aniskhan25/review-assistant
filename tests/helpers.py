from app.configuration import load_policy
from app.decision import ManualBackend
from app.ingestion import document
from app.review import new_review, confirm_fact, confirm_decision, REQUIRED_FACTS

TEXT = """Project summary
Application ID: synthetic-001
Access mode: Fast Lane
Target machine: LUMI-G
Project duration (months): 2
Organization type: SME
Country: Finland
VAT number: FI12345678
Resources
Requested GPU hours: 50000
Maximum number of GPUs: 64
Total storage (GB): 1000
Total transfer (GB): 200
Personal data declared: No
Previous LUMI use: No
Previous EuroHPC allocation: No
Code details and feasibility
Code(s) used: PyTorch
Frameworks: PyTorch
Backend: ROCm
PyTorch supports ROCm; our core code targets AMD GPUs on LUMI-G.
No prior installation on LUMI. Custom environment installation is needed.
Workplan
We will run 50 training experiments, benchmark throughput and use independent concurrent jobs.
Scalability and performance
Independent job arrays use up to 64 GPUs. Each training experiment uses one GPU.
"""


def review(text=TEXT):
    return new_review(document([{"page": 1, "text": text}]), ManualBackend(), load_policy(), "test-reviewer")


def confirmed(state):
    ids = [e["id"] for e in state["document"]["evidence"]]
    for field in REQUIRED_FACTS:
        fact = state["facts"][field]
        value = fact["value"]
        raw = ("yes" if value else "no") if isinstance(value, bool) else str(value)
        confirm_fact(state, field, raw, "PRESENT", ids, "Checked against proposal")
    for qid in state["decisions"]:
        confirm_decision(state, qid, "NO" if qid == "code_previously_installed" else "YES", ids, "Verified proposal evidence")
    return state


def pdf_bytes(text=TEXT):
    """Minimal valid text PDF fixture without an extra PDF-writing dependency."""
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in text.splitlines()]
    stream = ("BT /F1 10 Tf 40 780 Td 12 TL " + " ".join(f"({line}) Tj T*" for line in escaped) + " ET").encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 820] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"]
    data, offsets = b"%PDF-1.4\n", [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data)
    data += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
