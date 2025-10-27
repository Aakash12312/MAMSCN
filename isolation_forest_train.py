# ============================================
# Network Anomaly Detection (Isolation Forest)
# ============================================

import pandas as pd
import numpy as np
import os
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
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
print("[INFO] Columns:", df.columns.tolist())

# -----------------------------
# 2. Identify label column (optional)
# -----------------------------
label_col = None
for col in ["class", "Class", "label", "Label"]:
    if col in df.columns:
        label_col = col
        break

if label_col:
    print(f"[INFO] Detected label column: '{label_col}'")
    print(df[label_col].value_counts())

# -----------------------------
# 3. Select numeric columns only
# -----------------------------
df_num = df.select_dtypes(include=['float64', 'int64'])
print(f"[INFO] Using {df_num.shape[1]} numeric features")

# -----------------------------
# 4. Scale the data
# -----------------------------
scaler = StandardScaler()
X = scaler.fit_transform(df_num)

# -----------------------------
# 5. Train Isolation Forest (always)
# -----------------------------
print("\n[MODE] Unsupervised Isolation Forest")

# Adjust contamination to a safe value if dataset is imbalanced
contamination = 0.05
iso = IsolationForest(contamination=contamination, random_state=42)

print("[INFO] Training Isolation Forest...")
for _ in tqdm(range(1), desc="Fitting Model"):
    iso.fit(X)

print("[INFO] Predicting anomalies...")
y_pred = iso.predict(X)
df['anomaly'] = np.where(y_pred == -1, 1, 0)

# -----------------------------
# 6. Evaluate (optional) if label exists
# -----------------------------
if label_col:
    # Convert labels to 0/1 if needed
    y_true = np.where(df[label_col] == 'normal', 0, 1)
    print("\n[INFO] Evaluation against ground truth:")
    print("Accuracy:", accuracy_score(y_true, df['anomaly']))
    print("\nConfusion Matrix:\n", confusion_matrix(y_true, df['anomaly']))
    print("\nClassification Report:\n", classification_report(y_true, df['anomaly']))

# -----------------------------
# 7. Visualize anomaly results
# -----------------------------
plt.figure(figsize=(6, 4))
df['anomaly'].value_counts().plot(kind='bar', color=['green', 'red'])
plt.title("Anomaly Distribution")
plt.xticks(rotation=0)
plt.xlabel("0 = Normal, 1 = Anomaly")
plt.ylabel("Count")
plt.tight_layout()
plt.show()

# -----------------------------
# 8. Save Isolation Forest model, scaler, and feature order
# -----------------------------
os.makedirs("models", exist_ok=True)

# Model
model_path = "models/isolation_forest_model.pkl"
joblib.dump(iso, model_path)

# Scaler
scaler_path = "models/scaler.pkl"
joblib.dump(scaler, scaler_path)

# Feature order
feature_order_path = "models/feature_order.pkl"
joblib.dump(df_num.columns.tolist(), feature_order_path)

print(f"\n[INFO] Model saved at '{model_path}'")
print(f"[INFO] Scaler saved at '{scaler_path}'")
print(f"[INFO] Feature order saved at '{feature_order_path}'")

print("\n[INFO] Training complete ✅")
