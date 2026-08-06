"""Extract plain text from an uploaded company policy document (txt/pdf/docx)."""
import io

MAX_CHARS = 20_000


def extract_text(uploaded_file) -> str:
    name = (uploaded_file.name or "").lower()
    data = uploaded_file.read()

    if name.endswith(".txt") or name.endswith(".md"):
        text = data.decode("utf-8", errors="ignore")
    elif name.endswith(".pdf"):
        text = _extract_pdf(data)
    elif name.endswith(".docx"):
        text = _extract_docx(data)
    else:
        raise ValueError("Unsupported file type — please upload a .txt, .pdf, or .docx file.")

    return text[:MAX_CHARS]


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)
