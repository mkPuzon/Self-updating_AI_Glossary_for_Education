'''process_text.py

Uses LLMs to extract keywords and definitions from text.

Note for context window sizes:
32k = 32768
64k = 65536
128k = 131072
256k = 262144
512k = 524288
1M = 1048576

Aug 2025
'''
import os
import re
import sys
import json
import time
import requests
from typing import Tuple, Optional, Dict, Any, List

from openai import OpenAI
from dotenv import load_dotenv
from src.metrics import PipelineMetrics, ErrorCategory
from src.logger_config import get_logger

logger = get_logger(__name__)

def query_keywords(abstract_txt: str, model: str = "gemma3:4b") -> Tuple[str, float, Optional[str]]:
    """
    Query Ollama model to extract keywords from abstract.

    Args:
        abstract_txt: Paper abstract text
        model: Ollama model to use

    Returns:
        Tuple of (response, duration, error_msg)
    """
    ollama_url = os.getenv("OLLAMA_API")
    sys_prompt = os.getenv("KEYWORD_PROMPT_1")

    if not ollama_url:
        error_msg = "OLLAMA_API environment variable not set"
        logger.error(error_msg)
        return "", 0.0, error_msg

    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "prompt": sys_prompt + abstract_txt,
        "stream": True,
        "options": {
            "num_ctx": 65536
        }
    }

    model_response = ""
    t0 = time.time()

    try:
        logger.debug(f"Querying Ollama for keywords", extra={"model": model})

        with requests.post(ollama_url, headers=headers, json=data, stream=True, timeout=60) as response:
            if response.status_code != 200:
                duration = time.time() - t0
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"Ollama keyword query failed: {error_msg}", extra={"model": model})
                return "", duration, error_msg

            for line in response.iter_lines():
                if line:
                    try:
                        json_data = json.loads(line.decode('utf-8'))
                        text = json_data.get("response", "")
                        model_response += text
                    except json.JSONDecodeError:
                        continue

        duration = time.time() - t0
        logger.info(f"Keywords extracted", extra={"model": model, "duration": duration, "response_length": len(model_response)})
        return model_response, duration, None

    except requests.exceptions.Timeout:
        duration = time.time() - t0
        error_msg = "Request timeout (60s)"
        logger.error(f"Ollama keyword query timeout", extra={"model": model, "duration": duration})
        return "", duration, error_msg

    except requests.exceptions.RequestException as e:
        duration = time.time() - t0
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Ollama keyword query failed: {error_msg}", extra={"model": model})
        return "", duration, error_msg

    except Exception as e:
        duration = time.time() - t0
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Unexpected error in keyword query: {error_msg}", extra={"model": model})
        return "", duration, error_msg

