import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path

from identity.resolver import resolve_identities


def load_entities(db):
    rows = db.execute("""
        SELECT id, canonical_key, display_name, metadata_json
        FROM entities
        ORDER BY canonical_key
    """).fetchall()

    entities = []

    for row in rows:
        metadata = json.loads(row["metadata_json"] or "{}")

        entities.append({
            "id": row["id"],
            "canonical_key": row["canonical_key"],
            "display_name": row["display_name"],
            "mac": metadata.get("mac_address"),
        })

    return entities


def save_mapping(db, entity_id, source, external_id, source_type):
    now = datetime.now(timezone.utc).isoformat()

    mapping_id = str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"homelable-sync:{source}:{external_id}"
    ))

    db.execute("""
        INSERT INTO source_mappings (
            id, entity_id, source, external_id,
            source_type, first_seen, last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            entity_id = excluded.entity_id,
            source_type = excluded.source_type,
            last_seen = excluded.last_seen
    """, (
        mapping_id,
        entity_id,
        source,
        external_id,
        source_type,
        now,
        now,
    ))


def reconcile(db_path, inventory, nodes, save_mappings=False):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    try:
        entities = load_entities(db)

        results = resolve_identities(
            entities=entities,
            inventory=inventory,
            nodes=nodes,
        )

        if save_mappings:
            with db:
                for result in results:
                    if result["status"] != "matched":
                        continue

                    if result["inventory_id"]:
                        save_mapping(
                            db,
                            result["entity_id"],
                            "homelable_inventory",
                            result["inventory_id"],
                            "device_inventory",
                        )

                    if result["node_id"]:
                        save_mapping(
                            db,
                            result["entity_id"],
                            "homelable_node",
                            result["node_id"],
                            "canvas_node",
                        )

        return results

    finally:
        db.close()