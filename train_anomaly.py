# train_anomaly.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
# Load dataset
df = pd.read_csv("../SNMP 2016 dataset/all_data.csv")
print(f"✅ Dataset loaded: {df.shape}")
# Ensure class column exists
if "class" not in df.columns:
    raise ValueError("❌ Expected 'class' column not found!")
# Features and label
X = df.drop(columns=["class"])
y = df["class"]
print("✅ Using 'class' as label column")
print("Unique classes:", y.unique())

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
# Train Random Forest
print("\n🔹 Training Random Forest...")
rf = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    min_samples_leaf=2,
    max_features="sqrt"
)
rf.fit(X_train, y_train)

# Evaluate
y_pred = rf.predict(X_test)
print("\n📊 Random Forest Results:")
print(classification_report(y_test, y_pred))
print("✅ Accuracy:", accuracy_score(y_test, y_pred))

# Save model
joblib.dump(rf, "random_forest.pkl")
print("💾 Random Forest model saved as random_forest.pkl")
