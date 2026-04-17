'''db_functions.py

Dumps metadata from .json file to SQLite database with modular design and verbose logging.

Aug 2025'''
import os
import re
import glob
import json
import sqlite3
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv
from src.metrics import PipelineMetrics, ErrorCategory
from src.logger_config import get_logger

logger = get_logger(__name__)

# ===== Utility Functions =====
def clean_text(text: str) -> str:
    """Remove null bytes and other problematic characters from text."""
    if not isinstance(text, str):
        return text
    try:
        # First, handle surrogate pairs by replacing them
        text = text.encode('utf-8', 'surrogatepass').decode('utf-8', 'replace')
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\uFFFD]', '', text)
        # Replace any remaining problematic Unicode characters
        text = text.encode('ascii', 'ignore').decode('ascii', 'ignore')
        return text
    except Exception as e:
        # If any error occurs during cleaning, return an empty string
        logger.warning(f"Error cleaning text: {str(e)}")
        return ""

def get_db_connection(verbose=False):
    """Create and return a database connection."""
    try:
        conn = sqlite3.connect(DB_NAME)
        # use Write-Ahead-Logging (WAL)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        if verbose:
            print(f"Connection to {DB_NAME} successful.")
        return conn
        
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        raise e

def setup_db(db_path: str) -> Tuple[bool, Optional[str]]:
    """
    Set up SQLite database with required tables.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Tuple of (success, error_message)
    """
    try:
        with sqlite3.connect(db_path) as conn:
            logger.info(f"Setting up database", extra={"db_path": db_path, "sqlite_version": sqlite3.sqlite_version})

            cursor = conn.cursor()

            create_table_articles = '''
            CREATE TABLE IF NOT EXISTS articles (
                article_id INTEGER PRIMARY KEY,
                uuid TEXT,
                title TEXT,
                date_submitted TEXT,
                date_scraped TEXT,
                tags TEXT,
                authors TEXT,
                abstract TEXT,
                pdf_url TEXT,
                full_arxiv_url TEXT,
                full_text TEXT,
                keywords TEXT
            );
            '''
            create_table_keywords = '''
            CREATE TABLE IF NOT EXISTS keywords (
                keyword TEXT PRIMARY KEY,
                definition TEXT,
                count INTEGER DEFAULT 1,
                paper_references TEXT
            );
            '''

            cursor.execute(create_table_articles)
            cursor.execute(create_table_keywords)
            conn.commit()

            logger.info("Database setup complete", extra={"tables": ["articles", "keywords"]})
            return True, None

    except sqlite3.OperationalError as e:
        error_msg = f"SQLite operational error: {str(e)}"
        logger.error(f"Failed to setup database: {error_msg}", extra={"db_path": db_path})
        return False, error_msg

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Unexpected error setting up database: {error_msg}", extra={"db_path": db_path})
        return False, error_msg

def clean_and_transform(key, raw_data):
    article_id = int(key)

    # convert strings to lists
    tags_raw = raw_data.get('tags', '')
    tags_list = [t.strip() for t in tags_raw.split(',')] if tags_raw else []
    authors_raw = raw_data.get('authors', '')
    authors_list = [a.strip() for a in authors_raw.split(',')] if authors_raw else []

    # convert unix timestamp to string
    try:
        ts = raw_data.get('date_scraped')
        if ts:
            ds = datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d')
        else:
            ds = None
    except ValueError:
        ds = None

    keyword_list = raw_data.get('keywords', [])

    return (
        article_id,
        raw_data.get('uuid'),
        raw_data.get('title'),
        raw_data.get('date_submitted'),
        ds,
        json.dumps(tags_list),    # Store as JSON string
        json.dumps(authors_list), # Store as JSON string
        raw_data.get('abstract'),
        raw_data.get('pdf_url'),
        raw_data.get('full_arxiv_url'),
        raw_data.get('full_text'),
        json.dumps(keyword_list)
    )

