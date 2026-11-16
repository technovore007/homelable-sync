
import sqlite3
import unittest

from reconciliation.relationships import (
    get_relationship_evidence,
    get_relationships,
    observe_relationship,
    record_evidence,
    relationship_id_for,
    upsert_relationship,
)


class RelationshipTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite3.connect(":memory:")

        self.db.executescript("""
            CREATE TABLE relationships (
                id TEXT PRIMARY KEY,
                source_entity_id TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(
                    source_entity_id,
                    target_entity_id,
                    relationship_type
                )
            );

            CREATE TABLE relationship_evidence (
                id TEXT PRIMARY KEY,
                relationship_id TEXT NOT NULL
                    REFERENCES relationships(id),
                source TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                confidence TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
        """)

    def tearDown(self):
        self.db.close()

    def test_relationship_id_is_deterministic(self):
        first = relationship_id_for("a", "b", "connected_to")
        second = relationship_id_for("a", "b", "connected_to")

        self.assertEqual(first, second)

    def test_relationship_creation(self):
        relationship_id = upsert_relationship(
            self.db,
            "entity-a",
            "entity-b",
            "connected_to",
        )

        self.db.commit()

        relationships = get_relationships(self.db)

        self.assertEqual(len(relationships), 1)
        self.assertEqual(
            relationships[0]["id"],
            relationship_id,
        )

    def test_repeated_upsert_does_not_duplicate(self):
        first = upsert_relationship(
            self.db,
            "entity-a",
            "entity-b",
            "connected_to",
        )

        second = upsert_relationship(
            self.db,
            "entity-a",
            "entity-b",
            "connected_to",
        )

        self.assertEqual(first, second)
        self.assertEqual(len(get_relationships(self.db)), 1)

    def test_metadata_is_preserved(self):
        upsert_relationship(
            self.db,
            "entity-a",
            "entity-b",
            "connected_to",
            metadata={"router": "huawei"},
        )

        upsert_relationship(
            self.db,
            "entity-a",
            "entity-b",
            "connected_to",
            metadata={"band": "5GHz"},
        )

        relationship = get_relationships(self.db)[0]

        self.assertEqual(
            relationship["metadata"],
            {"router": "huawei", "band": "5GHz"},
        )

    def test_duplicate_evidence_is_ignored(self):
        relationship_id = upsert_relationship(
            self.db,
            "entity-a",
            "entity-b",
            "connected_to",
        )

        arguments = {
            "relationship_id": relationship_id,
            "source": "huawei_router",
            "evidence_type": "wifi_association",
            "confidence": "high",
            "payload": {"band": "5GHz"},
            "observed_at": "2026-11-16T14:00:00+00:00",
        }

        first = record_evidence(self.db, **arguments)
        second = record_evidence(self.db, **arguments)

        self.assertTrue(first)
        self.assertFalse(second)

        self.assertEqual(
            len(get_relationship_evidence(self.db, relationship_id)),
            1,
        )

    def test_observation_creates_relationship_and_evidence(self):
        relationship_id, inserted = observe_relationship(
            db=self.db,
            source_entity_id="entity-a",
            target_entity_id="entity-b",
            relationship_type="connected_to",
            evidence_source="huawei_router",
            evidence_type="wifi_association",
            confidence="high",
            payload={"band": "5GHz"},
            observed_at="2026-11-16T14:00:00+00:00",
        )

        self.assertTrue(inserted)
        self.assertEqual(len(get_relationships(self.db)), 1)
        self.assertEqual(
            len(get_relationship_evidence(self.db, relationship_id)),
            1,
        )

    def test_self_relationship_is_rejected(self):
        with self.assertRaises(ValueError):
            upsert_relationship(
                self.db,
                "entity-a",
                "entity-a",
                "connected_to",
            )


if __name__ == "__main__":
    unittest.main()
