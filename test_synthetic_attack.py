# test_synthetic_attacks.py
import joblib
import numpy as np
import pandas as pd

# load model artifacts
scaler = joblib.load("models/scaler.pkl")
model = joblib.load("models/isolation_forest_model.pkl")
feature_order = joblib.load("models/feature_order.pkl")
header = "ifInOctets11,ifOutOctets11,ifoutDiscards11,ifInUcastPkts11,ifInNUcastPkts11,ifInDiscards11,ifOutUcastPkts11,ifOutNUcastPkts11,tcpOutRsts,tcpInSegs,tcpOutSegs,tcpPassiveOpens,tcpRetransSegs,tcpCurrEstab,tcpEstabResets,tcp?ActiveOpens,udpInDatagrams,udpOutDatagrams,udpInErrors,udpNoPorts,ipInReceives,ipInDelivers,ipOutRequests,ipOutDiscards,ipInDiscards,ipForwDatagrams,ipOutNoRoutes,ipInAddrErrors,icmpInMsgs,icmpInDestUnreachs,icmpOutMsgs,icmpOutDestUnreachs,icmpInEchos,icmpOutEchoReps,class"
values = "1867925250,902237363,0,52007310,16978,0,7197292,3968,1,682,537,49,14,0,5,3,241016,187093,1,22,59300887,244972,187698,569,23,59244345,7,0,49,26,46,23,23,23,normal"

# 3) Build DataFrame for features (exclude 'class' column for model input)
cols = header.split(",")
vals = values.split(",")
assert len(cols) == len(vals), "header/values length mismatch"

# Put into dict, convert numeric columns to float
row = dict(zip(cols, vals))
# Remove class label before prediction
if 'class' in row:
    true_label = row.pop('class')
else:
    true_label = None

# Convert to numeric where possible
for k in list(row.keys()):
    try:
        row[k] = float(row[k])
    except:
        # leave as-is if cannot convert
        pass

df_row = pd.DataFrame([row])

# 4) Align to training feature order and fill missing
X = df_row.reindex(columns=feature_order, fill_value=0)

# 5) Scale with saved scaler
Xs = scaler.transform(X)

# 6) Score & predict
score = float(model.decision_function(Xs)[0])   # higher -> more normal
pred_raw = int(model.predict(Xs)[0])            # 1 = normal, -1 = anomaly
flag = "Normal" if pred_raw == 1 else "Anomaly"

# 7) Print results (including original label if present)
print("=== Single-row prediction ===")
if true_label is not None:
    print("Ground-truth label (from CSV):", true_label)
print(f"Anomaly score (decision_function): {score:.6f}   (higher = more normal)")
print(f"Discrete prediction: {pred_raw}  -> {flag}")
print("\nFeature snippet (first 10 features used):")
print(X.iloc[0][:10])
# helper: base normal sample (you can also take a real row from your training CSV)
def base_sample():
    # create a zero-based sample and fill in with small baseline values
    s = {f: 0.0 for f in feature_order}
    # set some realistic baseline values (tweak as needed)
    if 'ifInOctets11' in s: s['ifInOctets11'] = 1_000_000
    if 'ifOutOctets11' in s: s['ifOutOctets11'] = 900_000
    if 'tcpInSegs' in s: s['tcpInSegs'] = 1000
    if 'udpInDatagrams' in s: s['udpInDatagrams'] = 100
    if 'ipInReceives' in s: s['ipInReceives'] = 1200
    if 'icmpInMsgs' in s: s['icmpInMsgs'] = 5
    return s

# create synthetic attack types
def synth_udp_flood(base, intensity=50):
    s = base.copy()
    # spike UDP datagrams and octets drastically
    if 'udpInDatagrams' in s: s['udpInDatagrams'] *= intensity
    if 'ifInOctets11' in s: s['ifInOctets11'] *= intensity
    if 'ipInReceives' in s: s['ipInReceives'] *= intensity
    return s

def synth_tcp_syn_flood(base, intensity=50):
    s = base.copy()
    # spike TCP segments and passive opens or retrans
    if 'tcpInSegs' in s: s['tcpInSegs'] *= intensity
    if 'tcpPassiveOpens' in s: s['tcpPassiveOpens'] *= intensity
    if 'tcpRetransSegs' in s: s['tcpRetransSegs'] *= intensity / 5
    return s

def synth_http_flood(base, intensity=30):
    s = base.copy()
    # more in/out requests, small packet sizes -> high packet/byte ratio could be used later
    if 'ipOutRequests' in s: s['ipOutRequests'] *= intensity
    if 'ifInUcastPkts11' in s: s['ifInUcastPkts11'] *= intensity
    if 'ifInOctets11' in s: s['ifInOctets11'] *= (intensity // 2)
    return s

# test function: scale, score, predict
def test_sample(sample_dict):
    df = pd.DataFrame([sample_dict])
    # align columns
    df = df.reindex(columns=feature_order, fill_value=0)
    Xs = scaler.transform(df)
    score = model.decision_function(Xs)[0]   # higher -> more normal
    pred = model.predict(Xs)[0]              # 1=normal, -1=anomaly
    return score, pred

if __name__ == "__main__":
    base = base_sample()

    # normal baseline
    s_score, s_pred = test_sample(base)
    print(f"BASELINE → score={s_score:.4f}, flag={'Normal' if s_pred==1 else 'Anomaly'}")

    # synthetic UDP flood
    udp = synth_udp_flood(base, intensity=100)
    score_udp, pred_udp = test_sample(udp)
    print(f"SIM UDP FLOOD → score={score_udp:.4f}, flag={'Normal' if pred_udp==1 else 'Anomaly'}")

    # synthetic TCP SYN flood
    syn = synth_tcp_syn_flood(base, intensity=80)
    score_syn, pred_syn = test_sample(syn)
    print(f"SIM TCP-SYN FLOOD → score={score_syn:.4f}, flag={'Normal' if pred_syn==1 else 'Anomaly'}")

    # synthetic HTTP flood
    http = synth_http_flood(base, intensity=60)
    score_http, pred_http = test_sample(http)
    print(f"SIM HTTP FLOOD → score={score_http:.4f}, flag={'Normal' if pred_http==1 else 'Anomaly'}")
