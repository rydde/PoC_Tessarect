from pathlib import Path
import json
import re
import sys
import urllib.error
import urllib.request


BASE_DIR = Path(__file__).resolve().parent
INPUT_TEXT = BASE_DIR / "output" / "Greek_Doc.txt"
OUTPUT_JSON = BASE_DIR / "output" / "Greek_Doc_entities.json"

# Use one of the models installed in your local Docker Ollama instance.
OLLAMA_MODEL = "gemma4:latest"
OLLAMA_URL = "http://localhost:11434/api/generate"

TEXT_FIXES = {
    "ΜΠΕΚΑΣ ΕΜΠΟΡΙΚΗΙ.Κ.Ε.": "ΜΠΕΚΑΣ ΕΜΠΟΡΙΚΗ Ι.Κ.Ε.",
    "Ανεξάρτητη Αρχή Δημοσίων Eoddwv": "Ανεξάρτητη Αρχή Δημοσίων Εσόδων",
    "Οικονοµικών": "Οικονομικών",
    "οικονοµικών": "οικονομικών",
}


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


def build_prompt(text: str) -> str:
    return f"""
Extract all person names, organization names, and tax IDs from the OCR text below.

The text is Greek OCR output, so tolerate OCR mistakes.
Greek tax IDs may be labeled as AFM, Tax ID, A.F.M., or Greek equivalents.
Include organizations after labels like "Προς:" as recipient organizations.
Normalize obvious OCR spelling artifacts in extracted names, but keep evidence from the source text.

Return only valid JSON using this schema:
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


def normalize_text(text: str) -> str:
    for wrong, correct in TEXT_FIXES.items():
        text = text.replace(wrong, correct)
    return text


def normalize_value(value):
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    return value


def add_recipient_organizations(extracted: dict, text: str) -> dict:
    organizations = extracted.setdefault("organizations", [])
    existing_names = {
        organization.get("name")
        for organization in organizations
        if isinstance(organization, dict)
    }

    for match in re.finditer(r"^Προς:\s*(.+)$", text, flags=re.MULTILINE):
        name = match.group(1).strip()
        if name and name not in existing_names:
            organizations.append(
                {
                    "name": name,
                    "tax_id": None,
                    "evidence": match.group(0).strip(),
                }
            )
            existing_names.add(name)

    return extracted


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not INPUT_TEXT.exists():
        print(f"Input text file not found: {INPUT_TEXT}")
        print("Run ocr_local.py first.")
        sys.exit(1)

    text = normalize_text(INPUT_TEXT.read_text(encoding="utf-8-sig"))
    prompt = build_prompt(text)
    response_text = call_ollama(prompt)

    try:
        extracted = json.loads(response_text)
    except json.JSONDecodeError:
        print("Ollama did not return valid JSON. Raw response:")
        print(response_text)
        sys.exit(1)

    extracted = normalize_value(extracted)
    extracted = add_recipient_organizations(extracted, text)

    OUTPUT_JSON.write_text(
        json.dumps(extracted, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8-sig",
    )

    print(f"Saved extracted entities to: {OUTPUT_JSON}")
    print(json.dumps(extracted, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
