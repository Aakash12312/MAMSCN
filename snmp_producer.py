# snmp_producer.py (Updated and Optimized)

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
    get_cmd
)

KAFKA_BOOTSTRAP = "localhost:9092"
KAFKA_TOPIC = "snmp_metrics"
POLL_INTERVAL = 10  # seconds

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

async def poll_snmp(snmp_engine, ip, oids_list, community='public', hostname=None):
    """
    Poll multiple SNMP OIDs from a given device in a single request.
    This function is now more efficient by accepting a list of OIDs.
    """
    transport = await UdpTransportTarget.create((ip, 161))

    # Create a list of ObjectType objects from the OID strings for the get_cmd
    var_binds_to_get = [ObjectType(ObjectIdentity(oid)) for oid in oids_list]

    errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
        snmp_engine,  # <-- Use the single, shared SNMP engine
        CommunityData(community, mpModel=1),
        transport,
        ContextData(),
        *var_binds_to_get  # <-- The * unpacks the list into multiple arguments
    )

    result = {}
    if errorIndication:
        result['error'] = str(errorIndication)
    elif errorStatus:
        result['error'] = f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex)-1][0]}"
    else:
        # Loop through all the returned values from the single request
        for varBind in varBinds:
            result[str(varBind[0])] = str(varBind[1])

    # This creates a single, consolidated message for the device
    message = {
        "host": hostname or ip,
        "ip": ip,
        "collector_hostname": "LocalCollector",
        "timestamp": datetime.now().isoformat(),
        "results": result  # The results dict now contains all OIDs for the device
    }

    producer.send(KAFKA_TOPIC, message)
    print(f"✅ Sent consolidated SNMP data for {ip} to Kafka")


async def poll_all_devices():
    """
    Poll all devices from inventory.csv once.
    This is now optimized to create ONE task per DEVICE, not per OID.
    """
    # Create the SnmpEngine ONCE for the entire polling cycle.
    snmp_engine = SnmpEngine()
    
    with open("inventory.csv") as f:
        reader = csv.DictReader(f)
        tasks = []
        for row in reader:
            # Get all OIDs for this device from the CSV
            oids_to_poll = row["oids"].split(";")
            
            if not oids_to_poll:
                continue

            # Create a SINGLE task for this device with ALL its OIDs
            tasks.append(
                poll_snmp(
                    snmp_engine,
                    row["ip"],
                    oids_to_poll,  # Pass the entire list of OIDs
                    row.get("community", "public"),
                    row.get("hostname")
                )
            )

    # Concurrently run all the device-polling tasks
    if tasks:
        await asyncio.gather(*tasks)

    # Flush Kafka producer (still a blocking call, as per our earlier discussion)
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