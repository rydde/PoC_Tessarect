from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
from itertools import zip_longest


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOCAL_TESSDATA_DIR = BASE_DIR / "tessdata"

# Use a mixed-language pass plus a Greek-only pass. The mixed pass helps with
# email, URLs, and Latin labels; the Greek-only pass helps avoid Latin letters
# being hallucinated into Greek words.
PRIMARY_LANGUAGE = "ell+eng"
FALLBACK_LANGUAGE = "ell"
PDF_RENDER_SCALE = 4
TESSERACT_PSM = "11"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTENSION = ".pdf"

GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
LATIN_RE = re.compile(r"[A-Za-z]")


def find_tesseract() -> str:
    tesseract = shutil.which("tesseract")
    if tesseract:
        return tesseract

    common_paths = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]
    for path in common_paths:
        if path.exists():
            return str(path)

    print("Tesseract was not found on PATH.")
    print("Install it, then make sure the 'tesseract' command works in PowerShell.")
    print("For Greek OCR, also install the Greek language data file: ell.traineddata")
    sys.exit(1)


def tesseract_env() -> dict[str, str]:
    env = os.environ.copy()
    if LOCAL_TESSDATA_DIR.exists():
        env["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA_DIR)
    return env


def normalize_ocr_text(text: str) -> str:
    text = text.replace("µ", "μ")
    text = re.sub(r"(\S)([ΙI]\.\s*Κ\.\s*Ε\.)", r"\1 \2", text)
    text = re.sub(r"\s+([.,:;])", r"\1", text)
    return text


def run_tesseract(tesseract: str, image_path: Path, language: str) -> str:
    command = [
        tesseract,
        str(image_path),
        "stdout",
        "-l",
        language,
        "--oem",
        "1",
        "--psm",
        TESSERACT_PSM,
    ]

    if LOCAL_TESSDATA_DIR.exists():
        command.extend(["--tessdata-dir", str(LOCAL_TESSDATA_DIR)])

    command.extend(
        [
            "-c",
            "preserve_interword_spaces=1",
            "-c",
            "user_defined_dpi=300",
        ]
    )

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=tesseract_env(),
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    return result.stdout.strip()


def looks_like_mixed_greek_error(line: str) -> bool:
    if "@" in line or "&" in line or "://" in line or "tax id" in line.lower():
        return False

    greek_count = len(GREEK_RE.findall(line))
    latin_count = len(LATIN_RE.findall(line))
    return greek_count >= 5 and latin_count >= 4


def choose_best_line(primary_line: str, fallback_line: str) -> str:
    primary = primary_line.strip()
    fallback = fallback_line.strip()

    if not primary:
        return fallback
    if not fallback:
        return primary

    primary_latin = len(LATIN_RE.findall(primary))
    fallback_latin = len(LATIN_RE.findall(fallback))

    if looks_like_mixed_greek_error(primary) and fallback_latin < primary_latin:
        return fallback

    return primary


def merge_ocr_text(primary_text: str, fallback_text: str) -> str:
    primary_lines = primary_text.splitlines()
    fallback_lines = fallback_text.splitlines()
    merged_lines = [
        choose_best_line(primary_line or "", fallback_line or "")
        for primary_line, fallback_line in zip_longest(primary_lines, fallback_lines)
    ]
    return normalize_ocr_text("\n".join(merged_lines).strip())


def ocr_image(tesseract: str, image_path: Path) -> str:
    primary_text = run_tesseract(tesseract, image_path, PRIMARY_LANGUAGE)
    fallback_text = run_tesseract(tesseract, image_path, FALLBACK_LANGUAGE)
    return merge_ocr_text(primary_text, fallback_text)


def ocr_pdf(tesseract: str, pdf_path: Path) -> str:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise RuntimeError("PDF support requires pypdfium2. Install it with: pip install pypdfium2")

    page_text = []
    pdf = pdfium.PdfDocument(str(pdf_path))

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for page_number, page in enumerate(pdf, start=1):
            bitmap = page.render(scale=PDF_RENDER_SCALE)
            image = bitmap.to_pil().convert("L")
            image_path = temp_path / f"{pdf_path.stem}_page_{page_number}.png"
            image.save(image_path)

            text = ocr_image(tesseract, image_path)
            page_text.append(f"--- Page {page_number} ---\n{text}")

    return "\n\n".join(page_text).strip()


def main() -> None:
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    tesseract = find_tesseract()
    input_files = sorted(
        file
        for file in INPUT_DIR.iterdir()
        if file.suffix.lower() in IMAGE_EXTENSIONS or file.suffix.lower() == PDF_EXTENSION
    )

    if not input_files:
        print(f"No images or PDFs found in: {INPUT_DIR}")
        print("Add a Greek text image or PDF, then run: python ocr_local.py")
        return

    for input_path in input_files:
        print(f"OCR: {input_path.name}")
        try:
            if input_path.suffix.lower() == PDF_EXTENSION:
                text = ocr_pdf(tesseract, input_path)
            else:
                text = ocr_image(tesseract, input_path)
        except RuntimeError as error:
            print(f"  Failed: {error}")
            continue

        output_path = OUTPUT_DIR / f"{input_path.stem}.txt"
        output_path.write_text(text + "\n", encoding="utf-8-sig")
        print(f"  Saved: {output_path.name}")


if __name__ == "__main__":
    main()
