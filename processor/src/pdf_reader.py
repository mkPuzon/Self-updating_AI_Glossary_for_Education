import io

import pypdf
import requests

_HEADERS = {"User-Agent": "SAGE/1.0 (research project; contact via GitHub)"}
MAX_PAGES = 15


def download_and_extract_text(pdf_url: str) -> str:
    """Download a PDF and return plain text from the first MAX_PAGES pages."""
    resp = requests.get(pdf_url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()

    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    pages = min(MAX_PAGES, len(reader.pages))

    parts = []
    for i in range(pages):
        text = reader.pages[i].extract_text()
        if text:
            parts.append(text)

    return "\n".join(parts)