def query_definitions(keywords: List[str], paper_txt: str, model: str = "gemma3:1b",
                      openai: bool = False) -> Tuple[str, float, Optional[str]]:
    """
    Query LLM to extract definitions for keywords from paper text.

    Args:
        keywords: List of keywords to define
        paper_txt: Full paper text
        model: Model to use (Ollama model name or "gpt-5-mini" for OpenAI)
        openai: Whether to use OpenAI API

    Returns:
        Tuple of (response, duration, error_msg)
    """
    if not keywords:
        return "{}", 0.0, "No keywords provided"

    sys_prompt = f"{os.getenv('DEFINTION_PROMPT_1')} {keywords}. Here is the paper itself: "

    # OpenAI path
    if openai:
        logger.debug("Querying OpenAI for definitions", extra={"model": "gpt-5-mini", "num_keywords": len(keywords)})
        t0 = time.time()

        try:
            client = OpenAI(api_key=os.environ.get("OPENAI_KEY"))
            response = client.responses.create(
                model=model,
                instructions="You are a Python dictionary generator. Do not return anything except for a valid Python dictionary.",
                input=sys_prompt + paper_txt,
            )
            duration = time.time() - t0
            logger.info(f"Definitions extracted from OpenAI", extra={"duration": duration, "response_length": len(response.output_text)})
            return response.output_text, duration, None

        except Exception as e:
            duration = time.time() - t0
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"OpenAI definition query failed: {error_msg}", extra={"duration": duration})
            return "", duration, error_msg

    ollama_url = os.getenv("OLLAMA_API")
    if not ollama_url:
        error_msg = "OLLAMA_API environment variable not set"
        logger.error(error_msg)
        return "", 0.0, error_msg

    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "prompt": sys_prompt + paper_txt,
        "stream": True,
        "options": {
            "num_ctx": 65536
        }
    }

    model_response = ""
    t0 = time.time()

    try:
        logger.debug(f"Querying Ollama for definitions", extra={"model": model, "num_keywords": len(keywords)})

        with requests.post(ollama_url, headers=headers, json=data, stream=True, timeout=120) as response:
            if response.status_code != 200:
                duration = time.time() - t0
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"Ollama definition query failed: {error_msg}", extra={"model": model})
                return "", duration, error_msg

            for line in response.iter_lines():
                if line:
                    try:
                        json_data = json.loads(line.decode('utf-8'))
                        text = json_data.get("response", "")
                        model_response += text
                    except json.JSONDecodeError:
                        continue

        duration = time.time() - t0
        logger.info(f"Definitions extracted", extra={"model": model, "duration": duration, "response_length": len(model_response)})
        return model_response, duration, None

    except requests.exceptions.Timeout:
        duration = time.time() - t0
        error_msg = "Request timeout (120s)"
        logger.error(f"Ollama definition query timeout", extra={"model": model, "duration": duration})
        return "", duration, error_msg

    except requests.exceptions.RequestException as e:
        duration = time.time() - t0
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Ollama definition query failed: {error_msg}", extra={"model": model})
        return "", duration, error_msg

    except Exception as e:
        duration = time.time() - t0
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Unexpected error in definition query: {error_msg}", extra={"model": model})
        return "", duration, error_msg

def check_keywords(keywords_str: str) -> Tuple[List[str], bool, Optional[str]]:
    """
    Parse keywords from LLM response string.

    Args:
        keywords_str: Raw LLM response containing keywords list

    Returns:
        Tuple of (keywords_list, success, error_msg)
    """
    if not keywords_str or not keywords_str.strip():
        error_msg = "Empty response from model"
        logger.warning("Keyword parsing failed: empty response")
        return [], False, error_msg

    pattern = r'\[(.*?)\]'
    match = re.search(pattern, keywords_str, re.DOTALL)

    if match:
        list_content = match.group(1)
        keywords_list = re.findall(r'["\']([^"\']+)["\']', list_content)

        if keywords_list:
            logger.debug(f"Parsed {len(keywords_list)} keywords successfully")
            return keywords_list, True, None
        else:
            error_msg = "Found list brackets but no quoted keywords inside"
            truncated_response = keywords_str[:500] + "..." if len(keywords_str) > 500 else keywords_str
            logger.warning(f"Keyword parsing failed: {error_msg}", extra={"raw_response": truncated_response})
            return [], False, error_msg
    else:
        error_msg = "Cannot find valid Python list in response (no square brackets)"
        truncated_response = keywords_str[:500] + "..." if len(keywords_str) > 500 else keywords_str
        logger.warning(f"Keyword parsing failed: {error_msg}", extra={"raw_response": truncated_response})
        return [], False, error_msg

def check_definitions(definitions_str: str) -> Tuple[Dict[str, str], bool, Optional[str]]:
    """
    Parse definitions dictionary from LLM response string.

    Args:
        definitions_str: Raw LLM response containing definitions dict

    Returns:
        Tuple of (definitions_dict, success, error_msg)
    """
    if not definitions_str or not definitions_str.strip():
        error_msg = "Empty response from model"
        logger.warning("Definition parsing failed: empty response")
        return {}, False, error_msg

    dict_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    dict_match = re.search(dict_pattern, definitions_str, re.DOTALL)

    if dict_match:
        try:
            import ast
            definitions_dict = ast.literal_eval(dict_match.group())

            if isinstance(definitions_dict, dict):
                # Filter out None values
                valid_defs = {k: v for k, v in definitions_dict.items() if v and v != 'None'}
                logger.debug(f"Parsed {len(valid_defs)} valid definitions successfully")
                return valid_defs, True, None
            else:
                error_msg = f"Parsed value is not a dict (got {type(definitions_dict).__name__})"
                truncated_response = definitions_str[:500] + "..." if len(definitions_str) > 500 else definitions_str
                logger.warning(f"Definition parsing failed: {error_msg}", extra={"raw_response": truncated_response})
                return {}, False, error_msg

        except (ValueError, SyntaxError) as e:
            error_msg = f"Failed to parse dictionary: {type(e).__name__}: {str(e)}"
            truncated_response = definitions_str[:500] + "..." if len(definitions_str) > 500 else definitions_str
            logger.warning(f"Definition parsing failed: {error_msg}", extra={"raw_response": truncated_response})
            return {}, False, error_msg

    else:
        error_msg = "No dictionary found in model response (no curly braces)"
        truncated_response = definitions_str[:500] + "..." if len(definitions_str) > 500 else definitions_str
        logger.warning(f"Definition parsing failed: {error_msg}", extra={"raw_response": truncated_response})
        return {}, False, error_msg

