import unittest

from identity.resolver import normalize_mac, resolve_identities


class ResolverTests(unittest.TestCase):

    def setUp(self):
        self.entities = [
            {
                "id": "entity-1",
                "canonical_key": "physical-mac:aa:bb:cc:dd:ee:01",
                "display_name": "Test Device",
                "mac": "AA:BB:CC:DD:EE:01",
            },
            {
                "id": "entity-2",
                "canonical_key": "physical-mac:aa:bb:cc:dd:ee:02",
                "display_name": "Missing Device",
                "mac": "aa:bb:cc:dd:ee:02",
            },
        ]

        self.inventory = [
            {
                "id": "inventory-1",
                "mac": "aa:bb:cc:dd:ee:01",
                "label": "Test Device",
                "status": "approved",
            },
        ]

        self.nodes = [
            {
                "id": "node-1",
                "device_id": "inventory-1",
                "mac": "aa:bb:cc:dd:ee:01",
                "label": "Test Device",
            },
        ]

    def test_normalize_mac(self):
        self.assertEqual(
            normalize_mac("AA-BB-CC-DD-EE-01"),
            "aa:bb:cc:dd:ee:01",
        )

    def test_invalid_mac(self):
        self.assertIsNone(normalize_mac("not-a-mac"))

    def test_exact_mac_match(self):
        results = resolve_identities(
            self.entities, self.inventory, self.nodes
        )

        self.assertEqual(results[0]["status"], "matched")
        self.assertEqual(results[0]["inventory_id"], "inventory-1")
        self.assertEqual(results[0]["node_id"], "node-1")

    def test_unmatched_entity(self):
        results = resolve_identities(
            self.entities, self.inventory, self.nodes
        )

        self.assertEqual(results[1]["status"], "unmatched")

    def test_duplicate_inventory_mac_is_ambiguous(self):
        duplicate = dict(self.inventory[0])
        duplicate["id"] = "inventory-duplicate"

        results = resolve_identities(
            self.entities,
            self.inventory + [duplicate],
            self.nodes,
        )

        self.assertEqual(results[0]["status"], "ambiguous")

    def test_ip_does_not_establish_identity(self):
        entity = [{
            "id": "entity-3",
            "canonical_key": "unknown",
            "display_name": "IP-only device",
            "mac": None,
            "ip": "192.168.1.50",
        }]

        inventory = [{
            "id": "inventory-3",
            "ip": "192.168.1.50",
            "mac": None,
        }]

        results = resolve_identities(entity, inventory, [])

        self.assertEqual(results[0]["status"], "unmatched")


if __name__ == "__main__":
    unittest.main()