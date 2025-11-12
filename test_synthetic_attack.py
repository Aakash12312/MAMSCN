# test_synthetic_attacks_hybrid_with_mysql.py
import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector

# --- Load environment variables (optional .env) ---
load_dotenv()

# --- Load model artifacts ---
print("[INFO] Loading models...")
scaler_if = joblib.load("models/scaler.pkl")
model_if = joblib.load("models/isolation_forest_model.pkl")
feature_order = joblib.load("models/feature_order.pkl")

# classification model artifacts
model_cls = joblib.load("models/anomaly_classifier.pkl")
scaler_cls = joblib.load("models/classifier_scaler.pkl")
label_encoder = joblib.load("models/label_encoder.pkl")

print("[INFO] Models loaded successfully ✅")

# --- Base normal sample ---
def base_sample():
    s = {f: 0.0 for f in feature_order}
    if 'ifInOctets11' in s: s['ifInOctets11'] = 1_000_000
    if 'ifOutOctets11' in s: s['ifOutOctets11'] = 900_000
    if 'tcpInSegs' in s: s['tcpInSegs'] = 1000
    if 'udpInDatagrams' in s: s['udpInDatagrams'] = 100
    if 'ipInReceives' in s: s['ipInReceives'] = 1200
    if 'icmpInMsgs' in s: s['icmpInMsgs'] = 5
    return s

# --- Synthetic attack generators ---
def synth_udp_flood(base, intensity=50):
    s = base.copy()
    if 'udpInDatagrams' in s: s['udpInDatagrams'] *= intensity
    if 'ifInOctets11' in s: s['ifInOctets11'] *= intensity
    if 'ipInReceives' in s: s['ipInReceives'] *= intensity
    return s

def synth_tcp_syn_flood(base, intensity=50):
    s = base.copy()
    if 'tcpInSegs' in s: s['tcpInSegs'] *= intensity
    if 'tcpPassiveOpens' in s: s['tcpPassiveOpens'] *= intensity
    if 'tcpRetransSegs' in s: s['tcpRetransSegs'] *= intensity / 5
    return s

def synth_http_flood(base, intensity=30):
    s = base.copy()
    if 'ipOutRequests' in s: s['ipOutRequests'] *= intensity
    if 'ifInUcastPkts11' in s: s['ifInUcastPkts11'] *= intensity
    if 'ifInOctets11' in s: s['ifInOctets11'] *= (intensity // 2)
    return s

# --- Testing helper ---
def test_sample(sample_dict):
    df = pd.DataFrame([sample_dict]).reindex(columns=feature_order, fill_value=0)

    # Scale for Isolation Forest
    X_if = scaler_if.transform(df)
    score = float(model_if.decision_function(X_if)[0])
    pred = int(model_if.predict(X_if)[0])  # 1 = normal, -1 = anomaly
    flag = "Normal" if pred == 1 else "Anomaly"

    anomaly_type = None
    if flag == "Anomaly":
        # Also scale for classifier
        X_cls = scaler_cls.transform(df)
        pred_cls = model_cls.predict(X_cls)
        anomaly_type = label_encoder.inverse_transform(pred_cls)[0]

    # return score as float for JSON/DB friendliness
    return score, flag, anomaly_type

# --- MySQL helper: create connection & ensure table exists ---
def get_db_connection():
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "Aakash10"),
        database=os.getenv("DB_NAME", "mon"),
        autocommit=False
    )
    return db

def ensure_table(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS snmp_metrics_ai (
        id INT AUTO_INCREMENT PRIMARY KEY,
        host VARCHAR(255),
        ip VARCHAR(50),
        collector_hostname VARCHAR(255),
        timestamp VARCHAR(30),
        results JSON,
        anomaly_score FLOAT,
        anomaly_flag VARCHAR(20),
        anomaly_type VARCHAR(50),
        anomaly_timestamp VARCHAR(30)
    )
    """)

def insert_sample_into_db(cursor, rec):
    cursor.execute("""
        INSERT INTO snmp_metrics_ai (
            host, ip, collector_hostname, timestamp, results,
            anomaly_score, anomaly_flag, anomaly_type, anomaly_timestamp
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        rec.get("host"),
        rec.get("ip"),
        rec.get("collector_hostname"),
        rec.get("timestamp"),
        json.dumps(rec.get("results")),  # stored as JSON text
        rec.get("anomaly_score"),
        rec.get("anomaly_flag"),
        rec.get("anomaly_type"),
        rec.get("anomaly_timestamp")
    ))

# --- Main test block ---
if __name__ == "__main__":
    # Connect to DB and ensure table exists
    try:
        db = get_db_connection()
        cursor = db.cursor()
        ensure_table(cursor)
        db.commit()
        print("[DB] Connected and table ensured")
    except Exception as e:
        print(f"[DB] Connection or table creation failed: {e}")
        db = None
        cursor = None

    base = base_sample()

    # function to log to db (if available) for a given sample and prediction results
    def log_sample_to_db(sample_dict, score, flag, anomaly_type, host="synthetic_host", ip="127.0.0.1", collector="synth_collector"):
        rec = {
            "host": host,
            "ip": ip,
            "collector_hostname": collector,
            "timestamp": datetime.now().isoformat(),
            "results": sample_dict,
            "anomaly_score": score,
            "anomaly_flag": flag,
            "anomaly_type": anomaly_type,
            "anomaly_timestamp": datetime.now().isoformat() if flag == "Anomaly" else None
        }
        if cursor:
            try:
                insert_sample_into_db(cursor, rec)
                db.commit()
                print(f"[DB] Inserted record for {rec['ip']} (flag={flag}, type={anomaly_type})")
            except Exception as e:
                db.rollback()
                print(f"[DB] Insert failed: {e}")
        else:
            print("[DB] No DB connection - skipping insert")

    # test base sample
    s_score, s_flag, s_type = test_sample(base)
    print(f"Base: Score={s_score:.4f}, Flag={s_flag}, Type={s_type or 'N/A'}")
    log_sample_to_db(base, s_score, s_flag, s_type)

    # UDP flood
    udp = synth_udp_flood(base, intensity=100)
    score_udp, flag_udp, type_udp = test_sample(udp)
    print(f"UDP: Score={score_udp:.4f}, Flag={flag_udp}, Type={type_udp or 'N/A'}")
    log_sample_to_db(udp, score_udp, flag_udp, type_udp, host="synthetic_udp_host", ip="10.0.0.100")

    # SYN flood
    syn = synth_tcp_syn_flood(base, intensity=80)
    score_syn, flag_syn, type_syn = test_sample(syn)
    print(f"SYN: Score={score_syn:.4f}, Flag={flag_syn}, Type={type_syn or 'N/A'}")
    log_sample_to_db(syn, score_syn, flag_syn, type_syn, host="synthetic_syn_host", ip="10.0.0.101")

    # HTTP flood
    print("\n=== SYNTHETIC HTTP FLOOD ===")
    http = synth_http_flood(base, intensity=60)
    score_http, flag_http, type_http = test_sample(http)
    print(f"HTTP: Score={score_http:.4f}, Flag={flag_http}, Type={type_http or 'N/A'}")
    log_sample_to_db(http, score_http, flag_http, type_http, host="synthetic_http_host", ip="10.0.0.102")

    # Close DB connection cleanly
    if db:
        cursor.close()
        db.close()
        print("[DB] Connection closed")
