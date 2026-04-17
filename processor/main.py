'''processor/main.py

Main controller for AURA data processing pipeline.
Orchestrates scraping, LLM processing, and database storage with comprehensive metrics tracking.

Last Updated: Feb 2026
'''
import os
import sys
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.scrape_papers import scrape_papers
from src.process_text import generate_keywords_and_defs
from src.db_functions import dump_metadata_to_db
from src.metrics import PipelineMetrics, ErrorCategory
from src.logger_config import setup_logging, get_logger

# Initialize logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


def save_metrics_history(metrics: PipelineMetrics) -> None:
    """
    Save metrics to historical log file (JSONL format).

    Args:
        metrics: PipelineMetrics object with run data
    """
    try:
        today = datetime.today().strftime("%Y-%m-%d")
        log_dir = Path("data/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        history_file = log_dir / f"metrics_history_{today}.jsonl"

        # Append metrics as single JSON line
        with open(history_file, "a") as f:
            f.write(metrics.to_json() + "\n")

        logger.info(f"Saved metrics to history", extra={"file": str(history_file)})

    except Exception as e:
        logger.error(f"Failed to save metrics history: {type(e).__name__}: {str(e)}")


def job():
    """
    Main workflow for data scraping, processing, and uploading. Runs the complete pipeline with metrics tracking.
    """
    today = datetime.today().strftime('%Y-%m-%d')

    # init metrics
    metrics = PipelineMetrics(run_date=today)
    logger.info("=" * 80)
    logger.info(f"AURA Pipeline Starting - {today}")
    logger.info("=" * 80)

    try:
        logger.info("Starting Stage 1: Paper Scraping")
        metrics.start_stage("scraping")

        try:
            num_metadata, num_pdfs = scrape_papers(
                query="cs.AI",
                date=today,
                max_results=200,
                method='pypdf',
                metrics=metrics
            )
            logger.info(f"Scraping complete: {num_metadata} metadata, {num_pdfs} PDFs")

        except Exception as e:
            logger.error(f"Scraping stage failed: {type(e).__name__}: {str(e)}", exc_info=True)
            metrics.record_error(
                ErrorCategory.PIPELINE_ERROR,
                f"Scraping stage failed: {str(e)}",
                {"stage": "scraping"}
            )
            raise
        finally:
            metrics.end_stage("scraping")

        logger.info("Starting Stage 2: LLM Processing")
        metrics.start_stage("llm_processing")

        try:
            file_path = f"./data/metadata/metadata_{today}.json"

            num_papers, num_kwds, num_dicts = generate_keywords_and_defs(
                batch_filepath=file_path,
                kwd_model="gemma3:12b",
                def_model="gpt-4.1-nano",
                openai=True,
                metrics=metrics
            )

            logger.info(f"LLM processing complete: {num_papers} papers, {num_kwds} keywords, {num_dicts} with definitions")

        except Exception as e:
            logger.error(f"LLM processing stage failed: {type(e).__name__}: {str(e)}", exc_info=True)
            metrics.record_error(
                ErrorCategory.PIPELINE_ERROR,
                f"LLM processing stage failed: {str(e)}",
                {"stage": "llm_processing"}
            )
            raise
        finally:
            metrics.end_stage("llm_processing")

        logger.info("Starting Stage 3: Database Import")
        metrics.start_stage("database")

        try:
            data_file = f'data/metadata/metadata_{today}.json'
            db_path = 'data/aura.db'

            papers_inserted, papers_duplicate, papers_no_defs = dump_metadata_to_db(
                json_filepath=data_file,
                db_path=db_path,
                metrics=metrics
            )

            logger.info(f"Database import complete: {papers_inserted} inserted, {papers_duplicate} duplicates, {papers_no_defs} no definitions")

        except Exception as e:
            logger.error(f"Database stage failed: {type(e).__name__}: {str(e)}", exc_info=True)
            metrics.record_error(
                ErrorCategory.PIPELINE_ERROR,
                f"Database stage failed: {str(e)}",
                {"stage": "database"}
            )
            raise
        finally:
            metrics.end_stage("database")

        logger.info("All stages complete")

        # generate and log summary
        summary = metrics.get_summary()
        print("\n" + summary + "\n")
        save_metrics_history(metrics)

        logger.info("=" * 80)
        logger.info(f"AURA Pipeline Complete - {today}")
        logger.info("=" * 80)

    except Exception as e:
        logger.critical(f"Pipeline failed catastrophically: {type(e).__name__}: {str(e)}", exc_info=True)

        # still generate summary to show what was accomplished before failure
        summary = metrics.get_summary()
        print("\n" + summary + "\n")

        # save metrics even on failure for debugging
        save_metrics_history(metrics)

        logger.info("=" * 80)
        logger.info(f"AURA Pipeline Failed - {today}")
        logger.info("=" * 80)

        raise


def clean_papers():
    """
    Delete locally stored papers after 7 days. Papers are only stored for immediate quality checks and troubleshooting.
    """
    try:
        expired = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')
        papers_dir = f"./data/pdfs/papers_{expired}"

        if os.path.exists(papers_dir):
            shutil.rmtree(papers_dir)
            logger.info(f"Cleaned up expired papers", extra={"date": expired, "dir": papers_dir})
        else:
            logger.debug(f"No papers to clean for date {expired}")

    except Exception as e:
        logger.error(f"clean_papers() failed: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    import schedule
    import time

    # run immediately on startup for testing
    logger.info("Starting AURA processor (test mode)")

    try:
        # job()
        # clean_papers()
        print("Not scraping until 2am")
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        sys.exit(1)

    # production scheduling (comment out for testing)
    schedule.every().day.at("02:00").do(job)
    schedule.every().day.at("01:45").do(clean_papers)
    
    logger.info("Scheduler started. Waiting for 2:00 AM...")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
