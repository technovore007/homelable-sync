
import json
import requests

BASE_URL = "http://127.0.0.1:8000"

def main():
    response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
    response.raise_for_status()
    spec = response.json()

    paths = spec.get("paths", {})
    schemas = spec.get("components", {}).get("schemas", {})

    print("\n" + "=" * 72)
    print("HOMELABLE GRAPH API CONTRACT")
    print("=" * 72)

    for path, methods in paths.items():
        if not any(part in path for part in ("/nodes", "/edges")):
            continue

        for method, operation in methods.items():
            if method.lower() not in {
                "get", "post", "put", "patch", "delete"
            }:
                continue

            print(f"\n{method.upper():7} {path}")
            print("Operation:", operation.get("operationId", "-"))

            request_body = operation.get("requestBody", {})
            content = request_body.get("content", {})
            json_schema = content.get("application/json", {}).get("schema", {})

            if json_schema:
                print("Request schema:", json.dumps(json_schema, indent=2))

    print("\n" + "=" * 72)
    print("RELEVANT COMPONENT SCHEMAS")
    print("=" * 72)

    keywords = ("Node", "Edge", "Relationship", "Canvas")

    for name, schema in schemas.items():
        if not any(word.lower() in name.lower() for word in keywords):
            continue

        print(f"\n--- {name} ---")
        print("Required:", schema.get("required", []))

        properties = schema.get("properties", {})
        for field, details in properties.items():
            print(
                f"  {field}: "
                f"{details.get('type', details.get('$ref', 'unknown'))}"
                f"{' [nullable]' if details.get('nullable') else ''}"
            )

if __name__ == "__main__":
    main()
