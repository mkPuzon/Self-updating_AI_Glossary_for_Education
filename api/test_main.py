"""api/test_main.py

Reproducible test suite for api/main.py.

Creates a small in-memory SQLite database (8 records: 3 articles + 5 keywords)
and runs assertions against both FastAPI endpoints without touching the
production aura.db.

Run:
    pytest api/test_main.py -v

Dependencies (beyond api/requirements.txt):
    pip install pytest          # test runner
    httpx is already pulled in by fastapi[standard] / starlette's TestClient
"""
import os
import sqlite3
import sys

import pytest

# ---------------------------------------------------------------------------
# Dummy data — 8 records chosen to cover every code path
# ---------------------------------------------------------------------------

ARTICLES = [
    # article_id, uuid, title, date_submitted, date_scraped,
    # tags, authors, abstract, pdf_url, full_arxiv_url, full_text, keywords
    (
        1, "uuid-1", "Attention Is All You Need", "2017-06-12", "2024-01-01",
        "['cs.LG', 'cs.AI']", "['Vaswani et al.']",
        "Introduces the Transformer architecture using only attention mechanisms.",
        "https://arxiv.org/pdf/1706.03762", "https://arxiv.org/abs/1706.03762", "full text 1", "['neural networks', 'transformer']",
    ),
    (
        2, "uuid-2", "Playing Atari with Deep RL", "2013-12-19", "2024-01-01",
        "['cs.LG']", "['Mnih et al.']",
        "Applies DQN to Atari games and achieves human-level performance.",
        "https://arxiv.org/pdf/1312.5602", "https://arxiv.org/abs/1312.5602", "full text 2", "['neural networks', 'reinforcement learning']",
    ),
    (
        3, "uuid-3", "BERT: Pre-training of Deep Transformers", "2018-10-11", "2024-01-01",
        "['cs.CL', 'cs.AI']", "['Devlin et al.']",
        "Introduces BERT for bidirectional pre-training of language models.",
        "https://arxiv.org/pdf/1810.04805", "https://arxiv.org/abs/1810.04805", "full text 3", "['neural networks', 'transformer', 'attention mechanism']",
    ),
]

KEYWORDS = [
    # keyword, definition, count, paper_references
    # paper_references mirrors production: json.dumps([str(article_id), ...])
    ("neural networks",        "Core ML architecture of interconnected nodes",            10, '["1", "2", "3"]'),
    ("transformer",            "Attention-based architecture for sequence modelling",      8, '["1", "3"]'),
    ("reinforcement learning", "Learning via reward signals from environment interaction",  5, '["2"]'),
    ("attention mechanism",    "Selective focus mechanism for model inputs",               3, '["3"]'),
    ("gradient descent",       "Iterative optimization technique for minimizing loss",     1, ""),
]


