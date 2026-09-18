"""
online_identity.py
-------------------
Analyzes online-account signals: email pattern, username pattern, phone
format, and duplicate/IP/device matches against existing registered users.

Disposable-email detection has TWO layers:
  1. A known-domain list (mailinator, tempmail, guerrillamail, etc.)
  2. A pattern-based heuristic that scores domains/usernames NOT in that list
     but that still "look" auto-generated (e.g., low vowel ratio, long
     random alnum strings, digit-heavy local parts) — this catches new
     disposable services the static list hasn't seen yet.
"""

import re
import math
from database import find_by_field

# ---------------------------------------------------------------------------
# Known disposable email domains (layer 1)
# ---------------------------------------------------------------------------
KNOWN_DISPOSABLE_DOMAINS = {
    "tempmail.com", "10minutemail.com", "mailinator.com", "guerrillamail.com",
    "yopmail.com", "throwawaymail.com", "sharklasers.com", "getnada.com",
    "dispostable.com", "trashmail.com", "fakeinbox.com", "maildrop.cc",
}

VOWELS = set("aeiou")


def _vowel_ratio(text: str) -> float:
    letters = [c for c in text.lower() if c.isalpha()]
    if not letters:
        return 0.5
    vowels = sum(1 for c in letters if c in VOWELS)
    return vowels / len(letters)


def _digit_ratio(text: str) -> float:
    if not text:
        return 0
    return sum(c.isdigit() for c in text) / len(text)


def _shannon_entropy(text: str) -> float:
    """Higher entropy = more 'random-looking' string."""
    if not text:
        return 0
    freq = {c: text.count(c) / len(text) for c in set(text)}
    return -sum(p * math.log2(p) for p in freq.values())


# ---------------------------------------------------------------------------
# EMAIL ANALYSIS
# ---------------------------------------------------------------------------
def analyze_email(email: str) -> dict:
    email = email.strip().lower()
    result = {"input": email, "flags": [], "risk_score": 0}

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        result["flags"].append("Invalid email format")
        result["risk_score"] += 40
        return result

    local, domain = email.split("@", 1)

    # Layer 1: known disposable domain
    if domain in KNOWN_DISPOSABLE_DOMAINS:
        result["flags"].append(f"Known disposable email domain ({domain})")
        result["risk_score"] += 50

    # Layer 2: pattern-based heuristic for domain and local part
    domain_name = domain.split(".")[0]
    if len(domain_name) <= 8 and _vowel_ratio(domain_name) < 0.2:
        result["flags"].append("Domain name looks randomly generated (very low vowel ratio)")
        result["risk_score"] += 20

    if len(local) >= 8 and _digit_ratio(local) >= 0.3 and _shannon_entropy(local) > 3.0:
        result["flags"].append("Local part looks auto-generated (high digit ratio + entropy)")
        result["risk_score"] += 25

    if not result["flags"]:
        result["flags"].append("No suspicious patterns detected")

    result["risk_score"] = min(result["risk_score"], 100)
    return result


# ---------------------------------------------------------------------------
# USERNAME ANALYSIS
# ---------------------------------------------------------------------------
def analyze_username(username: str) -> dict:
    username = username.strip()
    result = {"input": username, "flags": [], "risk_score": 0}

    if _digit_ratio(username) >= 0.35:
        result["flags"].append("High proportion of digits in username")
        result["risk_score"] += 20

    if len(username) >= 6 and _vowel_ratio(username) < 0.15:
        result["flags"].append("Username looks like a random character string")
        result["risk_score"] += 25

    if not result["flags"]:
        result["flags"].append("Username looks normal")

    result["risk_score"] = min(result["risk_score"], 100)
    return result


# ---------------------------------------------------------------------------
# PHONE VALIDATION (Indian mobile: 10 digits, starts 6-9)
# ---------------------------------------------------------------------------
def analyze_phone(phone: str) -> dict:
    phone = re.sub(r"\s|-", "", phone)
    result = {"input": phone, "flags": [], "risk_score": 0}

    if not re.fullmatch(r"[6-9]\d{9}", phone):
        result["flags"].append("Not a valid Indian mobile number format")
        result["risk_score"] += 40
    else:
        result["flags"].append("Valid phone format")

    return result


# ---------------------------------------------------------------------------
# DUPLICATE / IP / DEVICE CHECK
# ---------------------------------------------------------------------------
def check_duplicates(email: str, phone: str, ip_address: str, device_id: str) -> dict:
    result = {"flags": [], "risk_score": 0, "matches": {}}

    for field, value in [("email", email), ("phone", phone),
                          ("ip_address", ip_address), ("device_id", device_id)]:
        matches = find_by_field(field, value)
        if matches:
            result["matches"][field] = matches
            weight = 30 if field in ("email", "phone") else 20
            result["flags"].append(f"Existing account(s) already use this {field.replace('_', ' ')}")
            result["risk_score"] += weight

    if not result["flags"]:
        result["flags"].append("No duplicate email/phone/IP/device found")

    result["risk_score"] = min(result["risk_score"], 100)
    return result


# ---------------------------------------------------------------------------
def analyze_online_identity(name, email, phone, username, ip_address, device_id) -> dict:
    email_r = analyze_email(email)
    user_r = analyze_username(username)
    phone_r = analyze_phone(phone)
    dup_r = check_duplicates(email, phone, ip_address, device_id)

    total_score = round(
        email_r["risk_score"] * 0.3 +
        user_r["risk_score"] * 0.15 +
        phone_r["risk_score"] * 0.15 +
        dup_r["risk_score"] * 0.4, 1
    )

    return {
        "email_analysis": email_r,
        "username_analysis": user_r,
        "phone_analysis": phone_r,
        "duplicate_analysis": dup_r,
        "online_identity_risk_score": total_score,
    }


if __name__ == "__main__":
    import json
    from database import init_db
    init_db()  # ensure DB + seed data exist (won't reset if already there)

    # Try a fraud-pattern registration that reuses a seeded fraud IP/device
    test = analyze_online_identity(
        name="New Person",
        email="newperson.k382@tempmail.com",
        phone="9000000009",
        username="xk29fh3kd2",
        ip_address="45.33.12.200",   # reused from seed fraud ring
        device_id="DEV-X9Z1",        # reused from seed fraud ring
    )
    print(json.dumps(test, indent=2))
