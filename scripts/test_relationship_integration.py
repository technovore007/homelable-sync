
import sqlite3
from pathlib import Path

from reconciliation.relationships import (
    get_relationship_evidence,
    get_relationships,
    observe_relationship,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "synchronizer.db"


def main():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")

    try:
        db.execute("BEGIN")

        entities = db.execute(
            """
            SELECT id, canonical_key
            FROM entities
            ORDER BY canonical_key
            LIMIT 2
            """
        ).fetchall()

        if len(entities) != 2:
            raise RuntimeError(
                "Integration test requires at least two entities"
            )

        source_id, source_key = entities[0]
        target_id, target_key = entities[1]

        print("Source:", source_key)
        print("Target:", target_key)

        relationship_id, inserted = observe_relationship(
            db=db,
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type="integration_test",
            evidence_source="integration_test",
            evidence_type="synthetic_observation",
            confidence="test",
            payload={"purpose": "SQLite integration verification"},
            observed_at="2026-11-16T14:00:00+00:00",
        )

        relationships = get_relationships(db)
        evidence = get_relationship_evidence(db, relationship_id)

        assert any(
            item["id"] == relationship_id
            for item in relationships
        ), "Relationship was not persisted"

        assert len(evidence) == 1, "Evidence was not persisted"

        print("\nINTEGRATION TEST PASSED")
        print("Relationship ID:", relationship_id)
        print("Evidence inserted:", inserted)
        print("Evidence records:", len(evidence))

    finally:
        db.rollback()
        db.close()

    print("\nTransaction rolled back. No test records retained.")


if __name__ == "__main__":
    main()
