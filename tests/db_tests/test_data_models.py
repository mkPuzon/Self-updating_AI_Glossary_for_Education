import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy.orm import Session
from shared.models import get_engine, Article, Keyword
from processor.src.seed import upsert_keyword


@pytest.fixture
def engine():
    eng = get_engine(":memory:")
    yield eng
    eng.dispose()


def test_create_article(engine):
    with Session(engine) as s:
        s.add(
            Article(
                paper_id="test-001",
                title="Test Paper",
                tags=["cs.AI", "cs.LG"],
                abstract="An abstract.",
            )
        )
        s.commit()
        found = s.get(Article, "test-001")
        assert found.title == "Test Paper"
        assert found.tags == ["cs.AI", "cs.LG"]


def test_keyword_upsert_increments_count(engine):
    with Session(engine) as s:
        upsert_keyword(s, {"keyword": "Transformer", "definition": "A model.", "paper_references": ["p1"]})
        upsert_keyword(s, {"keyword": "Transformer", "definition": "A model.", "paper_references": ["p2"]})
        s.commit()
        kw = s.get(Keyword, "Transformer")
        assert kw.count == 2
        assert set(kw.paper_references) == {"p1", "p2"}


def test_keyword_upsert_no_duplicate_refs(engine):
    with Session(engine) as s:
        upsert_keyword(s, {"keyword": "Attention", "definition": "Focus.", "paper_references": ["p1"]})
        upsert_keyword(s, {"keyword": "Attention", "definition": "Focus.", "paper_references": ["p1"]})
        s.commit()
        kw = s.get(Keyword, "Attention")
        assert kw.count == 2
        assert kw.paper_references.count("p1") == 1


def test_new_keyword_count_starts_at_one(engine):
    with Session(engine) as s:
        upsert_keyword(s, {"keyword": "RLHF", "definition": "Reinforcement learning.", "paper_references": ["p99"]})
        s.commit()
        kw = s.get(Keyword, "RLHF")
        assert kw.count == 1
        assert kw.paper_references == ["p99"]


def test_keyword_dates_stored_on_create(engine):
    with Session(engine) as s:
        upsert_keyword(s, {"keyword": "LoRA", "definition": "Low-rank adaptation.", "paper_references": ["p1"], "dates": ["2024-01-10"]})
        s.commit()
        kw = s.get(Keyword, "LoRA")
        assert kw.dates == ["2024-01-10"]


def test_keyword_dates_accumulate_across_papers(engine):
    with Session(engine) as s:
        upsert_keyword(s, {"keyword": "LoRA", "definition": "Low-rank adaptation.", "paper_references": ["p1"], "dates": ["2024-01-10"]})
        upsert_keyword(s, {"keyword": "LoRA", "definition": "Low-rank adaptation.", "paper_references": ["p2"], "dates": ["2024-03-05"]})
        s.commit()
        kw = s.get(Keyword, "LoRA")
        assert kw.dates == ["2024-01-10", "2024-03-05"]


def test_keyword_dates_duplicated_for_same_day(engine):
    with Session(engine) as s:
        upsert_keyword(s, {"keyword": "LoRA", "definition": "Low-rank adaptation.", "paper_references": ["p1"], "dates": ["2024-01-10"]})
        upsert_keyword(s, {"keyword": "LoRA", "definition": "Low-rank adaptation.", "paper_references": ["p2"], "dates": ["2024-01-10"]})
        s.commit()
        kw = s.get(Keyword, "LoRA")
        assert kw.dates.count("2024-01-10") == 2
