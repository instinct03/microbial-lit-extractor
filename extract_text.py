from pypdf import PdfReader
import json
import csv
import sys
import requests
import os

EXPORT_CSV = "--export" in sys.argv
print("DEBUG: EXPORT_CSV =", EXPORT_CSV)
OVERWRITE = "--overwrite" in sys.argv
print("DEBUG: OVERWRITE =", OVERWRITE)


def call_llm(prompt):
    api_key = "REDACTED" # Add your OpenRouter API key here

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload
    )

    data = response.json()
    return data["choices"][0]["message"]["content"]


def validate_extraction(data):
    errors = []

    if not data["title"]["value"] or not data["title"]["pages"]:
        errors.append("Title missing or unpaged")

    if data["main_topic"]["value"] != "Not reported":
        if len(data["main_topic"]["pages"]) == 0:
            errors.append("Main topic has no pages")

    if len(data["bacterial_organisms"]["values"]) != len(
        data["bacterial_organisms"]["pages"]
    ):
        errors.append("Organism values/pages length mismatch")

    return errors


def export_to_csv(data, filename):
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Field", "Value", "Pages (PDF)"])

        writer.writerow(["Title", data["title"]["value"], data["title"]["pages"]])
        writer.writerow(["Main Topic", data["main_topic"]["value"], data["main_topic"]["pages"]])

        for org, page in zip(
            data["bacterial_organisms"]["values"],
            data["bacterial_organisms"]["pages"]
        ):
            writer.writerow(["Bacterial Organism", org, f"[{page}]"])

        writer.writerow([
            "Culture Media Focus",
            data["culture_media_focus"].get("value", "Not reported"),
            data["culture_media_focus"].get("pages", [])
        ])


# ---- BATCH MODE ----

PAPERS_DIR = "papers"
OUTPUT_DIR = "outputs"

os.makedirs(OUTPUT_DIR, exist_ok=True)

if not os.path.exists(PAPERS_DIR):
    print(f"Creating missing folder: {PAPERS_DIR}")
    os.makedirs(PAPERS_DIR)
    print("Put PDFs in this folder and rerun.")
    exit(0)

pdf_files = [f for f in os.listdir(PAPERS_DIR) if f.lower().endswith(".pdf")]

