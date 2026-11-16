import re


def normalize_mac(value):
    if not value:
        return None

    value = str(value).strip().lower().replace("-", ":")

    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value):
        return None

    return value


def resolve_identities(entities, inventory, nodes):
    """
    Match canonical entities to Homelable inventory and canvas nodes.

    Identity matching is based on exact MAC addresses.
    IP and hostname are supporting/reporting attributes only.
    """

    inventory_by_mac = {}
    nodes_by_device_id = {}
    nodes_by_mac = {}

    for device in inventory:
        mac = normalize_mac(device.get("mac"))
        if mac:
            inventory_by_mac.setdefault(mac, []).append(device)

    for node in nodes:
        device_id = node.get("device_id")
        if device_id:
            nodes_by_device_id.setdefault(device_id, []).append(node)

        mac = normalize_mac(node.get("mac"))
        if mac:
            nodes_by_mac.setdefault(mac, []).append(node)

    results = []

    for entity in entities:
        mac = normalize_mac(entity.get("mac"))

        result = {
            "entity_id": entity["id"],
            "canonical_key": entity["canonical_key"],
            "mac": mac,
            "entity_name": entity.get("display_name"),
            "status": "unmatched",
            "inventory_id": None,
            "inventory_name": None,
            "inventory_status": None,
            "node_id": None,
            "node_name": None,
            "reason": None,
        }

        if not mac:
            result["reason"] = "Canonical entity has no valid MAC"
            results.append(result)
            continue

        candidates = inventory_by_mac.get(mac, [])

        if len(candidates) > 1:
            result["status"] = "ambiguous"
            result["reason"] = (
                f"Multiple Homelable inventory records have MAC {mac}"
            )
            results.append(result)
            continue

        if not candidates:
            result["reason"] = "No Homelable inventory record with this MAC"
            results.append(result)
            continue

        device = candidates[0]
        inventory_id = device.get("id")

        result.update({
            "status": "matched",
            "inventory_id": inventory_id,
            "inventory_name": (
                device.get("label")
                or device.get("friendly_name")
                or device.get("hostname")
            ),
            "inventory_status": device.get("status"),
        })

        node_candidates = []

        if inventory_id:
            node_candidates = nodes_by_device_id.get(inventory_id, [])

        # Fallback only if no node is linked through device_id.
        if not node_candidates:
            node_candidates = nodes_by_mac.get(mac, [])

        if len(node_candidates) == 1:
            node = node_candidates[0]
            result["node_id"] = node.get("id")
            result["node_name"] = node.get("label")

        elif len(node_candidates) > 1:
            result["status"] = "ambiguous"
            result["reason"] = (
                "Inventory matched, but multiple canvas nodes reference it"
            )

        else:
            result["reason"] = "Inventory matched; no canvas node exists"

        results.append(result)

    return results