# consumer_ai_snmp.py (Isolation Forest with anomaly scores)
import os
import json
import csv
from kafka import KafkaConsumer
from dotenv import load_dotenv
import mysql.connector
import joblib
import pandas as pd

load_dotenv()

# --- CONFIG ---
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "snmp_metrics"
OUTPUT_CSV = "snmp_consumed_ai.csv"

# Threshold for marking anomaly
ANOMALY_THRESHOLD = -0.1  # adjust based on your dataset

# --- OID to feature mapping ---
OID_TO_FEATURE = {
    # Interfaces (ifTable index 11)
    "1.3.6.1.2.1.2.2.1.10.11": "ifInOctets11",
    "1.3.6.1.2.1.2.2.1.16.11": "ifOutOctets11",
    "1.3.6.1.2.1.2.2.1.19.11": "ifOutDiscards11",
    "1.3.6.1.2.1.2.2.1.11.11": "ifInUcastPkts11",
    "1.3.6.1.2.1.2.2.1.12.11": "ifInNUcastPkts11",
    "1.3.6.1.2.1.2.2.1.13.11": "ifInDiscards11",
    "1.3.6.1.2.1.2.2.1.17.11": "ifOutUcastPkts11",
    "1.3.6.1.2.1.2.2.1.18.11": "ifOutNUcastPkts11",
    # TCP
    "1.3.6.1.2.1.6.15.0": "tcpOutRsts",
    "1.3.6.1.2.1.6.10.0": "tcpInSegs",
    "1.3.6.1.2.1.6.11.0": "tcpOutSegs",
    "1.3.6.1.2.1.6.6.0": "tcpPassiveOpens",
    "1.3.6.1.2.1.6.12.0": "tcpRetransSegs",
    "1.3.6.1.2.1.6.9.0": "tcpCurrEstab",
    "1.3.6.1.2.1.6.8.0": "tcpEstabResets",
    "1.3.6.1.2.1.6.5.0": "tcpActiveOpens",
    # UDP
    "1.3.6.1.2.1.7.1.0": "udpInDatagrams",
    "1.3.6.1.2.1.7.4.0": "udpOutDatagrams",
    "1.3.6.1.2.1.7.3.0": "udpInErrors",
    "1.3.6.1.2.1.7.2.0": "udpNoPorts",
    # IP
    "1.3.6.1.2.1.4.3.0": "ipInReceives",
    "1.3.6.1.2.1.4.9.0": "ipInDelivers",
    "1.3.6.1.2.1.4.10.0": "ipOutRequests",
    "1.3.6.1.2.1.4.11.0": "ipOutDiscards",
    "1.3.6.1.2.1.4.8.0": "ipInDiscards",
    "1.3.6.1.2.1.4.6.0": "ipForwDatagrams",
    "1.3.6.1.2.1.4.12.0": "ipOutNoRoutes",
    "1.3.6.1.2.1.4.5.0": "ipInAddrErrors",
    # ICMP
    "1.3.6.1.2.1.5.1.0": "icmpInMsgs",
    "1.3.6.1.2.1.5.3.0": "icmpInDestUnreachs",
    "1.3.6.1.2.1.5.14.0": "icmpOutMsgs",
    "1.3.6.1.2.1.5.23.0": "icmpOutDestUnreachs",
    "1.3.6.1.2.1.5.8.0": "icmpInEchos",
    "1.3.6.1.2.1.5.21.0": "icmpOutEchoReps"
}

# --- Load model, scaler, and feature order ---
print("💾 Loading Isolation Forest model...")
model = joblib.load("./models/isolation_forest_model.pkl")
scaler = joblib.load("./models/scaler.pkl")
feature_order = joblib.load("./models/feature_order.pkl")
print("✅ Model, scaler, and feature order loaded")

# --- Setup MySQL ---
db = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", "Aakash10"),
    database=os.getenv("DB_NAME", "mon")
)
cursor = db.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS snmp_metrics_ai (
    id INT AUTO_INCREMENT PRIMARY KEY,
    host VARCHAR(255),
    ip VARCHAR(50),
    collector_hostname VARCHAR(255),
    timestamp VARCHAR(30),
    results JSON,
    anomaly_score FLOAT,
    anomaly_flag VARCHAR(20)
)
""")
db.commit()

# --- Setup CSV ---
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "host", "ip", "collector_hostname", "timestamp",
        "feature", "value", "anomaly_score", "anomaly_flag"
    ])

# --- Kafka Consumer ---
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    auto_offset_reset="latest",
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode("utf-8"))
)

print("📡 Waiting for SNMP messages...")

for msg in consumer:
    rec = msg.value
    results = rec.get("results", {})
    if "error" in results:
        print(f"⚠ Skipping {rec.get('ip')} due to error {results['error']}")
        continue

    try:
        # Map OIDs → feature names
        mapped_results = {OID_TO_FEATURE.get(k, k): float(v) for k, v in results.items()}

        # Align features
        feature_vector = pd.DataFrame([mapped_results])
        feature_vector = feature_vector.reindex(columns=feature_order, fill_value=0)

        # Scale
        feature_vector_scaled = scaler.transform(feature_vector)

        # Get anomaly score (higher = more normal)
        score = model.decision_function(feature_vector_scaled)[0]
        anomaly_flag = "Normal" if score >= ANOMALY_THRESHOLD else "Anomaly"

        # Insert into MySQL
        cursor.execute("""
            INSERT INTO snmp_metrics_ai (host, ip, collector_hostname, timestamp, results, anomaly_score, anomaly_flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            rec.get("host"),
            rec.get("ip"),
            rec.get("collector_hostname"),
            rec.get("timestamp"),
            json.dumps(mapped_results),
            score,
            anomaly_flag
        ))
        db.commit()

        # Append to CSV
        with open(OUTPUT_CSV, "a", newline="") as f:
            writer = csv.writer(f)
            for feature, value in mapped_results.items():
                writer.writerow([
                    rec.get("host"),
                    rec.get("ip"),
                    rec.get("collector_hostname"),
                    rec.get("timestamp"),
                    feature,
                    value,
                    score,
                    anomaly_flag
                ])

        print(f"✅ {rec.get('ip')} @ {rec.get('timestamp')} → {anomaly_flag} (score={score:.3f})")

    except Exception as e:
        print(f"❌ Processing error: {e}")
