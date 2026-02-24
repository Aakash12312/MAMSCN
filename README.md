Model Failure: Isolation Forest failed on balanced data.→ Re-processed data to make anomalies rare → detection accuracy improved.
Scalability Bottleneck: Single poller couldn’t scale.→ Adopted multi-agent model; Producers now run in parallel.

Possible Enhancements: 
AI Alert Prioritization: Use a second model (Transformer) to rank alerts.
Analyst Feedback Loop: Allow marking false positives in Grafana → retrain models automatically.
Automated Remediation: Extend alerting.py to trigger fixes (e.g., firewall rule updates).