for pdf in pdf_files:           
    pdf_path = os.path.join(PAPERS_DIR, pdf)
    print(f"\n=== Processing {pdf} ===")

    reader = PdfReader(pdf_path)

    pages = {}
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        pages[i] = text if text else ""

    print(f"Loaded {len(pages)} pages.\n")

    prompt = """
You are a STRICT information extraction system for scientific papers.

ABSOLUTE RULES:
- DO NOT summarize.
- DO NOT paraphrase.
- DO NOT infer or generalize.
- ONLY copy text that appears explicitly in the paper.
- If a valid extractive sentence does not exist, return "Not reported".
- EVERY extracted value MUST be traceable to the paper text.
- Pages are mandatory. If no page can be given, return "Not reported".

TASK:
Extract the following information using ONLY the provided page texts.

RETURN ONLY VALID JSON in the exact schema below.
NO explanations. NO extra keys.

SCHEMA:
{
  "title": {
    "value": "",
    "pages": []
  },
  "main_topic": {
    "value": "",
    "pages": []
  },
  "bacterial_organisms": {
    "values": [],
    "pages": []
  },
  "culture_media_focus": {
    "value": "",
    "pages": []
  }
}

FIELD RULES:

TITLE:
- Must be copied verbatim from the paper.
- Usually appears on the first page.

MAIN_TOPIC:
- Must be a sentence copied ≥70% verbatim from the paper.
- Prefer abstract or introduction.
- No phrases like "this paper reviews", "this study aims", etc.

MAIN_TOPIC (ADDITIONAL RULE):
- Prefer sentences that specify scope, context, or constraints
  (e.g. geographic region, resource setting, clinical context).
- Avoid generic statements unless no scoped sentence exists.

BACTERIAL_ORGANISMS:
- Include ONLY bacteria.
- Exclude fungi, yeast, algae, protozoa.
- Organism name must appear explicitly.
- Values and pages arrays MUST be the same length.

BACTERIAL ORGANISMS (CROSS-DOMAIN VALIDATION RULES):
- MUST be bacteria or archaea taxa.
- EXCLUDE viruses (e.g. SARS-CoV-2), fungi, yeasts, algae, protozoa, helminths, and eukaryotic cells.
- EXCLUDE culture media (e.g. Mueller-Hinton agar, blood agar, nutrient broth, LB broth).
- EXCLUDE supplements, buffers, reagents, enzymes, and molecules (e.g. IPTG, ATP, plasmids).
- EXCLUDE mammalian or animal cell lines (e.g. HEK293, Caco-2).
- EXCLUDE antibiotics and drugs (e.g. ampicillin, kanamycin).
- EXCLUDE generic terms (e.g. bacteria, Gram-negative, microbes).
- ALLOW genus-only or genus-species format (e.g. Pseudomonas OR Pseudomonas aeruginosa).
- Strain-level names are allowed if bacterial (e.g. E. coli K-12 MG1655).
- Values and pages MUST align 1:1.
- If multiple organisms appear on the same page, repeat the page number so that values[] and pages[] have equal length.
- If a virus is detected in the text, ignore it and do NOT include it in the output.

TAXONOMIC PREFERENCE:
- If species-level is given, prefer it.
- If only genus-level is given, accept it.
- If only higher-level (family/order) is given, return Not reported.


CULTURE_MEDIA_FOCUS:
- Use an extractive or near-extractive sentence.
- No evaluative adjectives.
- If culture media is not explicitly discussed, return "Not reported".

If any rule cannot be satisfied, return "Not reported" for that field.

PAGE TEXTS BELOW:
"""

    for page_num, text in pages.items():
        prompt += f"\n--- Page {page_num} ---\n{text[:1500]}\n"

    raw_json = call_llm(prompt)
    print("MODEL RAW OUTPUT:")
    print(raw_json)

    raw = raw_json.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.split("json")[-1].strip()

    try:
        extracted_json = json.loads(raw)
    except Exception as e:
        print(f"JSON parse error in {pdf}:", e)
        continue

            # ---- NORMALIZE PAGE NUMBERS ----
    if "bacterial_organisms" in extracted_json:
        pages_list = extracted_json["bacterial_organisms"].get("pages", [])
        extracted_json["bacterial_organisms"]["pages"] = [
            int(p) for p in pages_list
            if isinstance(p, (int, str)) and str(p).isdigit()
        ]

    # ---- FORCE ORGANISM / PAGE ALIGNMENT ----
    if "bacterial_organisms" in extracted_json:
        vals = extracted_json["bacterial_organisms"].get("values", [])
        pgs = extracted_json["bacterial_organisms"].get("pages", [])

        if len(vals) > len(pgs) and len(pgs) > 0:
            pgs = pgs + [pgs[-1]] * (len(vals) - len(pgs))
        elif len(pgs) > len(vals):
            pgs = pgs[:len(vals)]

        extracted_json["bacterial_organisms"]["pages"] = pgs

    # ---- VALIDATION ----
    errors = validate_extraction(extracted_json)
    if errors:
        print(f"VALIDATION ERRORS in {pdf}:")
        for e in errors:
            print("-", e)
        continue

    print(f"Extraction valid for {pdf}")

    base = os.path.splitext(pdf)[0]
    out_json = os.path.join(OUTPUT_DIR, base + ".json")

    if os.path.exists(out_json) and not OVERWRITE:
        print(f"{out_json} already exists — use --overwrite to replace")
        continue

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(extracted_json, f, indent=2)

    print(f"Saved → {out_json}")

    if EXPORT_CSV:
        out_csv = os.path.join(OUTPUT_DIR, base + ".csv")
        export_to_csv(extracted_json, out_csv)
        print(f"Saved CSV → {out_csv}")

