# VerifyGrid — Fake Identity Detection Platform

A full-featured fraud/fake-identity detection platform with real user accounts,
government ID validation, OCR document cross-check, online identity analysis,
selfie liveness check, and a machine learning fraud-risk model.

## Features
- Real signup/login system (password hashing via werkzeug)
- Landing page with live stats
- Multi-step identity verification wizard (Email OTP -> Document -> Selfie -> Review) — requires login
- Email OTP verification (demo mode: shown on-screen, no SMTP required)
- Live webcam selfie capture + face-presence check (OpenCV YuNet DNN detector)
- Government ID validation: Aadhaar (Verhoeff checksum), PAN, Passport, Driving License
  - "Fill Sample ID" button generates a checksum-valid test Aadhaar number for demo purposes
- OCR document reading + cross-check against form data (Tesseract) — gracefully
  handles real photographed documents where OCR can't read every field cleanly
- Online identity analysis: disposable email detection, bot-like usernames, duplicate/IP/device matching
- ML fraud-risk model (Random Forest, 92% accuracy) with AI confidence score
- Result page with animated risk meter, QR code, and PDF download (browser print)
- Admin dashboard: charts (Chart.js), search/filter, activity log
- "My History" verification history for logged-in users
- Dark/light theme toggle
- Modern glassmorphism/gradient UI, fully responsive

## Setup

```
pip install flask opencv-python pytesseract pillow scikit-learn pandas numpy joblib werkzeug
```

Install Tesseract OCR (separate from pip):
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Mac: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

If pytesseract can't find Tesseract automatically, add this line near the top of `ocr_extract.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**Selfie face detection (optional but recommended):** download the YuNet model
(233 KB) and save it as `face_detection_yunet.onnx` in the project root:
https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2026may.onnx
Without it, the app still runs fine — the selfie check just reports "skipped."

## Run

```
python database.py           # creates DB + seed data (only needed once)
python generate_dataset.py   # creates training data (only needed once)
python train_model.py        # trains fraud_model.pkl (only needed once)
python app.py                 # starts the app
```

Open **http://localhost:5050**

1. Sign up for an account (name/email/phone/username/password)
2. You're logged in automatically -> click "Verify Identity"
3. Step through: personal info -> email OTP (shown on screen) -> upload ID document
   (use "Fill Sample ID" for a valid test Aadhaar number) -> selfie (optional) -> review -> submit

Admin dashboard: http://localhost:5050/admin/login (password: `admin123`)

## Notes for Your Report / Viva
- ML model: Random Forest, 2000 synthetic records, ~92% test accuracy
- Selfie check is a liveness/face-presence check only (not identity photo matching —
  that would need a heavier face-embedding model; noted as future work)
- Government ID validation checks format/checksum only — no public API exists for
  real-time government database lookups. Real Aadhaar numbers use a Verhoeff
  checksum digit, so the "Fill Sample ID" button exists specifically to let you
  demo the Verified path without hand-crafting a valid number.
- OCR cross-check treats "couldn't read a field from the photo" as inconclusive
  (small risk bump) rather than a hard mismatch (large risk bump) — a blurry or
  unusually formatted real ID photo isn't the same signal as a name that's
  genuinely different from what's on the document.
- OTP is demo-mode (shown on screen) since no SMTP server is configured
- QR codes and charts render client-side via JS (no extra Python dependencies needed)
- Passwords are hashed with werkzeug's `generate_password_hash` (PBKDF2) — never
  stored in plaintext
