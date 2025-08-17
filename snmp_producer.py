import asyncio
import csv
from datetime import datetime
from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd
)

POLL_INTERVAL = 10  # seconds
OUTPUT_FILE = "snmp_results.csv"

# Ensure CSV has headers
with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["hostname", "ip", "port", "community", "collector_hostname", "timestamp", "oid", "value"])


async def poll_snmp(ip, port, oid, community="public", hostname=None):
    """Poll a single SNMP OID from a given device and port."""
    try:
        transport = UdpTransportTarget((ip, int(port)))
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),  # SNMP v2c
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        if errorIndication or errorStatus:
            print(f"⚠️  Skipping {hostname or ip}:{port} OID {oid} due to error: {errorIndication or errorStatus.prettyPrint()}")
            return

        for varBind in varBinds:
            oid_str = str(varBind[0])
            value_str = str(varBind[1])

            with open(OUTPUT_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    hostname or ip,
                    ip,
                    port,
                    community,
                    "LocalCollector",
                    datetime.now().isoformat(),
                    oid_str,
                    value_str
                ])
            print(f"✅ Saved SNMP data for {hostname or ip}:{port} (community={community}) OID {oid_str} = {value_str}")

    except Exception as e:
        print(f"❌ Error polling {hostname or ip}:{port} OID {oid}: {e}")


async def poll_all_devices():
    with open("inventory.csv") as f:
        reader = csv.DictReader(f)
        tasks = []
        for row in reader:
            oids = row["oids"].split(";")
            for oid in oids:
                tasks.append(
                    poll_snmp(
                        row["ip"],
                        row.get("port", 161),
                        oid.strip(),
                        row.get("community", "public"),
                        row.get("hostname")
                    )
                )
        await asyncio.gather(*tasks)


async def main():
    while True:
        print(f"\n📡 Starting SNMP polling at {datetime.now().isoformat()}")
        await poll_all_devices()
        print(f"⏳ Waiting {POLL_INTERVAL} seconds before next poll...\n")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
