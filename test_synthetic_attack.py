# ============================================
# test_synthetic_attacks_hybrid.py
# ============================================
import joblib
import numpy as np
import pandas as pd

# --- Load model artifacts ---
print("[INFO] Loading models...")
scaler_if = joblib.load("models/scaler.pkl")
model_if = joblib.load("models/isolation_forest_model.pkl")
feature_order = joblib.load("models/feature_order.pkl")

# 🧠 NEW: Load classification model artifacts
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
    score = model_if.decision_function(X_if)[0]
    pred = model_if.predict(X_if)[0]  # 1 = normal, -1 = anomaly
    flag = "Normal" if pred == 1 else "Anomaly"

    anomaly_type = None
    if flag == "Anomaly":
        # 🧠 Also scale for classifier
        X_cls = scaler_cls.transform(df)
        pred_cls = model_cls.predict(X_cls)
        anomaly_type = label_encoder.inverse_transform(pred_cls)[0]

    return score, flag, anomaly_type

# --- Main test block ---
if __name__ == "__main__":
    base = base_sample()
    
    s_score, s_flag, s_type = test_sample(base)
    print(f"Score={s_score:.4f}, Flag={s_flag}, Type={s_type or 'N/A'}")

    udp = synth_udp_flood(base, intensity=100)
    score_udp, flag_udp, type_udp = test_sample(udp)
    print(f"Score={score_udp:.4f}, Flag={flag_udp}, Type={type_udp or 'N/A'}")

    syn = synth_tcp_syn_flood(base, intensity=80)
    score_syn, flag_syn, type_syn = test_sample(syn)
    print(f"Score={score_syn:.4f}, Flag={flag_syn}, Type={type_syn or 'N/A'}")

    print("\n=== SYNTHETIC HTTP FLOOD ===")
    http = synth_http_flood(base, intensity=60)
    score_http, flag_http, type_http = test_sample(http)
    print(f"Score={score_http:.4f}, Flag={flag_http}, Type={type_http or 'N/A'}")
