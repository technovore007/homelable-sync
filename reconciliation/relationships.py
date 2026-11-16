
import json
import sqlite3
import uuid

from datetime import datetime, timezone
from typing import Any


RELATIONSHIP_NAMESPACE = uuid.UUID(
    "d22e6d0b-2a69-4a68-9ad8-6d6e0e8b1b10"
)

VALID_STATUSES = {
    "candidate",
    "confirmed",
    "stale",
    "retired",
}


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def relationship_id_for(
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
) -> str:
    """Generate a stable ID for an entity relationship."""

    identity = (
        f"{source_entity_id}:"
        f"{target_entity_id}:"
        f"{relationship_type}"
    )

    return str(uuid.uuid5(RELATIONSHIP_NAMESPACE, identity))


def upsert_relationship(
    db: sqlite3.Connection,
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    status: str = "candidate",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Create or update a relationship between two canonical entities.

    Existing metadata is preserved and merged with new metadata.
    """

    if source_entity_id == target_entity_id:
        raise ValueError("An entity cannot have a relationship with itself")

    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid relationship status: {status}")

    if not relationship_type.strip():
        raise ValueError("Relationship type cannot be empty")

    relationship_id = relationship_id_for(
        source_entity_id,
        target_entity_id,
        relationship_type,
    )

    existing = db.execute(
        """
        SELECT metadata_json
        FROM relationships
        WHERE id = ?
        """,
        (relationship_id,),
    ).fetchone()

    existing_metadata = {}

    if existing:
        existing_metadata = json.loads(existing[0] or "{}")

    merged_metadata = {
        **existing_metadata,
        **(metadata or {}),
    }

    metadata_json = json.dumps(
        merged_metadata,
        sort_keys=True,
    )

    now = utc_now()

    db.execute(
        """
        INSERT INTO relationships (
            id,
            source_entity_id,
            target_entity_id,
            relationship_type,
            status,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT (
            source_entity_id,
            target_entity_id,
            relationship_type
        )
        DO UPDATE SET
            status = excluded.status,
            metadata_json = excluded.metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            relationship_id,
            source_entity_id,
            target_entity_id,
            relationship_type,
            status,
            metadata_json,
            now,
            now,
        ),
    )

    return relationship_id


def record_evidence(
    db: sqlite3.Connection,
    relationship_id: str,
    source: str,
    evidence_type: str,
    confidence: str,
    payload: dict[str, Any],
    observed_at: str | None = None,
) -> bool:
    """
    Record evidence for a relationship.

    Returns True if new evidence was inserted.
    Returns False if identical evidence already exists.
    """

    if not source.strip():
        raise ValueError("Evidence source cannot be empty")

    if not evidence_type.strip():
        raise ValueError("Evidence type cannot be empty")

    if not confidence.strip():
        raise ValueError("Evidence confidence cannot be empty")

    observed_at = observed_at or utc_now()

    payload_json = json.dumps(
        payload,
        sort_keys=True,
    )

    existing = db.execute(
        """
        SELECT 1
        FROM relationship_evidence
        WHERE relationship_id = ?
          AND source = ?
          AND evidence_type = ?
          AND observed_at = ?
          AND confidence = ?
          AND payload_json = ?
        LIMIT 1
        """,
        (
            relationship_id,
            source,
            evidence_type,
            observed_at,
            confidence,
            payload_json,
        ),
    ).fetchone()

    if existing:
        return False

    db.execute(
        """
        INSERT INTO relationship_evidence (
            id,
            relationship_id,
            source,
            evidence_type,
            observed_at,
            confidence,
            payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            relationship_id,
            source,
            evidence_type,
            observed_at,
            confidence,
            payload_json,
        ),
    )

    return True


def observe_relationship(
    db: sqlite3.Connection,
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    evidence_source: str,
    evidence_type: str,
    confidence: str,
    payload: dict[str, Any],
    observed_at: str | None = None,
    status: str = "candidate",
) -> tuple[str, bool]:
    """
    Create/update a relationship and attach its supporting evidence.

    Returns (relationship_id, evidence_inserted).
    """

    relationship_id = upsert_relationship(
        db=db,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        status=status,
    )

    evidence_inserted = record_evidence(
        db=db,
        relationship_id=relationship_id,
        source=evidence_source,
        evidence_type=evidence_type,
        confidence=confidence,
        payload=payload,
        observed_at=observed_at,
    )

    return relationship_id, evidence_inserted


def get_relationships(
    db: sqlite3.Connection,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve relationships and their metadata."""

    if status and status not in VALID_STATUSES:
        raise ValueError(f"Invalid relationship status: {status}")

    if status:
        rows = db.execute(
            """
            SELECT *
            FROM relationships
            WHERE status = ?
            ORDER BY created_at
            """,
            (status,),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT *
            FROM relationships
            ORDER BY created_at
            """
        ).fetchall()

    columns = [
        description[0]
        for description in db.execute(
            "SELECT * FROM relationships LIMIT 0"
        ).description
    ]

    results = []

    for row in rows:
        item = dict(zip(columns, row))
        item["metadata"] = json.loads(
            item.pop("metadata_json") or "{}"
        )
        results.append(item)

    return results


def get_relationship_evidence(
    db: sqlite3.Connection,
    relationship_id: str,
) -> list[dict[str, Any]]:
    """Retrieve all evidence associated with a relationship."""

    rows = db.execute(
        """
        SELECT *
        FROM relationship_evidence
        WHERE relationship_id = ?
        ORDER BY observed_at
        """,
        (relationship_id,),
    ).fetchall()

    columns = [
        description[0]
        for description in db.execute(
            "SELECT * FROM relationship_evidence LIMIT 0"
        ).description
    ]

    results = []

    for row in rows:
        item = dict(zip(columns, row))
        item["payload"] = json.loads(
            item.pop("payload_json")
        )
        results.append(item)

    return results
