"""
ocr_extract.py
--------------
Extracts text from an uploaded ID document image (using OpenCV for
pre-processing + Tesseract OCR), pulls out likely Name / DOB / ID-number
fields, and cross-checks them against what the user typed into the
registration form. A mismatch (e.g., form name != document name) is a
strong fraud signal in real KYC systems.
"""

import re
import difflib
import cv2
import os
import pytesseract

if os.name == "nt":
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path


def _preprocess(image_path: str):
    """Grayscale + threshold to improve OCR accuracy on scanned/photographed IDs."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    return thresh


def extract_text_from_image(image_path: str) -> str:
    processed = _preprocess(image_path)
    return pytesseract.image_to_string(processed)


def parse_fields(raw_text: str) -> dict:
    """Best-effort extraction of Name / DOB / ID number from OCR text."""
    fields = {"name": None, "dob": None, "id_number": None}

    name_match = re.search(r"Name\s*[:\-]\s*([A-Za-z .]+)", raw_text, re.IGNORECASE)
    if name_match:
        fields["name"] = name_match.group(1).strip()
    else:
        # Fallback: many real ID cards print the name with no "Name:" label at
        # all. Look for a line that's 2-4 Title Case words and has no digits —
        # a reasonable heuristic for a printed name on a document.
        for line in raw_text.splitlines():
            line = line.strip()
            words = line.split()
            if (2 <= len(words) <= 4 and
                    not any(ch.isdigit() for ch in line) and
                    all(w[:1].isalpha() for w in words) and
                    sum(1 for w in words if w[:1].isupper()) >= len(words) - 1):
                fields["name"] = line
                break

    dob_match = re.search(r"(?:DOB|Date of Birth)\s*[:\-]?\s*([\d/\-]+)", raw_text, re.IGNORECASE)
    if dob_match:
        fields["dob"] = dob_match.group(1).strip()

    # Try common ID number shapes: Aadhaar (12 digits), PAN (5L4D1L), Passport (1L7D)
    id_match = (
        re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", raw_text) or          # Aadhaar-like
        re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", raw_text) or             # PAN-like
        re.search(r"\b[A-PR-WY]\d{7}\b", raw_text)                    # Passport-like
    )
    if id_match:
        fields["id_number"] = re.sub(r"\s", "", id_match.group(0))

    return fields


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def cross_check(form_data: dict, extracted: dict) -> dict:
    """
    form_data: {"name": ..., "dob": ..., "id_number": ...}  (what user typed)
    extracted: output of parse_fields()  (what OCR read from the document)
    """
    result = {"flags": [], "risk_score": 0, "name_similarity": 0.0}

    if extracted.get("name"):
        name_sim = _similarity(form_data.get("name", ""), extracted.get("name", ""))
        result["name_similarity"] = round(name_sim, 2)
        if name_sim < 0.55:
            result["flags"].append(f"Name on form doesn't match document (similarity {name_sim:.0%})")
            result["risk_score"] += 35
        else:
            result["flags"].append(f"Name matches document (similarity {name_sim:.0%})")
    else:
        result["flags"].append("Could not read a name off the document (image quality/angle) — treated as inconclusive, not a mismatch")
        result["risk_score"] += 10

    if extracted.get("dob") and form_data.get("dob"):
        if extracted["dob"].replace("/", "-") != form_data["dob"].replace("/", "-"):
            result["flags"].append("Date of birth mismatch between form and document")
            result["risk_score"] += 30

    if extracted.get("id_number") and form_data.get("id_number"):
        if extracted["id_number"] != form_data["id_number"]:
            result["flags"].append("ID number on document does not match number entered in form")
            result["risk_score"] += 40
    elif not extracted.get("id_number"):
        result["flags"].append("Could not read a valid ID number from the document image")
        result["risk_score"] += 15

    result["risk_score"] = min(result["risk_score"], 100)
    return result


def verify_document_upload(image_path: str, form_data: dict) -> dict:
    raw_text = extract_text_from_image(image_path)
    extracted = parse_fields(raw_text)
    check = cross_check(form_data, extracted)
    return {"raw_ocr_text": raw_text.strip(), "extracted_fields": extracted, **check}


if __name__ == "__main__":
    # Create a simple plain-text test image (NOT a realistic ID template —
    # just enough to prove the OCR pipeline works end-to-end).
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (500, 200), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 20), "Name: Misbah Mubarak Marcha", fill="black")
    d.text((10, 60), "DOB: 12-05-2004", fill="black")
    d.text((10, 100), "Aadhaar: 2341 2341 2346", fill="black")
    img.save("data/sample_test_doc.png")

    form_input = {"name": "Misbah Marcha", "dob": "12-05-2004", "id_number": "234123412346"}
    result = verify_document_upload("data/sample_test_doc.png", form_input)
    import json
    print(json.dumps(result, indent=2))
