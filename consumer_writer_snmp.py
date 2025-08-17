# consumer_writer_snmp.py
from kafka import KafkaConsumer
import json
import mysql.connector

# Kafka Config
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "snmp_metrics"

# MySQL Config
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Root@1234",
    database="monitoring"
)
cursor = db.cursor()

# Ensure table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS snmp_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    host VARCHAR(255),
    ip VARCHAR(50),
    collector_hostname VARCHAR(255),
    timestamp VARCHAR(30),
    results JSON
)
""")
db.commit()

# Create Kafka consumer
consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("📡 Waiting for SNMP messages from Kafka...")

# Consume and write to MySQL
for msg in consumer:
    rec = msg.value
    results = rec.get("results", {})

    # Skip messages with error
    if "error" in results:
        print(f"⚠️  Skipping {rec.get('ip')} due to error: {results['error']}")
        continue

    try:
        cursor.execute("""
            INSERT INTO snmp_metrics (host, ip, collector_hostname, timestamp, results)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            rec.get('host'),
            rec.get('ip'),
            rec.get('collector_hostname'),
            rec.get('timestamp'),
            json.dumps(results)  # store only valid OIDs
        ))
        db.commit()
        print(f"✅ Inserted SNMP record for {rec.get('ip')} at {rec.get('timestamp')}")
    except Exception as e:
        print(f"❌ DB write error for {rec.get('ip')}: {e}")
