'''api/main.py

API to allow the front end to query the SQLite database.

last updated: mar 2026
'''
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import json
import ast  # generic parser for stringified lists

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# resolve db path relative to this file so local uvicorn runs work alongside Docker
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(_HERE, "..", "data", "aura.db"))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_refs(ref_string: str) -> list[int]:
    '''Parse the paper_references column from a stringified list into a list of ints.'''
    if not ref_string:
        return []
    try:
        parsed = json.loads(ref_string)
    except (json.JSONDecodeError, ValueError):
        try:
            parsed = ast.literal_eval(ref_string)
        except (ValueError, SyntaxError):
            parsed = [x.strip() for x in ref_string.split(',')]
    return [int(x) for x in parsed if x]


def parse_tags(tags_str: str) -> list[str]:
    '''Parse the tags column from a bracketed string into a clean list of strings.'''
    if not tags_str:
        return []
    cleaned = tags_str.replace('[', '').replace(']', '').replace("'", "")
    return [t.strip() for t in cleaned.split(',') if t.strip()]


@app.get("/terms")
def get_terms(search: str = None):
    '''Returns up to 100 most popular terms.'''
    
    # use WHERE 1=1 to ensure can append AND claudes
    query = """
        SELECT rowid AS id, keyword AS term, definition, count
        FROM keywords
        WHERE 1=1
    """
    params = []

    if search:
        # case insensitive; searches both keyword and definition 
        query += " AND (keyword LIKE ? OR definition LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY count DESC LIMIT 50"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": row["id"],
            "term": row["term"],
            "definition": row["definition"] or "No definition available.",
        }
        for row in rows
    ]


@app.get("/terms/{term_id}")
def get_term_details(term_id: int):
    with get_db() as conn:
        # get entry for specified keyword
        keyword_row = conn.execute(
            "SELECT *, rowid AS id FROM keywords WHERE rowid = ?", (term_id,)
        ).fetchone()

        if not keyword_row:
            raise HTTPException(status_code=404, detail="Term not found")

        article_ids = parse_refs(keyword_row["paper_references"])

        sources = []
        all_tags = []

        if article_ids:
            # get all articles that reference the specified keyword
            placeholders = ",".join("?" * len(article_ids))
            articles = conn.execute(
                f"""
                SELECT title, abstract, tags, full_arxiv_url, date_submitted
                FROM articles
                WHERE article_id IN ({placeholders})
                """,
                article_ids,
            ).fetchall()

            for art in articles:
                sources.append({
                    "title": art["title"],
                    "summary": (art["abstract"][:200] + "...") if art["abstract"] else "No abstract.",
                    "date": art["date_submitted"],
                    "link": art["full_arxiv_url"],
                })
                all_tags.extend(parse_tags(art["tags"]))

        # find other keywords from the DB as related terms 
        if article_ids:
            placeholders = ",".join("?" * len(article_ids))
            related_terms = conn.execute(
                f"""
                SELECT rowid AS id, keyword AS term
                FROM keywords
                WHERE rowid != ?
                AND ({" OR ".join(["paper_references LIKE ?" ] * len(article_ids))})
                LIMIT 5
                """,
                [term_id] + [f"%{aid}%" for aid in article_ids],
            ).fetchall()
        else:
            # fallback to random
            related_terms = conn.execute(
                "SELECT rowid AS id, keyword AS term FROM keywords WHERE rowid != ? ORDER BY RANDOM() LIMIT 5",
                (term_id,),
            ).fetchall()

    return {
        "id": keyword_row["id"],
        "term": keyword_row["keyword"],
        "definition": keyword_row["definition"],
        "sources": sources,
        "related_terms": [dict(row) for row in related_terms],
        "tags": [{"name": t} for t in list(set(all_tags))[:5]],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
