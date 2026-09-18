"""
selfie_check.py
----------------
Confirms a human face is present in the captured selfie image.

Uses OpenCV's DNN-based YuNet face detector (cv2.FaceDetectorYN), the
officially recommended replacement in OpenCV 5.x now that the old
Haar Cascade classifier (cv2.CascadeClassifier) moved out of the base
package. This is a "liveness/presence" check, not full facial-recognition
matching against the ID photo — that would need a much heavier
face-embedding model and is flagged as future work.

Requires the model file 'face_detection_yunet.onnx' in the project root.
Download it from:
https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2026may.onnx
"""

import os
import cv2

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_detection_yunet.onnx")
_detector = None
_model_available = os.path.isfile(_MODEL_PATH)

if _model_available:
    _detector = cv2.FaceDetectorYN.create(_MODEL_PATH, "", (320, 320), score_threshold=0.8)


def check_selfie(image_path: str) -> dict:
    if not _model_available:
        return {
            "face_detected": False, "face_count": 0,
            "reason": "Face detection model not found (face_detection_yunet.onnx missing) — selfie check skipped.",
        }

    img = cv2.imread(image_path)
    if img is None:
        return {"face_detected": False, "face_count": 0, "reason": "Could not read selfie image."}

    h, w = img.shape[:2]
    _detector.setInputSize((w, h))
    _, faces = _detector.detect(img)

    face_count = 0 if faces is None else len(faces)
    if face_count == 0:
        return {"face_detected": False, "face_count": 0, "reason": "No face detected in selfie."}
    if face_count > 1:
        return {"face_detected": True, "face_count": face_count,
                "reason": f"{face_count} faces detected — expected exactly one."}

    return {"face_detected": True, "face_count": 1, "reason": "Exactly one face detected."}
