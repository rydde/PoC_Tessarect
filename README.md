# Greek OCR + Local AI Extraction Demo

This project demonstrates how we can take a Greek PDF document, read the text from it using OCR, and then ask a local AI model to extract useful business information such as names, organizations, and tax IDs.

The important point: the document is not English, but the pipeline can still read it and extract structured information.

## Demo Summary

Input:

```text
input/Greek_Doc.pdf
```

Step 1 output:

```text
output/Greek_Doc.txt
```

This is the Greek text extracted from the PDF.

Step 2 output:

```text
output/Greek_Doc_entities.json
```

This is the final structured result, for example:

```json
{
  "people": [
    {
      "name": "Γεώργιος Παπαδόπουλος",
      "tax_id": "012345678",
      "role_or_title": "Διευθυντής Στρατηγικού Σχεδιασμού"
    }
  ]
}
```

## End-To-End Flow

```text
Greek PDF
   |
   v
Python script: ocr_local.py
   |
   v
Tesseract OCR reads the document image
   |
   v
Greek text file: output/Greek_Doc.txt
   |
   v
Python script: extract_names_tax_ids_ollama.py
   |
   v
Ollama local AI model understands the text
   |
   v
Structured JSON: output/Greek_Doc_entities.json
```

## Simple Architecture Diagram

```text
+-------------------+       +----------------------+       +-------------------+
| input/Greek_Doc   | ----> | Tesseract OCR         | ----> | Greek text output |
| PDF document      |       | via Python            |       | .txt file         |
+-------------------+       +----------------------+       +-------------------+
                                                                  |
                                                                  v
                                                        +----------------------+
                                                        | Ollama local model   |
                                                        | via Python prompt    |
                                                        +----------------------+
                                                                  |
                                                                  v
                                                        +----------------------+
                                                        | Extracted entities   |
                                                        | JSON file            |
                                                        +----------------------+
```

## What This Demo Proves

This proof of concept shows that:

- A scanned or image-based Greek document can be converted into machine-readable text.
- Tesseract can handle non-English OCR when the right language data is installed.
- A local AI model can read the OCR result and extract business fields.
- The final output can be saved as JSON, which is easy for other systems to consume.
- The process can run locally, without sending the document to a cloud AI service.

## Concepts In Plain Language

## What Is OCR?

OCR means Optical Character Recognition.

In simple terms, OCR is the process of turning text inside an image or scanned document into real editable text.

Example:

```text
Before OCR:
  A PDF page or image that only looks like text.

After OCR:
  Actual text that Python can read, search, copy, and process.
```

Why this matters:

```text
Scanned PDF -> OCR -> Searchable text -> Business data extraction
```

Without OCR, the computer only sees pixels. With OCR, the computer can read the words.

## What Is Tesseract?

Tesseract is an open-source OCR engine.

Think of Tesseract as the reading machine. We give it an image or a rendered PDF page, and it tries to recognize the letters and words.

In this project, Tesseract reads Greek text from the PDF.

Important Tesseract language files used here:

```text
ell.traineddata  = Greek language OCR data
eng.traineddata  = English language OCR data
```

We use both:

```python
LANGUAGE = "ell+eng"
```

Why both? The document is mainly Greek, but it also contains mixed content such as:

```text
Email: info@bekas-logistics.gr
Tax ID
Logistics
```

Using Greek plus English helps Tesseract read mixed-language documents more accurately.

## What Is Ollama?

Ollama is a tool for running AI language models locally on your machine or in Docker.

In this demo, Ollama is running locally at:

```text
http://localhost:11434
```

We use Ollama after OCR.

Tesseract reads the text. Ollama understands the text.

```text
Tesseract = reads characters from the document
Ollama    = understands the meaning and extracts fields
```

For example, Tesseract gives us text like:

```text
Ονοματεπώνυμο: Γεώργιος Παπαδόπουλος
Α.Φ.Μ. (Tax ID): 012345678
```

Then Ollama turns that into structured JSON:

```json
{
  "name": "Γεώργιος Παπαδόπουλος",
  "tax_id": "012345678"
}
```

## What Is A Prompt?

A prompt is the instruction we send to the AI model.

It tells the model what to do.

In this project, the prompt basically says:

```text
Read this Greek OCR text.
Find person names, organization names, and tax IDs.
Return the answer as JSON.
```

The prompt is important because the AI model is flexible. If we ask a vague question, we may get a vague answer. If we ask for a strict JSON structure, we get output that is easier to use in software.

