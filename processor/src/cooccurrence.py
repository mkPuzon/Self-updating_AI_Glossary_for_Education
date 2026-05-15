from collections import defaultdict
from itertools import combinations

from sqlalchemy.orm import Session

from shared.models import Keyword, KeywordCooccurrence


def rebuild_cooccurrences(session: Session) -> None:
    all_keywords = session.query(Keyword).all()

    paper_to_keywords: dict[str, list[str]] = defaultdict(list)
    for kw in all_keywords:
        for paper_id in (kw.paper_references or []):
            paper_to_keywords[paper_id].append(kw.keyword)

    counts: dict[tuple[str, str], int] = defaultdict(int)
    for kws in paper_to_keywords.values():
        for a, b in combinations(sorted(kws), 2):
            counts[(a, b)] += 1
            counts[(b, a)] += 1

    session.query(KeywordCooccurrence).delete()
    for (a, b), score in counts.items():
        session.add(KeywordCooccurrence(keyword_a=a, keyword_b=b, score=score))
    session.commit()
    print(f"  Co-occurrence table rebuilt ({len(counts)} pairs).")
