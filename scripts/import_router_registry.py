
#!/usr/bin/env python3

import argparse
import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path


NAMESPACE = uuid.UUID("b4ed8d66-12e8-4b2b-87ea-f91f9d8c3e01")


SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_key TEXT NOT NULL UNIQUE,
    display_name TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    first_seen TEXT,
    last_seen TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_mappings (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    source_type TEXT,
    first_seen TEXT,
    last_seen TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id),
    source TEXT NOT NULL,
    observation_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(entity_id, source, observation_type, observed_at)
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL REFERENCES entities(id),
    target_entity_id TEXT NOT NULL REFERENCES entities(id),
    relationship_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS relationship_evidence (
    id TEXT PRIMARY KEY,
    relationship_id TEXT NOT NULL REFERENCES relationships(id),
    source TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    confidence TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT PRIMARY KEY,
    last_success_at TEXT,
    last_error TEXT,
    cursor TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_observations_entity
ON observations(entity_id);

CREATE INDEX IF NOT EXISTS idx_observations_time
ON observations(observed_at);

CREATE INDEX IF NOT EXISTS idx_source_mappings_entity
ON source_mappings(entity_id);

CREATE INDEX IF NOT EXISTS idx_relationships_source
ON relationships(source_entity_id);

CREATE INDEX IF NOT EXISTS idx_relationships_target
ON relationships(target_entity_id);
"""



def stable_id(value):
    return str(uuid.uuid5(NAMESPACE, value))


def normalize_mac(value):
    mac = value.strip().lower().replace("-", ":")
    parts = mac.split(":")

    if len(parts) != 6 or any(
        len(part) != 2
        or any(char not in "0123456789abcdef" for char in part)
        for part in parts
    ):
        raise ValueError(f"Invalid MAC address: {value}")

    return ":".join(parts)


def is_locally_administered(mac):
    first_octet = int(mac.split(":")[0], 16)
    return bool(first_octet & 0x02)


def load_registry(path):
    data = json.loads(path.read_text())

    if not isinstance(data, dict) or "devices" not in data:
        raise ValueError("Registry must contain a 'devices' field")

    raw_devices = data["devices"]

    if isinstance(raw_devices, dict):
        devices = []

        for registry_mac, record in raw_devices.items():
            if not isinstance(record, dict):
                raise ValueError(
                    f"Invalid device record for {registry_mac}"
                )

            record = dict(record)
            record.setdefault("mac_address", registry_mac)
            devices.append(record)

    elif isinstance(raw_devices, list):
        devices = raw_devices

    else:
        raise ValueError(
            "'devices' must be a dictionary or a list"
        )

    if not devices:
        raise ValueError("Router registry contains no devices")

    return data, devices


def import_registry(registry_path, database_path):
    registry, devices = load_registry(registry_path)

    now = datetime.now(timezone.utc).isoformat()

    database_path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(database_path)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA busy_timeout = 5000")
    db.executescript(SCHEMA)

    imported = 0
    observations_added = 0

    try:
        with db:
            for record in devices:
                mac = normalize_mac(record["mac_address"])

                canonical_key = f"physical-mac:{mac}"
                entity_id = stable_id(canonical_key)

                metadata = {
                    "mac_address": mac,
                    "locally_administered": is_locally_administered(mac),
                    "registry_metadata": record.get("metadata", {})
                }

                db.execute("""
                    INSERT INTO entities (
                        id, entity_type, canonical_key,
                        display_name, metadata_json,
                        first_seen, last_seen,
                        created_at, updated_at
                    )
                    VALUES (?, 'physical_device', ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(canonical_key) DO UPDATE SET
                        metadata_json = excluded.metadata_json,
                        last_seen = excluded.last_seen,
                        updated_at = excluded.updated_at
                """, (
                    entity_id,
                    canonical_key,
                    record.get("metadata", {}).get("name"),
                    json.dumps(metadata, sort_keys=True),
                    record.get("first_seen"),
                    record.get("last_seen"),
                    now,
                    now
                ))

                db.execute("""
                    INSERT INTO source_mappings (
                        id, entity_id, source, external_id,
                        source_type, first_seen, last_seen
                    )
                    VALUES (?, ?, 'router_registry', ?,
                            'mac_address', ?, ?)
                    ON CONFLICT(source, external_id) DO UPDATE SET
                        entity_id = excluded.entity_id,
                        last_seen = excluded.last_seen
                """, (
                    stable_id(f"router_registry:{mac}"),
                    entity_id,
                    mac,
                    record.get("first_seen"),
                    record.get("last_seen")
                ))

                imported += 1

                for source, observation in record.get(
                    "observations", {}
                ).items():

                    observed_at = observation.get("observed_at") or now
                    payload = observation.get("fields", {})

                    cursor = db.execute("""
                        INSERT OR IGNORE INTO observations (
                            id, entity_id, source,
                            observation_type, observed_at,
                            payload_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        stable_id(
                            f"{entity_id}:{source}:{observed_at}"
                        ),
                        entity_id,
                        source,
                        source,
                        observed_at,
                        json.dumps(payload, sort_keys=True)
                    ))

                    observations_added += cursor.rowcount

            db.execute("""
                INSERT INTO sync_state (
                    source, last_success_at, metadata_json
                )
                VALUES ('router_registry', ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    last_success_at = excluded.last_success_at,
                    last_error = NULL,
                    metadata_json = excluded.metadata_json
            """, (
                now,
                json.dumps({
                    "registry_version": registry.get("version"),
                    "registry_updated_at": registry.get("updated_at")
                }, sort_keys=True)
            ))

        print("\nRouter registry import successful.")
        print("Registry records processed:", imported)
        print("New observations inserted:", observations_added)

        for table in (
            "entities",
            "source_mappings",
            "observations",
            "relationships",
            "relationship_evidence"
        ):
            count = db.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table}: {count}")

        print(
            "Database integrity:",
            db.execute("PRAGMA integrity_check").fetchone()[0]
        )

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Import router registry into synchronizer SQLite"
    )

    parser.add_argument(
        "--registry",
        default="/home/admin0/network-observability/data/devices.json"
    )

    parser.add_argument(
        "--database",
        default="/home/admin0/homelable-sync/data/synchronizer.db"
    )

    args = parser.parse_args()

    import_registry(
        Path(args.registry),
        Path(args.database)
    )


if __name__ == "__main__":
    main()