## Data Flow With Responsibilities

```text
1. PDF input
   Responsibility: source document

2. PDF rendering
   Responsibility: convert PDF page into a high-resolution image

3. Tesseract OCR
   Responsibility: convert image text into real text

4. OCR cleanup
   Responsibility: fix known OCR issues such as Greek/English character confusion

5. Ollama prompt
   Responsibility: ask the AI model to extract specific fields

6. JSON output
   Responsibility: store extracted data in a structured format
```

## Current Folder Layout

```text
PoC_Tessarect/
  input/
    Greek_Doc.pdf

  output/
    Greek_Doc.txt
    Greek_Doc_entities.json

  tessdata/
    ell.traineddata
    eng.traineddata

  ocr_local.py
  extract_names_tax_ids_ollama.py
  README.md
```

## Script 1: OCR The Greek PDF

Run:

```powershell
.\.venv\Scripts\python.exe ocr_local.py
```

What it does:

```text
1. Looks inside the input folder.
2. Finds Greek_Doc.pdf.
3. Converts the PDF page into a high-resolution image.
4. Sends the image to Tesseract.
5. Saves extracted Greek text into output/Greek_Doc.txt.
```

Important settings:

```python
LANGUAGE = "ell+eng"
PDF_RENDER_SCALE = 4
TESSERACT_PSM = "11"
```

Meaning:

```text
ell+eng = read Greek and English
scale 4 = render the PDF at higher quality before OCR
psm 11  = let Tesseract find sparse text across the full page
```

## Script 2: Extract Names And Tax IDs

Run:

```powershell
.\.venv\Scripts\python.exe extract_names_tax_ids_ollama.py
```

What it does:

```text
1. Reads output/Greek_Doc.txt.
2. Sends the OCR text to Ollama.
3. Asks the model to find people, organizations, and tax IDs.
4. Saves the result into output/Greek_Doc_entities.json.
```

The Ollama model currently used:

```python
OLLAMA_MODEL = "gemma4:latest"
```

## Final Output Example

The final JSON includes:

```json
{
  "people": [
    {
      "name": "Γεώργιος Παπαδόπουλος",
      "tax_id": "012345678",
      "role_or_title": "Διευθυντής Στρατηγικού Σχεδιασμού"
    }
  ],
  "organizations": [
    {
      "name": "ΜΠΕΚΑΣ ΕΜΠΟΡΙΚΗ Ι.Κ.Ε."
    },
    {
      "name": "Διεύθυνση Οικονομικών Υπηρεσιών"
    },
    {
      "name": "ΑΑΔΕ (Ανεξάρτητη Αρχή Δημοσίων Εσόδων)"
    }
  ]
}
```

## Why OCR Cleanup Is Needed

OCR is not always perfect, especially when a document mixes languages.

For example, Greek letters can sometimes look similar to English letters. Tesseract may incorrectly read:

```text
Ανεξάρτητη Αρχή Δημοσίων Eoddwv
```

when the correct text is:

```text
Ανεξάρτητη Αρχή Δημοσίων Εσόδων
```

So the Python code includes a small cleanup step for known OCR mistakes in this demo document.

This is normal in OCR projects. Production systems usually combine:

```text
OCR settings + language data + cleanup rules + AI extraction
```

## Demo Talking Points

Use these points when presenting:

- This is a local pipeline for reading non-English documents.
- Tesseract handles the OCR part.
- Ollama handles the understanding and extraction part.
- The final JSON can be passed to another system, database, or API.
- The example uses Greek, but the same idea can work for other languages if Tesseract language data is available.
- The document does not need to be sent to a cloud model for this demo.

## Demo Commands

Run OCR:

```powershell
.\.venv\Scripts\python.exe ocr_local.py
```

Run extraction:

```powershell
.\.venv\Scripts\python.exe extract_names_tax_ids_ollama.py
```

Open final result:

```text
output/Greek_Doc_entities.json
```

## Requirements

Installed or available:

```text
Python
Tesseract OCR
Greek Tesseract language data: ell.traineddata
English Tesseract language data: eng.traineddata
Ollama running locally in Docker
An Ollama model such as gemma4:latest
```

Ollama should respond at:

```text
http://localhost:11434
```

## One-Sentence Explanation

This demo converts a Greek PDF into readable text using Tesseract OCR, then uses a local Ollama AI model to extract names, organizations, and tax IDs into structured JSON.
