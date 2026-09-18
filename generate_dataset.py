"""
generate_dataset.py
--------------------
Creates a synthetic dataset of 2000 user profiles for training the fraud
ML model. Each record has profile + account-behavior features drawn from
two overlapping populations (genuine-leaning vs fraud-leaning), then a
composite risk score determines the final 3-class label:
    0 = Verified
    1 = Flagged for Review
    2 = Rejected

Feature overlap is intentional — real fraud data is never perfectly
separable, so we don't want a model that reports a suspicious 100% accuracy.
"""

import numpy as np
import pandas as pd

np.random.seed(42)
N = 2000

# 65% genuine-leaning, 35% fraud-leaning population
is_fraud_leaning = np.random.rand(N) < 0.35

def clip(a, lo, hi):
    return np.clip(a, lo, hi)

# --- Profile features ---
profile_completeness = np.where(
    is_fraud_leaning,
    clip(np.random.normal(35, 20, N), 0, 100),
    clip(np.random.normal(82, 14, N), 0, 100),
)
has_profile_picture = np.where(
    is_fraud_leaning,
    np.random.rand(N) < 0.30,
    np.random.rand(N) < 0.90,
).astype(int)
bio_length = np.where(
    is_fraud_leaning,
    clip(np.random.normal(8, 12, N), 0, None),
    clip(np.random.normal(110, 45, N), 0, None),
)
email_pattern_risk = np.where(
    is_fraud_leaning,
    clip(np.random.normal(62, 20, N), 0, 100),
    clip(np.random.normal(10, 10, N), 0, 100),
)
username_pattern_risk = np.where(
    is_fraud_leaning,
    clip(np.random.normal(55, 22, N), 0, 100),
    clip(np.random.normal(12, 12, N), 0, 100),
)
document_valid = np.where(
    is_fraud_leaning,
    np.random.rand(N) < 0.35,
    np.random.rand(N) < 0.93,
).astype(int)

# --- Account behavior features ---
account_age_days = np.where(
    is_fraud_leaning,
    clip(np.random.exponential(15, N), 0, 90),
    clip(np.random.normal(420, 260, N), 1, None),
)
login_frequency_per_week = np.where(
    is_fraud_leaning,
    clip(np.random.choice([0, 1], N) * np.random.exponential(1, N) +
         (1 - np.random.choice([0, 1], N)) * np.random.normal(20, 8, N), 0, None),
    clip(np.random.normal(5, 2.5, N), 0, None),
)
days_since_last_login = np.where(
    is_fraud_leaning,
    clip(np.random.exponential(25, N), 0, None),
    clip(np.random.exponential(3, N), 0, None),
)
activity_score = np.where(
    is_fraud_leaning,
    clip(np.random.normal(12, 14, N), 0, 100),
    clip(np.random.normal(55, 18, N), 0, 100),
)
duplicate_flag = np.where(
    is_fraud_leaning,
    np.random.rand(N) < 0.40,
    np.random.rand(N) < 0.03,
).astype(int)

df = pd.DataFrame({
    "profile_completeness": profile_completeness.round(1),
    "has_profile_picture": has_profile_picture,
    "bio_length": bio_length.round(0),
    "email_pattern_risk": email_pattern_risk.round(1),
    "username_pattern_risk": username_pattern_risk.round(1),
    "document_valid": document_valid,
    "account_age_days": account_age_days.round(1),
    "login_frequency_per_week": login_frequency_per_week.round(2),
    "days_since_last_login": days_since_last_login.round(1),
    "activity_score": activity_score.round(1),
    "duplicate_flag": duplicate_flag,
})

# --- Composite risk score (0-100) built from the features above ---
risk_score = (
    (100 - df["profile_completeness"]) * 0.15 +
    (1 - df["has_profile_picture"]) * 10 +
    df["email_pattern_risk"] * 0.20 +
    df["username_pattern_risk"] * 0.15 +
    (1 - df["document_valid"]) * 20 +
    (df["account_age_days"] < 30).astype(int) * 12 +
    (df["activity_score"] < 20).astype(int) * 8 +
    df["duplicate_flag"] * 15
)
# add noise so the boundary isn't perfectly crisp
risk_score = risk_score + np.random.normal(0, 6, N)
risk_score = clip(risk_score, 0, 100)

label = pd.cut(risk_score, bins=[-1, 35, 65, 101], labels=[0, 1, 2]).astype(int)
df["risk_score"] = risk_score.round(1)
df["label"] = label  # 0=Verified, 1=Flagged for Review, 2=Rejected

label_names = {0: "Verified", 1: "Flagged for Review", 2: "Rejected"}
df["label_name"] = df["label"].map(label_names)

df.to_csv("data/identity_dataset.csv", index=False)
print(f"Generated {len(df)} records -> data/identity_dataset.csv")
print(df["label_name"].value_counts())
print("\nSample rows:")
print(df.head(5).to_string())
