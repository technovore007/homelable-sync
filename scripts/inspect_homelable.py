import json

from homelable.client import HomelableClient


client = HomelableClient()

try:
    spec = client.get_openapi()

    print("\n========== INVENTORY-RELATED API ROUTES ==========")

    for path, methods in sorted(spec.get("paths", {}).items()):
        if any(word in path.lower() for word in (
            "device", "inventory", "scan", "node", "canvas"
        )):
            for method, details in methods.items():
                if method.lower() in (
                    "get", "post", "put", "patch", "delete"
                ):
                    print(
                        method.upper(),
                        path,
                        "-",
                        details.get("summary", "")
                    )

    print("\n========== CURRENT HOMELABLE DATA ==========")

    for name, fetch in (
        ("DESIGNS", client.get_designs),
        ("NODES", client.get_nodes),
        ("EDGES", client.get_edges),
        ("CANVAS", client.get_canvas),
        ("PENDING DEVICES", client.get_pending_devices),
        ("HIDDEN DEVICES", client.get_hidden_devices),
    ):
        result = fetch()

        print(f"\n{name}")

        if isinstance(result, list):
            print("Count:", len(result))
            if result:
                print(json.dumps(result[0], indent=2))
        else:
            print(json.dumps(result, indent=2))

finally:
    client.close()
