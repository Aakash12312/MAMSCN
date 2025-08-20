import asyncio
import csv
import json
from datetime import datetime
from kafka import KafkaProducer
from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd
)

# --- CONFIGURATION ---
KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "snmp_metrics"
POLL_INTERVAL = 10  # seconds
LOCAL_CSV_LOG = "snmp_polled_data.csv"  # Define the CSV filename

# --- KAFKA PRODUCER SETUP ---
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# --- [NEW] ENSURE CSV FILE IS CREATED WITH HEADERS AT STARTUP ---
# This is the part you liked from the other script.
# It creates the file and writes the header row once when the script starts.
try:
    with open(LOCAL_CSV_LOG, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["hostname", "ip", "port", "community", "collector_hostname", "timestamp", "oid", "value"])
except IOError as e:
    print(f"❌ Critical Error: Could not create or write to {LOCAL_CSV_LOG}. Please check permissions. Error: {e}")
    exit(1) # Exit if we can't create the log file.
# --- END NEW PART ---


async def poll_snmp(snmp_engine, ip, oids_list, community='public', hostname=None):
    """
    Poll multiple SNMP OIDs from a given device in a single request.
    """
    try:
        host, port_str = ip.split(':')
        port = int(port_str)
    except ValueError:
        print(f"⚠️  Skipping invalid IP address format: {ip}")
        return

    transport = UdpTransportTarget((host, port))
    var_binds_to_get = [ObjectType(ObjectIdentity(oid)) for oid in oids_list]

    errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
        snmp_engine,
        CommunityData(community, mpModel=1), # Using mpModel=1 for SNMPv2c is more standard
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
        print(f"❌ Error polling {hostname} ({ip}): {errorIndication}")
        record["results"]["error"] = str(errorIndication)
    elif errorStatus:
        error_msg = f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
        print(f"❌ SNMP Error on {hostname} ({ip}): {error_msg}")
        record["results"]["error"] = error_msg
    else:
        print(f"✅ Successfully polled {hostname} ({ip})")
        for varBind in varBinds:
            oid = str(varBind[0])
            value = str(varBind[1])
            record["results"][oid] = value

        # --- [NEW] WRITE RESULTS TO THE CSV FILE ---
        # After a successful poll, loop through the results and append each one
        # as a new row in the CSV log file.
        try:
            with open(LOCAL_CSV_LOG, "a", newline="") as f:
                writer = csv.writer(f)
                for oid, value in record["results"].items():
                    writer.writerow([
                        record["host"],
                        host,
                        port,
                        community,
                        record["collector_hostname"],
                        record["timestamp"],
                        oid,
                        value
                    ])
        except IOError as e:
            print(f"🔥 Error writing to CSV log: {e}")
        # --- END NEW PART ---

    # Send the consolidated record to Kafka (this is unchanged)
    producer.send(KAFKA_TOPIC, record)


async def poll_all_devices():
    """Reads inventory, creates polling tasks, and runs them concurrently."""
    snmp_engine = SnmpEngine()

    with open("inventory.csv") as f:
        reader = csv.DictReader(f)
        tasks = []
        for row in reader:
            if not row.get("ip") or ":" not in row["ip"]:
                continue

            oids_to_poll = [oid for oid in row["oids"].split(";") if oid]

            if not oids_to_poll:
                continue

            tasks.append(
                poll_snmp(
                    snmp_engine,
                    row["ip"],
                    oids_to_poll,
                    row.get("community", "public"),
                    row.get("hostname")
                )
            )

    if tasks:
        await asyncio.gather(*tasks)

    producer.flush()


async def main():
    """Run SNMP polling in a loop every POLL_INTERVAL seconds."""
    while True:
        print(f"\n📡 Starting SNMP polling cycle at {datetime.now().isoformat()}")
        await poll_all_devices()
        print(f"⏳ Waiting {POLL_INTERVAL} seconds before next poll...\n")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down producer.")
        producer.close()