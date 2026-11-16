#!/usr/bin/env python3

import argparse
import json
import sqlite3
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from homelable.client import HomelableClient
from reconciliation.homelable import reconcile


DB_PATH = ROOT / "data" / "synchronizer.db"


def unwrap_list(data):
    """Accept either a direct list or a common API list wrapper."""

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("items", "devices", "nodes", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    raise ValueError(
        f"Expected an API list response, received: {type(data).__name__}"
    )


def load_inventory(client):
    return unwrap_list(client.get_pending_devices())


def load_nodes(client):
    return unwrap_list(client.get_nodes())


def load_router_entity_count():
    with sqlite3.connect(DB_PATH) as db:
        return db.execute(
            "SELECT COUNT(*) FROM entities"
        ).fetchone()[0]


def print_report(results, inventory, nodes, save_mappings):
    matched = [r for r in results if r["status"] == "matched"]
    unmatched = [r for r in results if r["status"] == "unmatched"]
    ambiguous = [r for r in results if r["status"] == "ambiguous"]

    matched_inventory_ids = {
        r["inventory_id"] for r in results if r["inventory_id"]
    }

    unmatched_inventory = [
        d for d in inventory
        if d.get("id") not in matched_inventory_ids
    ]

    print("\n" + "=" * 72)
    print("HOMELABLE IDENTITY RECONCILIATION")
    print("=" * 72)

    print(f"Router canonical entities : {len(results)}")
    print(f"Homelable inventory       : {len(inventory)}")
    print(f"Canvas nodes              : {len(nodes)}")

    print("\nRESULT SUMMARY")
    print("-" * 72)
    print(f"Matched                   : {len(matched)}")
    print(f"Unmatched                 : {len(unmatched)}")
    print(f"Ambiguous                 : {len(ambiguous)}")
    print(f"Inventory without match   : {len(unmatched_inventory)}")

    print("\nMATCHED IDENTITIES")
    print("-" * 72)

    for r in matched:
        node = r["node_name"] or "No canvas node"
        print(
            f"[MATCH] {r['entity_name'] or r['mac']}\n"
            f"        MAC       : {r['mac']}\n"
            f"        Inventory : {r['inventory_id']} "
            f"({r['inventory_name'] or 'Unnamed'})\n"
            f"        Node      : {r['node_id'] or 'None'} ({node})"
        )

    print("\nUNMATCHED CANONICAL ENTITIES")
    print("-" * 72)

    for r in unmatched:
        print(
            f"[UNMATCHED] {r['entity_name'] or r['mac']} "
            f"| {r['mac']} | {r['reason']}"
        )

    print("\nAMBIGUOUS IDENTITIES")
    print("-" * 72)

    for r in ambiguous:
        print(
            f"[AMBIGUOUS] {r['entity_name'] or r['mac']} "
            f"| {r['mac']} | {r['reason']}"
        )

    print("\nHOMELABLE INVENTORY WITHOUT ROUTER MATCH")
    print("-" * 72)

    for d in unmatched_inventory:
        print(
            f"[INVENTORY ONLY] "
            f"{d.get('label') or d.get('hostname') or 'Unnamed'} "
            f"| MAC: {d.get('mac') or 'Unknown'} "
            f"| ID: {d.get('id')} "
            f"| Status: {d.get('status', 'Unknown')}"
        )

    print("\n" + "=" * 72)

    if save_mappings:
        print("Local SQLite mappings saved.")
        print("Homelable API was not modified.")
    else:
        print("DRY RUN: no database mappings or Homelable data were modified.")
        print("Use --save-mappings to persist confirmed mappings locally.")

    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile router entities with Homelable inventory."
    )

    parser.add_argument(
        "--save-mappings",
        action="store_true",
        help="Persist confirmed UUID mappings in local SQLite only.",
    )

    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Synchronizer database not found: {DB_PATH}")

    if load_router_entity_count() == 0:
        raise SystemExit("No canonical entities found. Import the router registry first.")

    client = HomelableClient()

    try:
        inventory = load_inventory(client)
        nodes = load_nodes(client)

        results = reconcile(
            db_path=DB_PATH,
            inventory=inventory,
            nodes=nodes,
            save_mappings=args.save_mappings,
        )

        print_report(
            results,
            inventory,
            nodes,
            args.save_mappings,
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()