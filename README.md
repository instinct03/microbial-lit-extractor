# Microbial Literature Extractor

Automated tool for extracting bacterial organisms, culture media, and metadata 
from scientific PDFs using LLM-based parsing.

Built as a personal research utility during my B.Sc. Industrial Microbiology 
studies at [your university], to assist with literature review workflows.

## What it does
- Batch processes multiple PDFs from a local folder
- Extracts: paper title, main topic, bacterial organisms (with page numbers), culture media focus
- Outputs structured JSON per paper
- Optional CSV export via --export flag

## How to use
1. Place PDFs in the `papers/` folder
2. Run: `python extract_text.py`
3. Add `--export` for CSV output
4. Add `--overwrite` to reprocess existing files
5. Results saved to `outputs/`

## Requirements
- Python 3.x
- pypdf
- requests
- An OpenRouter API key (add it to the `api_key` variable in the script)

## Built with
- [pypdf](https://pypdf.readthedocs.io/)
- [OpenRouter API](https://openrouter.ai/)
- LLM model: meta-llama/llama-3.1-8b-instruct

## Status
Functional and Under occasional improvement.
