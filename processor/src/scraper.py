import re
import datetime as dt
import xml.etree.ElementTree as ET

import requests

ARXIV_API = "http://export.arxiv.org/api/query"
_NS = "http://www.w3.org/2005/Atom"
_HEADERS = {"User-Agent": "SAGE/1.0 (research project)"}


def fetch_arxiv_papers(category: str, limit: int) -> list[dict]:
    """Fetch the most recently submitted papers from a given arXiv category."""
    params = {
        "search_query": f"cat:{category}",
        "start": 0,
        "max_results": limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    resp = requests.get(ARXIV_API, params=params, headers=_HEADERS, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    papers = []

    for entry in root.findall(f"{{{_NS}}}entry"):
        id_text = entry.find(f"{{{_NS}}}id").text.strip()
        match = re.search(r"arxiv\.org/abs/([\w.]+?)(?:v\d+)?$", id_text)
        if not match:
            continue
        arxiv_id = match.group(1)

        title = entry.find(f"{{{_NS}}}title").text.strip().replace("\n", " ")
        abstract = entry.find(f"{{{_NS}}}summary").text.strip().replace("\n", " ")
        published = entry.find(f"{{{_NS}}}published").text[:10]

        tags = [
            cat.get("term")
            for cat in entry.findall(f"{{{_NS}}}category")
            if cat.get("term")
        ]

        papers.append(
            {
                "paper_id": arxiv_id,
                "title": title,
                "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                "date_submitted": published,
                "date_scraped": dt.date.today().isoformat(),
                "tags": tags,
                "abstract": abstract,
            }
        )

    return papers