def process_file(data_dir):

    with get_db_connection() as conn:
        cursor = conn.cursor()
        total_inserted = 0

        print(f"Processing {os.path.basename(data_dir)}...")
        try:
            with open(data_dir, 'r', encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            
            batch_data = []
            for key, entry in data.items():
                clean_row = clean_and_transform(key, entry)
                batch_data.append(clean_row)

            # bulk insert data
            cursor.executemany('''
                INSERT OR IGNORE INTO articles (
                    article_id, uuid, title, date_submitted, date_scraped, 
                    tags, authors, abstract, pdf_url, full_arxiv_url, full_text, keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch_data)
            
            total_inserted += cursor.rowcount
            conn.commit()

        except Exception as e:
            print(f"Error processing {data_dir}: {e}")
    
    print(f"---- Total rows inserted: {total_inserted}")

def dump_metadata_to_db(json_filepath: str, db_path: str,
                        metrics: Optional[PipelineMetrics] = None) -> Tuple[int, int, int]:
    """
    Add paper metadata to SQLite database.

    Args:
        json_filepath: Path to JSON file with paper metadata
        db_path: Path to SQLite database
        metrics: Optional PipelineMetrics object for tracking

    Returns:
        Tuple of (papers_inserted, papers_duplicate, papers_no_definitions)
    """
    logger.info(f"Starting database import", extra={"json_file": json_filepath, "db_path": db_path})

    # Setup database
    success, error = setup_db(db_path=db_path)
    if not success:
        if metrics:
            metrics.record_error(ErrorCategory.DATABASE_ERROR, f"Database setup failed: {error}", {"db_path": db_path})
        return 0, 0, 0

    # Load metadata from JSON
    try:
        with open(json_filepath, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} papers from JSON", extra={"file": json_filepath})
    except FileNotFoundError:
        error_msg = f"Metadata file not found: {json_filepath}"
        logger.error(error_msg)
        if metrics:
            metrics.record_error(ErrorCategory.VALIDATION_ERROR, error_msg, {"file": json_filepath})
        return 0, 0, 0
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {str(e)}"
        logger.error(error_msg, extra={"file": json_filepath})
        if metrics:
            metrics.record_error(ErrorCategory.VALIDATION_ERROR, error_msg, {"file": json_filepath})
        return 0, 0, 0

    # Track statistics
    papers_inserted = 0
    papers_duplicate = 0
    papers_no_definitions = 0
    papers_error = 0
    keywords_new = 0
    keywords_existing = 0
    processed_keywords = set()

    with sqlite3.connect(db_path) as conn:
        # SQL queries
        sql_check_duplicate = "SELECT article_id FROM articles WHERE title = ? OR uuid = ?"
        sql_insert_articles = """
            INSERT INTO articles (
                uuid, title, date_submitted, date_scraped, tags, authors,
                abstract, pdf_url, full_arxiv_url, full_text, keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        sql_check_keyword = "SELECT count, paper_references FROM keywords WHERE keyword = ?"
        sql_update_keyword = "UPDATE keywords SET count = ?, paper_references = ? WHERE keyword = ?"
        sql_insert_keyword = "INSERT INTO keywords (keyword, definition, count, paper_references) VALUES (?, ?, 1, ?)"

        cur = conn.cursor()

        for paper in data.values():
            if metrics:
                metrics.increment("database.papers_attempted")

            # Begin transaction for this paper
            conn.execute("BEGIN")

            try:
                # Extract and validate definitions
                definitions = paper.get('definitions', {})
                if not isinstance(definitions, dict):
                    definitions = {}

                definitions = {
                    str(k).strip(): str(v) if v is not None else ''
                    for k, v in definitions.items()
                    if v != "None" and v is not None and k is not None
                }

                # Skip papers without definitions
                if not definitions:
                    conn.rollback()
                    papers_no_definitions += 1
                    if metrics:
                        metrics.increment("database.papers_no_definitions")
                    logger.info(f"Skipping paper (no definitions)", extra={
                        "uuid": paper.get('uuid', 'Unknown'),
                        "title": paper.get('title', 'Unknown')[:50]
                    })
                    continue

                # Parse lists
                tags_list = [t.strip() for t in paper.get('tags', '').split(',') if t.strip()] if isinstance(paper.get('tags'), str) else []
                authors_list = [a.strip() for a in paper.get('authors', '').split(',') if a.strip()] if isinstance(paper.get('authors'), str) else []

                keywords_raw = paper.get('keywords', [])
                if isinstance(keywords_raw, str):
                    keywords_list = [k.strip() for k in keywords_raw.split(',') if k.strip()]
                else:
                    keywords_list = [str(k).strip() for k in keywords_raw if k]

                # Serialization helpers
                clean_str = lambda x: x.strip() if isinstance(x, str) else x
                json_list = lambda x: json.dumps([clean_str(i) for i in x])

                # Check for duplicates
                cur.execute(sql_check_duplicate, (paper.get('title', ''), paper.get('uuid', '')))
                if cur.fetchone():
                    conn.rollback()
                    papers_duplicate += 1
                    if metrics:
                        metrics.increment("database.papers_duplicate")
                    logger.info(f"Skipping duplicate paper", extra={
                        "uuid": paper.get('uuid', 'Unknown'),
                        "title": paper.get('title', 'Unknown')[:50]
                    })
                    continue

                # Insert article
                data_to_insert = (
                    clean_str(paper.get('uuid', '')),
                    clean_str(paper.get('title', '')),
                    clean_str(paper.get('date_submitted')),
                    paper.get('date_scraped'),
                    json_list(tags_list),
                    json_list(authors_list),
                    clean_str(paper.get('abstract')),
                    clean_str(paper.get('pdf_url')),
                    clean_str(paper.get('full_arxiv_url')),
                    clean_str(paper.get('full_text')),
                    json_list(keywords_list)
                )

                cur.execute(sql_insert_articles, data_to_insert)
                article_id = cur.lastrowid

                # Process keywords
                for keyword, definition in definitions.items():
                    clean_kw = keyword.strip()
                    clean_def = definition.strip()
                    if not clean_kw:
                        continue

                    cur.execute(sql_check_keyword, (clean_kw,))
                    row = cur.fetchone()

                    if row:  # Existing keyword
                        current_count = row[0]
                        try:
                            current_refs = json.loads(row[1])
                        except:
                            current_refs = []

                        new_count = current_count
                        if str(article_id) not in current_refs:
                            current_refs.append(str(article_id))
                            new_count += 1

                        cur.execute(sql_update_keyword, (
                            new_count,
                            json.dumps(current_refs),
                            clean_kw
                        ))

                        if clean_kw not in processed_keywords:
                            keywords_existing += 1
                            processed_keywords.add(clean_kw)

                    else:  # New keyword
                        initial_refs = json.dumps([str(article_id)])
                        cur.execute(sql_insert_keyword, (clean_kw, clean_def, initial_refs))

                        if clean_kw not in processed_keywords:
                            keywords_new += 1
                            processed_keywords.add(clean_kw)

                # Commit this paper
                conn.commit()
                papers_inserted += 1

                if metrics:
                    metrics.increment("database.papers_inserted")

                logger.debug(f"Inserted paper", extra={
                    "article_id": article_id,
                    "uuid": paper.get('uuid', 'Unknown'),
                    "num_keywords": len(definitions)
                })

            except Exception as inner_e:
                conn.rollback()
                papers_error += 1

                if metrics:
                    metrics.increment("database.papers_error")
                    metrics.record_error(
                        ErrorCategory.DATABASE_ERROR,
                        f"Failed to insert paper: {type(inner_e).__name__}: {str(inner_e)}",
                        {
                            "uuid": paper.get('uuid', 'Unknown'),
                            "title": paper.get('title', 'Unknown')[:100]
                        }
                    )

                logger.error(f"Failed to insert paper: {type(inner_e).__name__}: {str(inner_e)}", extra={
                    "uuid": paper.get('uuid', 'Unknown'),
                    "title": paper.get('title', 'Unknown')[:100]
                })
                continue

    # Update metrics
    if metrics:
        metrics.increment("database.keywords_new", keywords_new)
        metrics.increment("database.keywords_existing", keywords_existing)
        metrics.increment("database.keywords_total", len(processed_keywords))

    logger.info(f"Database import complete", extra={
        "papers_inserted": papers_inserted,
        "papers_duplicate": papers_duplicate,
        "papers_no_definitions": papers_no_definitions,
        "papers_error": papers_error,
        "keywords_new": keywords_new,
        "keywords_existing": keywords_existing,
        "keywords_total": len(processed_keywords)
    })

    return papers_inserted, papers_duplicate, papers_no_definitions
        
if __name__ == "__main__":
    today = datetime.today().strftime('%Y-%m-%d')
    today = "2026-01-28"

    DATA_DIR = f'data/metadata/metadata_{today}.json'
    DB_NAME = 'data/aura.db'

    # setup_db(DATA_DIR)
    dump_metadata_to_db(DATA_DIR, DB_NAME, verbose=True)