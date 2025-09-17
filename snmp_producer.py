import asyncio
import csv
import json
from datetime import datetime
from kafka import KafkaProducer
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity, getCmd
)

# --- CONFIGURATION ---
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "snmp_metrics"
POLL_INTERVAL = 10  # seconds
LOCAL_CSV_LOG = "snmp_polled_data.csv"

# Kafka producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# CSV log header
with open(LOCAL_CSV_LOG, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["hostname", "ip", "port", "community", "collector_hostname", "timestamp", "oid", "value"])

async def poll_snmp(snmp_engine, ip, oids_list, community='public', hostname=None):
    """Poll multiple OIDs for one device."""
    try:
        host, port_str = ip.split(':')
        port = int(port_str)
    except ValueError:
        print(f"⚠ Invalid IP format: {ip}")
        return

    transport = UdpTransportTarget((host, port))
    var_binds_to_get = [ObjectType(ObjectIdentity(oid)) for oid in oids_list]

    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        snmp_engine,
        CommunityData(community, mpModel=1),
        transport,
        ContextData(),
        *var_binds_to_get
    )

    record = {
        "host": hostname or ip,
        "ip": ip,
        "collector_hostname": "local-producer",
        "timestamp": datetime.now().isoformat(),
        "results": {}
    }

    if errorIndication:
        record["results"]["error"] = str(errorIndication)
        print(f"❌ Error polling {ip}: {errorIndication}")
    elif errorStatus:
        error_msg = f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
        record["results"]["error"] = error_msg
        print(f"❌ SNMP Error {ip}: {error_msg}")
    else:
        for varBind in varBinds:
            oid = str(varBind[0])
            value = str(varBind[1])
            record["results"][oid] = value
        print(f"✅ Polled {ip}")

        # Write to CSV
        with open(LOCAL_CSV_LOG, "a", newline="") as f:
            writer = csv.writer(f)
            for oid, value in record["results"].items():
                writer.writerow([record["host"], host, port, community,
                                record["collector_hostname"], record["timestamp"], oid, value])

    # Send to Kafka
    producer.send(KAFKA_TOPIC, record)

async def poll_all_devices():
    snmp_engine = SnmpEngine()
    tasks = []
    with open("inventory.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if ":" not in row["ip"]: continue
            oids_to_poll = [oid for oid in row["oids"].split(";") if oid]
            if not oids_to_poll: continue
            tasks.append(poll_snmp(snmp_engine, row["ip"], oids_to_poll,
                                row.get("community", "public"), row.get("hostname")))
    if tasks:
        await asyncio.gather(*tasks)
    producer.flush()

async def main():
    while True:
        print(f"\n📡 Polling at {datetime.now().isoformat()}")
        await poll_all_devices()
        print(f"⏳ Sleeping {POLL_INTERVAL}s...\n")
        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Shutting down producer.")
        producer.close()