def create_dummy_db(path: str) -> None:
    """Build schema and populate with 8 dummy records (3 articles + 5 keywords).

    Schema matches production (db_functions.py::setup_db):
      - keywords uses keyword TEXT PRIMARY KEY (no numeric id column); rowid is
        the implicit SQLite rowid used by the /terms/{id} endpoint.
      - paper_references stores JSON arrays of string article IDs, matching the
        json.dumps([str(article_id)]) format written by dump_metadata_to_db.
    """
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE articles (
            article_id      INTEGER PRIMARY KEY,
            uuid            TEXT,
            title           TEXT,
            date_submitted  TEXT,
            date_scraped    TEXT,
            tags            TEXT,
            authors         TEXT,
            abstract        TEXT,
            pdf_url         TEXT,
            full_arxiv_url  TEXT,
            full_text       TEXT,
            keywords        TEXT
        );
        CREATE TABLE keywords (
            keyword          TEXT PRIMARY KEY,
            definition       TEXT,
            count            INTEGER DEFAULT 1,
            paper_references TEXT
        );
    """)
    conn.executemany("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ARTICLES)
    conn.executemany(
        "INSERT INTO keywords (keyword, definition, count, paper_references) VALUES (?,?,?,?)",
        KEYWORDS,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Session-scoped fixture: one DB + one TestClient for the whole test run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client(tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("db") / "test_aura.db")
    create_dummy_db(db_path)

    # Ensure api/ is on sys.path so `import main` resolves correctly.
    api_dir = os.path.dirname(os.path.abspath(__file__))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)

    import main as _main

    # Patch DB_PATH *after* import — get_db() reads the module-level variable
    # each call, so this redirect takes effect immediately.
    _main.DB_PATH = db_path

    from starlette.testclient import TestClient
    return TestClient(_main.app)


# ---------------------------------------------------------------------------
# GET /terms
# ---------------------------------------------------------------------------

def test_get_terms_returns_all(client):
    """Returns all 5 keywords sorted by count descending."""
    r = client.get("/terms")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    assert data[0]["term"] == "neural networks"    # count=10, highest
    assert data[-1]["term"] == "gradient descent"  # count=1,  lowest


def test_get_terms_response_shape(client):
    """Each term has id, term, and definition fields."""
    data = client.get("/terms").json()
    for item in data:
        assert "id" in item
        assert "term" in item
        assert "definition" in item


def test_get_terms_search_keyword_column(client):
    """search= is matched case-insensitively against the keyword column."""
    r = client.get("/terms", params={"search": "neural"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["term"] == "neural networks"


def test_get_terms_search_definition_column(client):
    """search= also matches against the definition column."""
    r = client.get("/terms", params={"search": "Attention-based"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["term"] == "transformer"


def test_get_terms_search_no_match(client):
    """A non-matching search returns an empty list, not a 404."""
    r = client.get("/terms", params={"search": "zzznomatch"})
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET /terms/{term_id}
# ---------------------------------------------------------------------------

def test_get_term_detail_sources(client):
    """neural networks (id=1) references all 3 articles — expect exactly 3 sources."""
    r = client.get("/terms/1")
    assert r.status_code == 200
    data = r.json()
    assert data["term"] == "neural networks"
    assert len(data["sources"]) == 3
    titles = {s["title"] for s in data["sources"]}
    assert "Attention Is All You Need" in titles
    assert "Playing Atari with Deep RL" in titles
    assert "BERT: Pre-training of Deep Transformers" in titles


def test_get_term_detail_source_fields(client):
    """Each source object exposes title, summary, date, and link."""
    sources = client.get("/terms/1").json()["sources"]
    for s in sources:
        assert "title" in s
        assert "summary" in s
        assert "date" in s
        assert "link" in s
        assert s["link"].startswith("https://arxiv.org")


def test_get_term_detail_tags(client):
    """Tags are parsed and cs.LG appears (shared by articles 1 and 2)."""
    tags = client.get("/terms/1").json()["tags"]
    assert len(tags) > 0
    tag_names = {t["name"] for t in tags}
    assert "cs.LG" in tag_names


def test_get_term_detail_related_terms(client):
    """transformer (id=2) shares article 1 with neural networks — must appear in related."""
    data = client.get("/terms/2").json()
    related = {t["term"] for t in data["related_terms"]}
    assert "neural networks" in related


def test_get_term_detail_no_refs_fallback(client):
    """gradient descent (id=5) has no article refs — returns empty sources and
    falls back to random related terms from the rest of the keyword table."""
    r = client.get("/terms/5")
    assert r.status_code == 200
    data = r.json()
    assert data["term"] == "gradient descent"
    assert data["sources"] == []
    assert len(data["related_terms"]) > 0   # 4 other keywords exist


def test_get_term_not_found(client):
    """A non-existent term ID returns HTTP 404."""
    r = client.get("/terms/999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# dates field
# ---------------------------------------------------------------------------

def test_get_term_detail_dates_multiple(client):
    """neural networks (id=1) refs articles dated 2017-06-12, 2013-12-19, 2018-10-11.
    Expects [earliest, latest] regardless of insertion order."""
    dates = client.get("/terms/1").json()["dates"]
    assert len(dates) == 2
    assert dates[0] == "2013-12-19"   # earliest
    assert dates[1] == "2018-10-11"   # latest


def test_get_term_detail_dates_single(client):
    """reinforcement learning (id=3) refs only article 2 (2013-12-19).
    Expects the same date in both positions."""
    dates = client.get("/terms/3").json()["dates"]
    assert dates == ["2013-12-19", "2013-12-19"]


def test_get_term_detail_dates_no_refs(client):
    """gradient descent (id=5) has no article refs — dates should be an empty list."""
    dates = client.get("/terms/5").json()["dates"]
    assert dates == []
