# ============================================
# Network Anomaly Classification (Supervised)
# ============================================

import pandas as pd
import numpy as np
import os
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib

# -----------------------------
# 1. Load Dataset
# -----------------------------
print("[INFO] Loading dataset...")
base_path = "./datasets"
file_name = "all_data (3).csv"
df = pd.read_csv(os.path.join(base_path, file_name))

print("[INFO] Dataset loaded:", df.shape)

# -----------------------------
# 2. Identify label column
# -----------------------------
label_col = None
for col in ["class", "Class", "label", "Label"]:
    if col in df.columns:
        label_col = col
        break

if not label_col:
    raise ValueError("No label column found. Please ensure the dataset has a 'class' or 'label' column.")

print(f"[INFO] Detected label column: '{label_col}'")
print(df[label_col].value_counts())

# -----------------------------
# 3. Prepare features (numeric only)
# -----------------------------
df_num = df.select_dtypes(include=['float64', 'int64'])
print(f"[INFO] Using {df_num.shape[1]} numeric features")

# -----------------------------
# 4. Encode labels
# -----------------------------
le = LabelEncoder()
y = le.fit_transform(df[label_col])

# -----------------------------
# 5. Split train/test data
# -----------------------------
X_train, X_test, y_train, y_test = train_test_split(
    df_num, y, test_size=0.2, random_state=42, stratify=y
)

# -----------------------------
# 6. Scale data
# -----------------------------
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# -----------------------------
# 7. Train classification model
# -----------------------------
print("[INFO] Training Random Forest Classifier...")
clf = RandomForestClassifier(
    n_estimators=150,
    random_state=42,
    n_jobs=-1,
    class_weight="balanced"
)

clf.fit(X_train_scaled, y_train)

# -----------------------------
# 8. Evaluate model
# -----------------------------
print("[INFO] Evaluating model...")
y_pred = clf.predict(X_test_scaled)

print("\nAccuracy:", accuracy_score(y_test, y_pred))
print("\nConfusion Matrix:\n", confusion_matrix(y_test, y_pred))
print("\nClassification Report:\n", classification_report(y_test, y_pred, target_names=le.classes_))

# -----------------------------
# 9. Visualize class distribution
# -----------------------------
plt.figure(figsize=(8, 4))
pd.Series(y_pred).value_counts().plot(kind='bar', color='skyblue')
plt.title("Predicted Class Distribution")
plt.xlabel("Class Label (encoded)")
plt.ylabel("Count")
plt.tight_layout()
plt.show()

# -----------------------------
# 10. Save model, scaler, and label encoder
# -----------------------------
os.makedirs("models", exist_ok=True)

joblib.dump(clf, "models/anomaly_classifier.pkl")
joblib.dump(scaler, "models/classifier_scaler.pkl")
joblib.dump(le, "models/label_encoder.pkl")

print("\n[INFO] Model saved at 'models/anomaly_classifier.pkl'")
print("[INFO] Scaler saved at 'models/classifier_scaler.pkl'")
print("[INFO] Label encoder saved at 'models/label_encoder.pkl'")
print("\n[INFO] Training complete ✅")
