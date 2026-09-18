"""
id_verification.py
-------------------
Validates the STRUCTURE of government-issued ID numbers (Aadhaar, PAN,
Passport, Driving License). This checks format + checksum correctness only —
it does NOT connect to any government database (no such public API exists
for student projects). It answers: "Is this a well-formed, non-tampered
ID number?" Combined with OCR cross-check, this is the standard first line
of defense used in real KYC systems before a manual/official verification step.
"""

import re

# ---------------------------------------------------------------------------
# 1. AADHAAR VALIDATION (12-digit number + Verhoeff checksum)
# ---------------------------------------------------------------------------
# The Verhoeff algorithm is a public, well-known checksum algorithm (like the
# Luhn algorithm used for credit cards). Aadhaar numbers are generated with
# this checksum baked in, so we can verify structural validity offline.

_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0]
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]
]
_VERHOEFF_INV = [0,4,3,2,1,5,6,7,8,9]


def _verhoeff_checksum_valid(number_str: str) -> bool:
    """Returns True if the Verhoeff checksum digit (last digit) is valid."""
    c = 0
    digits = [int(d) for d in reversed(number_str)]
    for i, digit in enumerate(digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][digit]]
    return c == 0


def generate_valid_aadhaar() -> str:
    """
    Generates a random 11-digit base + a valid Verhoeff checksum digit.
    For DEMO/TESTING purposes only — lets you test the 'Verified' path
    without having to guess a checksum-valid number by hand. This does
    NOT produce a real, registered Aadhaar number.
    """
    import random
    base = str(random.randint(2, 9)) + "".join(str(random.randint(0, 9)) for _ in range(10))
    c = 0
    for i, digit in enumerate(reversed(base)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(digit)]]
    check_digit = _VERHOEFF_INV[c]
    return base + str(check_digit)


def validate_aadhaar(number: str) -> dict:
    number = re.sub(r"\s|-", "", str(number))
    result = {"id_type": "Aadhaar", "input": number, "valid": False, "reason": ""}

    if not re.fullmatch(r"\d{12}", number):
        result["reason"] = "Must be exactly 12 digits."
        return result
    if number[0] in ("0", "1"):
        result["reason"] = "Aadhaar numbers never start with 0 or 1."
        return result
    if not _verhoeff_checksum_valid(number):
        result["reason"] = "Checksum failed — number is not structurally valid (likely fake/typo)."
        return result

    result["valid"] = True
    result["reason"] = "Format and checksum valid."
    return result


# ---------------------------------------------------------------------------
# 2. PAN VALIDATION  (format: AAAAA9999A)
# ---------------------------------------------------------------------------
def validate_pan(pan: str) -> dict:
    pan = str(pan).strip().upper()
    result = {"id_type": "PAN", "input": pan, "valid": False, "reason": ""}

    pattern = r"[A-Z]{5}[0-9]{4}[A-Z]{1}"
    if not re.fullmatch(pattern, pan):
        result["reason"] = "Must match format AAAAA9999A (5 letters, 4 digits, 1 letter)."
        return result

    # 4th character encodes holder type (P=Individual, C=Company, H=HUF, etc.)
    valid_4th = set("ABCFGHLJPT")
    if pan[3] not in valid_4th:
        result["reason"] = f"4th character '{pan[3]}' is not a recognized PAN holder-type code."
        return result

    result["valid"] = True
    result["reason"] = "Format valid."
    return result


# ---------------------------------------------------------------------------
# 3. PASSPORT VALIDATION (India format: 1 letter + 7 digits)
# ---------------------------------------------------------------------------
def validate_passport(number: str) -> dict:
    number = str(number).strip().upper().replace(" ", "")
    result = {"id_type": "Passport", "input": number, "valid": False, "reason": ""}

    if not re.fullmatch(r"[A-PR-WY][0-9]{7}", number):
        result["reason"] = "Must be 1 letter (not Q,X,Z) followed by 7 digits."
        return result

    result["valid"] = True
    result["reason"] = "Format valid."
    return result


# ---------------------------------------------------------------------------
# 4. DRIVING LICENSE VALIDATION (India generic format: SS RR YYYY NNNNNNN)
# ---------------------------------------------------------------------------
def validate_driving_license(number: str) -> dict:
    number = str(number).strip().upper().replace(" ", "").replace("-", "")
    result = {"id_type": "Driving License", "input": number, "valid": False, "reason": ""}

    # e.g. GJ0520230012345  -> 2 letter state code, 2 digit RTO code, 4 digit year, 7 digit serial
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}(19|20)\d{2}\d{7}", number):
        result["reason"] = "Must match SSRRYYYYNNNNNNN (state code, RTO code, year, serial)."
        return result

    result["valid"] = True
    result["reason"] = "Format valid."
    return result


# ---------------------------------------------------------------------------
DISPATCH = {
    "aadhaar": validate_aadhaar,
    "pan": validate_pan,
    "passport": validate_passport,
    "driving_license": validate_driving_license,
}


def verify_document(doc_type: str, number: str) -> dict:
    doc_type = doc_type.lower().replace(" ", "_")
    if doc_type not in DISPATCH:
        return {"valid": False, "reason": f"Unsupported document type: {doc_type}"}
    return DISPATCH[doc_type](number)


if __name__ == "__main__":
    # Quick self-test with sample numbers (these are NOT real people's IDs —
    # generated purely to satisfy/fail the format+checksum rules for testing)
    tests = [
        ("aadhaar", "234123412346"),   # random 12-digit, likely fails checksum
        ("pan", "ABCPD1234E"),
        ("pan", "12345ABCDE"),         # wrong format
        ("passport", "A1234567"),
        ("driving_license", "GJ0520230012345"),
    ]
    for doc_type, num in tests:
        print(verify_document(doc_type, num))
