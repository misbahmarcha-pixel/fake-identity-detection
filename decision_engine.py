"""
decision_engine.py
-------------------
Combines all four detection modules into one final decision:
  - Government ID format validation      (weight 30%)
  - OCR document cross-check              (weight 20%)
  - Online identity analysis (email/username/duplicates/IP/device) (weight 20%)
  - ML behavioral fraud model             (weight 30%)

Weights favor the ML model + document validity, per project scope.
Final categories: Verified (<35) / Flagged for Review (35-65) / Rejected (>65)
"""

import joblib
import pandas as pd

from id_verification import verify_document
from online_identity import analyze_online_identity
from ocr_extract import verify_document_upload
from selfie_check import check_selfie

_bundle = joblib.load("fraud_model.pkl")
_MODEL = _bundle["model"]
_FEATURES = _bundle["features"]

WEIGHTS = {
    "id_format": 0.25,
    "ocr_crosscheck": 0.15,
    "online_identity": 0.20,
    "ml_model": 0.30,
    "selfie_liveness": 0.10,
}


def _ml_risk_score(profile_completeness, has_profile_picture, bio_length,
                    email_pattern_risk, username_pattern_risk, document_valid,
                    duplicate_flag) -> float:
    """
    New registrations have no account history yet, so behavior features
    (account_age_days, login_frequency, days_since_last_login, activity_score)
    start at their "brand new account" values. This is realistic: a fresh
    account naturally carries more model-driven scrutiny than an established one.
    """
    row = pd.DataFrame([{
        "profile_completeness": profile_completeness,
        "has_profile_picture": int(has_profile_picture),
        "bio_length": bio_length,
        "email_pattern_risk": email_pattern_risk,
        "username_pattern_risk": username_pattern_risk,
        "document_valid": int(document_valid),
        "account_age_days": 0,
        "login_frequency_per_week": 0,
        "days_since_last_login": 0,
        "activity_score": 0,
        "duplicate_flag": int(duplicate_flag),
    }])[_FEATURES]

    proba = _MODEL.predict_proba(row)[0]  # [P(Verified), P(Flagged), P(Rejected)]
    # convert class probabilities into a single 0-100 risk score
    risk = proba[1] * 50 + proba[2] * 100
    return round(float(risk), 1), proba.tolist()


def evaluate_registration(form_data: dict, doc_image_path: str, selfie_image_path: str = None) -> dict:
    """
    form_data keys: name, email, phone, username, bio, has_profile_picture,
                    doc_type, id_number, dob, ip_address, device_id
    """
    reasons = []

    # 1. Government ID format validation
    id_result = verify_document(form_data["doc_type"], form_data["id_number"])
    id_format_score = 0 if id_result["valid"] else 100
    reasons.append(f"[ID Format] {id_result['reason']}")

    # 2. OCR document cross-check
    ocr_result = verify_document_upload(doc_image_path, {
        "name": form_data["name"], "dob": form_data.get("dob", ""),
        "id_number": form_data["id_number"],
    })
    reasons.extend(f"[OCR] {f}" for f in ocr_result["flags"])

    # 3. Online identity analysis
    online_result = analyze_online_identity(
        name=form_data["name"], email=form_data["email"], phone=form_data["phone"],
        username=form_data["username"], ip_address=form_data["ip_address"],
        device_id=form_data["device_id"],
    )
    for module in ["email_analysis", "username_analysis", "phone_analysis", "duplicate_analysis"]:
        reasons.extend(f"[{module.replace('_', ' ').title()}] {f}" for f in online_result[module]["flags"])

    duplicate_flag = 1 if online_result["duplicate_analysis"]["risk_score"] > 0 else 0

    # 4. ML behavioral model
    bio_length = len(form_data.get("bio", "") or "")
    profile_completeness = sum([
        bool(form_data.get("bio")), bool(form_data.get("has_profile_picture")),
        bool(form_data.get("email")), bool(form_data.get("phone")),
    ]) / 4 * 100
    ml_score, proba = _ml_risk_score(
        profile_completeness=profile_completeness,
        has_profile_picture=form_data.get("has_profile_picture", False),
        bio_length=bio_length,
        email_pattern_risk=online_result["email_analysis"]["risk_score"],
        username_pattern_risk=online_result["username_analysis"]["risk_score"],
        document_valid=id_result["valid"],
        duplicate_flag=duplicate_flag,
    )
    reasons.append(f"[ML Model] Predicted class probabilities — Verified: {proba[0]:.0%}, "
                    f"Flagged: {proba[1]:.0%}, Rejected: {proba[2]:.0%}")

    # 5. Selfie liveness/presence check (face detection only, not identity matching)
    if selfie_image_path:
        selfie_result = check_selfie(selfie_image_path)
        selfie_score = 0 if (selfie_result["face_detected"] and selfie_result["face_count"] == 1) else 70
        reasons.append(f"[Selfie Check] {selfie_result['reason']}")
    else:
        selfie_result = {"face_detected": False, "face_count": 0, "reason": "No selfie provided."}
        selfie_score = 40
        reasons.append("[Selfie Check] No selfie provided — treated as moderate risk.")

    # Combine
    final_score = (
        id_format_score * WEIGHTS["id_format"] +
        ocr_result["risk_score"] * WEIGHTS["ocr_crosscheck"] +
        online_result["online_identity_risk_score"] * WEIGHTS["online_identity"] +
        ml_score * WEIGHTS["ml_model"] +
        selfie_score * WEIGHTS["selfie_liveness"]
    )
    final_score = round(final_score, 1)

    if final_score < 35:
        decision = "Verified"
    elif final_score <= 65:
        decision = "Flagged for Review"
    else:
        decision = "Rejected"

    # AI confidence: how confident the ML model is in the predicted class
    class_idx = {"Verified": 0, "Flagged for Review": 1, "Rejected": 2}[decision]
    ai_confidence = round(proba[class_idx] * 100, 1)
    reasons.append(f"[AI Confidence] {ai_confidence}% confidence in '{decision}' classification")

    return {
        "decision": decision,
        "final_risk_score": final_score,
        "ai_confidence": ai_confidence,
        "module_scores": {
            "id_format_score": id_format_score,
            "ocr_crosscheck_score": ocr_result["risk_score"],
            "online_identity_score": online_result["online_identity_risk_score"],
            "ml_model_score": ml_score,
            "selfie_score": selfie_score,
        },
        "reasons": reasons,
        "selfie_result": selfie_result,
        "raw": {"id_result": id_result, "ocr_result": ocr_result, "online_result": online_result},
    }
