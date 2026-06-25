from pathlib import Path
import json
import re
import sys
import urllib.error
import urllib.request


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# Use one of the models installed in your local Docker Ollama instance.
OLLAMA_MODEL = "gemma4:latest"
OLLAMA_URL = "http://localhost:11434/api/generate"

TAX_ID_RE = re.compile(
    r"(?:Α\.?\s*Φ\.?\s*Μ\.?|AFM|A\.?\s*F\.?\s*M\.?|Tax\s*ID)\D{0,20}(\d{7,12})",
    flags=re.IGNORECASE,
)
PERSON_LABEL_RE = re.compile(
    r"^(?:[οo©]\s*)?(?:Ονοματεπώνυμο|Όνομα|Name|Full\s+Name)\s*:\s*(.+)$",
    flags=re.IGNORECASE,
)
ROLE_LABEL_RE = re.compile(
    r"^(?:[οo©]\s*)?(?:Ιδιότητα|Ρόλος|Role|Title)\s*:\s*(.+)$",
    flags=re.IGNORECASE,
)
ORG_LABEL_RE = re.compile(r"^(?:Προς|To|Recipient)\s*:\s*(.+)$", flags=re.IGNORECASE)
ACRONYM_ORG_RE = re.compile(
    r"\b([A-ZΑ-ΩΆΈΉΊΌΎΏ]{2,})\s*\(([^)]{8,})\)"
)


def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        print(f"Ollama returned HTTP {error.code}.")
        print(error_body)
        sys.exit(1)
    except urllib.error.URLError as error:
        print("Could not connect to Ollama at http://localhost:11434.")
        print("Start Ollama, pull a model, then run this script again.")
        print(f"Details: {error}")
        sys.exit(1)

    if "response" not in data:
        print("Unexpected Ollama response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        sys.exit(1)

    return data["response"]


def normalize_text(text: str) -> str:
    text = text.replace("µ", "μ")
    text = re.sub(r"(\S)([ΙI]\.\s*Κ\.\s*Ε\.)", r"\1 \2", text)
    text = re.sub(r"\s+([.,:;])", r"\1", text)
    return text


def clean_name(value: str) -> str:
    value = normalize_text(value.strip())
    value = re.sub(r"^[οo©]\s+", "", value)
    return value.strip(" -")


def build_prompt(text: str) -> str:
    return f"""
Extract all person names, organization names, and tax IDs from the OCR text below.

The text is OCR output from a Greek business document. It may contain OCR mistakes.
Tax IDs may be labeled as AFM, Tax ID, A.F.M., or Greek equivalents.
Include recipient organizations that appear after labels like "Προς:".
Return only valid JSON. Do not add commentary.

Use this exact schema:
{{
  "people": [
    {{
      "name": "string",
      "tax_id": "string or null",
      "role_or_title": "string or null",
      "evidence": "short exact text snippet"
    }}
  ],
  "organizations": [
    {{
      "name": "string",
      "tax_id": "string or null",
      "evidence": "short exact text snippet"
    }}
  ],
  "tax_ids": [
    {{
      "tax_id": "string",
      "associated_name": "string or null",
      "evidence": "short exact text snippet"
    }}
  ]
}}

OCR text:
---
{text}
---
""".strip()


def ensure_list(extracted: dict, key: str) -> list:
    value = extracted.get(key)
    if not isinstance(value, list):
        value = []
        extracted[key] = value
    return value


def add_unique_item(items: list, item: dict, unique_key: str) -> None:
    new_value = item.get(unique_key)
    if not new_value:
        return

    for existing in items:
        if isinstance(existing, dict) and existing.get(unique_key) == new_value:
            for key, value in item.items():
                if existing.get(key) in (None, "") and value not in (None, ""):
                    existing[key] = value
            return

    items.append(item)


def apply_rule_based_safeguards(extracted: dict, text: str) -> dict:
    people = ensure_list(extracted, "people")
    organizations = ensure_list(extracted, "organizations")
    tax_ids = ensure_list(extracted, "tax_ids")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    last_person = None
    for index, line in enumerate(lines):
        person_match = PERSON_LABEL_RE.match(line)
        if person_match:
            name = clean_name(person_match.group(1))
            last_person = name
            role = None
            evidence_lines = [line]

            if index + 1 < len(lines):
                role_match = ROLE_LABEL_RE.match(lines[index + 1])
                if role_match:
                    role = clean_name(role_match.group(1))
                    evidence_lines.append(lines[index + 1])

            add_unique_item(
                people,
                {
                    "name": name,
                    "tax_id": None,
                    "role_or_title": role,
                    "evidence": "\n".join(evidence_lines),
                },
                "name",
            )

        org_match = ORG_LABEL_RE.match(line)
        if org_match:
            name = clean_name(org_match.group(1))
            add_unique_item(
                organizations,
                {
                    "name": name,
                    "tax_id": None,
                    "evidence": line,
                },
                "name",
            )

        for acronym, expansion in ACRONYM_ORG_RE.findall(line):
            add_unique_item(
                organizations,
                {
                    "name": f"{acronym} ({clean_name(expansion)})",
                    "tax_id": None,
                    "evidence": line,
                },
                "name",
            )

        tax_match = TAX_ID_RE.search(line)
        if tax_match:
            tax_id = tax_match.group(1)
            add_unique_item(
                tax_ids,
                {
                    "tax_id": tax_id,
                    "associated_name": last_person,
                    "evidence": line,
                },
                "tax_id",
            )
            if last_person:
                add_unique_item(
                    people,
                    {
                        "name": last_person,
                        "tax_id": tax_id,
                        "role_or_title": None,
                        "evidence": line,
                    },
                    "name",
                )

    return extracted


def extract_entities(input_text: Path) -> dict:
    text = normalize_text(input_text.read_text(encoding="utf-8-sig"))
    response_text = call_ollama(build_prompt(text))

    try:
        extracted = json.loads(response_text)
    except json.JSONDecodeError:
        print("Ollama did not return valid JSON. Raw response:")
        print(response_text)
        sys.exit(1)

    return apply_rule_based_safeguards(extracted, text)


def input_files_from_args() -> list[Path]:
    if len(sys.argv) > 1:
        return [Path(arg).resolve() for arg in sys.argv[1:]]

    return sorted(
        path for path in OUTPUT_DIR.glob("*.txt") if not path.name.endswith("_entities.txt")
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    input_files = input_files_from_args()
    if not input_files:
        print(f"No OCR text files found in: {OUTPUT_DIR}")
        print("Run ocr_local.py first.")
        sys.exit(1)

    for input_text in input_files:
        if not input_text.exists():
            print(f"Input text file not found: {input_text}")
            continue

        output_json = input_text.with_name(f"{input_text.stem}_entities.json")
        extracted = extract_entities(input_text)
        output_json.write_text(
            json.dumps(extracted, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8-sig",
        )

        print(f"Saved extracted entities to: {output_json}")
        print(json.dumps(extracted, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