def clean_keywords(definitions: Dict[str, str]) -> int:
    """
    Count keywords with valid definitions (excluding 'None' values).

    Args:
        definitions: Dictionary of keyword -> definition

    Returns:
        Count of keywords with valid definitions
    """
    num_keywords_defined = 0

    for word, definition in definitions.items():
        if definition and definition != 'None':
            num_keywords_defined += 1

    return num_keywords_defined
            
    
def generate_keywords_and_defs(batch_filepath: str, kwd_model: str = "gemma3:12b",
                               def_model: str = "llama3.3", openai: bool = False,
                               metrics: Optional[PipelineMetrics] = None) -> Tuple[int, int, int]:
    """
    Extract keywords and definitions from papers using LLMs.

    Args:
        batch_filepath: Path to JSON file with paper metadata
        kwd_model: Model to use for keyword extraction
        def_model: Model to use for definition extraction
        openai: Whether to use OpenAI for definitions
        metrics: Optional PipelineMetrics object for tracking

    Returns:
        Tuple of (num_papers, num_keywords_extracted, num_papers_with_defs)
    """
    load_dotenv()

    logger.info(f"Starting LLM processing", extra={
        "file": batch_filepath,
        "kwd_model": kwd_model,
        "def_model": def_model,
        "use_openai": openai
    })

    try:
        with open(batch_filepath, "r") as f:
            metadata_dict = json.load(f)

    except FileNotFoundError:
        error_msg = f"File not found: {batch_filepath}"
        logger.error(error_msg)
        if metrics:
            metrics.record_error(ErrorCategory.VALIDATION_ERROR, error_msg, {"file": batch_filepath})
        return 0, 0, 0

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in file: {str(e)}"
        logger.error(error_msg, extra={"file": batch_filepath})
        if metrics:
            metrics.record_error(ErrorCategory.VALIDATION_ERROR, error_msg, {"file": batch_filepath})
        return 0, 0, 0

    updated_dict = {}
    num_kwds_generated = 0
    num_papers_with_defs = 0
    num_papers = len(metadata_dict.keys())

    logger.info(f"Processing {num_papers} papers for keyword/definition extraction")

    for i in range(num_papers):
        paper_id = str(i)
        paper = metadata_dict[paper_id]
        arxiv_url = paper.get('full_arxiv_url', 'Unknown')

        if metrics:
            metrics.increment("llm.papers_processed")

        logger.debug(f"Processing paper {i+1}/{num_papers}", extra={"arxiv_url": arxiv_url})

        # Check if paper has text
        if not paper.get('full_text'):
            logger.info(f"Skipping paper (no full text)", extra={"paper_id": paper_id, "arxiv_url": arxiv_url})
            paper["keywords"] = []
            paper["definitions"] = {}
            updated_dict[paper_id] = paper

            if metrics:
                metrics.increment("llm.papers_skipped_no_text")
            continue

        # extract keywords from abstract
        kwd_response, kwd_duration, kwd_error = query_keywords(
            abstract_txt=paper['abstract'],
            model=kwd_model
        )

        if kwd_error:
            if metrics:
                metrics.increment("llm.keywords_extraction_failed")
                metrics.record_error(
                    ErrorCategory.LLM_ERROR,
                    f"Keyword query failed: {kwd_error}",
                    {"paper_id": paper_id, "arxiv_url": arxiv_url, "model": kwd_model}
                )
            paper["keywords"] = []
            paper["definitions"] = {}
            updated_dict[paper_id] = paper
            continue

        keywords, kwd_parse_success, kwd_parse_error = check_keywords(kwd_response)

        if not kwd_parse_success or not keywords:
            if metrics:
                metrics.increment("llm.keywords_extraction_failed")
                metrics.record_error(
                    ErrorCategory.LLM_ERROR,
                    f"Keyword parsing failed: {kwd_parse_error}",
                    {"paper_id": paper_id, "arxiv_url": arxiv_url, "raw_response": kwd_response[:200]}
                )
            paper["keywords"] = []
            paper["definitions"] = {}
            updated_dict[paper_id] = paper
            continue

        if metrics:
            metrics.increment("llm.keywords_extraction_success")
            metrics.increment("llm.total_keywords_extracted", len(keywords))

        logger.info(f"Extracted {len(keywords)} keywords", extra={"paper_id": paper_id, "keywords": keywords})

        # extract definitions for keywords
        def_response, def_duration, def_error = query_definitions(
            keywords=keywords,
            paper_txt=paper['full_text'],
            model=def_model,
            openai=openai
        )

        if def_error:
            if metrics:
                metrics.increment("llm.definitions_extraction_failed")
                metrics.record_error(
                    ErrorCategory.LLM_ERROR,
                    f"Definition query failed: {def_error}",
                    {"paper_id": paper_id, "arxiv_url": arxiv_url, "model": def_model, "openai": openai}
                )
            paper["keywords"] = keywords
            paper["definitions"] = {}
            updated_dict[paper_id] = paper
            continue

        definitions, def_parse_success, def_parse_error = check_definitions(def_response)

        if not def_parse_success:
            if metrics:
                metrics.increment("llm.definitions_extraction_failed")
                metrics.record_error(
                    ErrorCategory.LLM_ERROR,
                    f"Definition parsing failed: {def_parse_error}",
                    {"paper_id": paper_id, "arxiv_url": arxiv_url, "raw_response": def_response[:200]}
                )
            paper["keywords"] = keywords
            paper["definitions"] = {}
            updated_dict[paper_id] = paper
            continue

        if metrics:
            metrics.increment("llm.definitions_extraction_success")

        num_valid_defs = clean_keywords(definitions)
        num_kwds_generated += num_valid_defs

        if definitions:
            num_papers_with_defs += 1

        if metrics:
            metrics.increment("llm.total_definitions_extracted", num_valid_defs)
            keywords_without_defs = len(keywords) - num_valid_defs
            if keywords_without_defs > 0:
                metrics.increment("llm.keywords_without_definitions", keywords_without_defs)

        logger.info(f"Extracted {num_valid_defs} valid definitions", extra={
            "paper_id": paper_id,
            "total_keywords": len(keywords),
            "valid_definitions": num_valid_defs
        })

        paper["keywords"] = keywords
        paper["definitions"] = definitions
        updated_dict[paper_id] = paper

    # save updated metadata
    try:
        with open(batch_filepath, "w") as f:
            json.dump(updated_dict, f, indent=2)
        logger.info(f"Saved updated metadata to {batch_filepath}")

    except Exception as e:
        error_msg = f"Failed to save metadata: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, extra={"file": batch_filepath})
        if metrics:
            metrics.record_error(ErrorCategory.VALIDATION_ERROR, error_msg, {"file": batch_filepath})

    logger.info(f"LLM processing complete", extra={
        "papers_processed": num_papers,
        "keywords_extracted": num_kwds_generated,
        "papers_with_definitions": num_papers_with_defs
    })

    return num_papers, num_kwds_generated, num_papers_with_defs

if __name__ == "__main__":
    from datetime import datetime
    today = datetime.today().strftime("%Y-%m-%d")
        
    load_dotenv()

    file_path = f"metadata/metadata_{today}.json"
    num_papers, num_kwds, num_dicts = generate_keywords_and_defs(file_path, kwd_model="gemma3:12b", def_model="gemma3:12b", verbose=False)
    # num_papers, num_kwds, num_dicts = generate_keywords_and_defs(file_path, kwd_model="gemma3:12b", def_model="phi3:14b", verbose=False)
    print(f"[{sys.argv[1]}] {(num_kwds/(num_papers*3))*100:.2f}% keyword extraction rate | Out of {num_papers} total papers: num papers w/ definitions={num_dicts}, num keywords extracted={num_kwds}")
    
    