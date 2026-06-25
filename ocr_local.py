from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOCAL_TESSDATA_DIR = BASE_DIR / "tessdata"

# Use "ell+eng" for Greek documents that may contain English words, email, URLs,
# or Latin labels such as "Tax ID".
LANGUAGE = "ell+eng"
PDF_RENDER_SCALE = 4
TESSERACT_PSM = "11"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTENSION = ".pdf"

OCR_TEXT_FIXES = {
    "ΜΠΕΚΑΣ ΕΜΠΟΡΙΚΗΙ.Κ.Ε.": "ΜΠΕΚΑΣ ΕΜΠΟΡΙΚΗ Ι.Κ.Ε.",
    "Ανεξάρτητη Αρχή Δημοσίων Eoddwv": "Ανεξάρτητη Αρχή Δημοσίων Εσόδων",
    "Οικονοµικών": "Οικονομικών",
    "οικονοµικών": "οικονομικών",
    "επίσηµα": "επίσημα",
    "συστήµατά": "συστήματά",
    "Παραμένουµε": "Παραμένουμε",
}


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
    for wrong, correct in OCR_TEXT_FIXES.items():
        text = text.replace(wrong, correct)
    return text


def ocr_image(tesseract: str, image_path: Path) -> str:
    command = [
        tesseract,
        str(image_path),
        "stdout",
        "-l",
        LANGUAGE,
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

    return normalize_ocr_text(result.stdout.strip())


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
