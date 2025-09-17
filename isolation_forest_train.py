# ==============================
# Network Anomaly Detection (with verbose progress)
# ==============================

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from tqdm import tqdm

# 1. Load dataset
print("[INFO] Loading dataset...")
base_path = "./datasets/all_data (3).csv"
file_name = "all_data (3).csv"  # exact file name
df = pd.read_csv(os.path.join(base_path, file_name))

print("[INFO] Dataset shape:", df.shape)
print("[INFO] Columns:", df.columns.tolist())
print("[INFO] Preview:\n", df.head())

# 2. Select numeric features
print("\n[INFO] Selecting numeric features...")
df_num = df.select_dtypes(include=['float64', 'int64'])
print("[INFO] Using", df_num.shape[1], "numeric features")

# 3. Scale features
print("\n[INFO] Scaling features...")
scaler = StandardScaler()
X = scaler.fit_transform(df_num)

# 4. Train Isolation Forest with tqdm
print("\n[INFO] Training Isolation Forest...")
iso = IsolationForest(contamination=0.05, random_state=42, verbose=0)

# Wrap fit with tqdm progress
for _ in tqdm(range(1), desc="Fitting Model"):
    iso.fit(X)

# 5. Predict anomalies with progress bar
print("\n[INFO] Predicting anomalies...")
y_pred = []
for i in tqdm(range(0, len(X), 10000), desc="Predicting in batches"):
    batch_pred = iso.predict(X[i:i+10000])
    y_pred.extend(batch_pred)

df['anomaly'] = y_pred

# 6. Print results
print("\n[INFO] Anomaly counts:\n", df['anomaly'].value_counts())
print("\n[INFO] Sample results:\n", df[['anomaly']].head())

# 7. Visualize anomaly distribution
plt.figure(figsize=(6,4))
df['anomaly'].value_counts().plot(kind='bar', color=['green','red'])
plt.xticks([0,1], ['Normal','Anomaly'], rotation=0)
plt.title("Anomaly Detection Results")
plt.show()

# 8. Optional: Evaluate if dataset has labels
if 'Label' in df.columns or 'label' in df.columns:
    from sklearn.metrics import classification_report, confusion_matrix
    
    label_col = 'Label' if 'Label' in df.columns else 'label'
    print("\n[INFO] Confusion Matrix:\n", confusion_matrix(df[label_col], df['anomaly']))
    print("\n[INFO] Classification Report:\n", classification_report(df[label_col], df['anomaly']))
