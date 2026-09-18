"""
train_model.py
---------------
Trains a Random Forest classifier to predict identity risk category
(Verified / Flagged for Review / Rejected) from profile + behavior features.
Saves the trained model + feature list for use in the Flask app.
"""

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix
)

FEATURES = [
    "profile_completeness", "has_profile_picture", "bio_length",
    "email_pattern_risk", "username_pattern_risk", "document_valid",
    "account_age_days", "login_frequency_per_week", "days_since_last_login",
    "activity_score", "duplicate_flag",
]
LABEL_NAMES = {0: "Verified", 1: "Flagged for Review", 2: "Rejected"}

df = pd.read_csv("data/identity_dataset.csv")
X = df[FEATURES]
y = df["label"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=200, max_depth=10, random_state=42, class_weight="balanced"
)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)

acc = accuracy_score(y_test, y_pred)
print(f"Test Accuracy: {acc:.4f}\n")
print("Classification Report:")
print(classification_report(y_test, y_pred, target_names=list(LABEL_NAMES.values())))

print("Confusion Matrix (rows=actual, cols=predicted):")
cm = confusion_matrix(y_test, y_pred)
print(pd.DataFrame(cm, index=list(LABEL_NAMES.values()), columns=list(LABEL_NAMES.values())))

print("\nFeature Importances:")
importances = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
print(importances.to_string())

joblib.dump({"model": model, "features": FEATURES, "label_names": LABEL_NAMES}, "fraud_model.pkl")
print("\nModel saved -> fraud_model.pkl")
