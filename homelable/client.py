
import getpass
import os
from typing import Any

import requests


class HomelableAPIError(Exception):
    """Raised when the Homelable API returns an unexpected response."""


class HomelableClient:
    """Authenticated HTTP client for the Homelable REST API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000/api/v1",
        username: str = "admin0",
        password: str | None = None,
        timeout: int = 15,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        if password is None:
            password = os.getenv("HOMELABLE_PASSWORD")

        if not password:
            password = getpass.getpass("Homelable password: ")

        self._authenticate(password)

    # ------------------------------------------------------------------
    # Authentication and HTTP transport
    # ------------------------------------------------------------------

    def _authenticate(self, password: str) -> None:
        response = self.session.post(
            f"{self.base_url}/auth/login",
            json={
                "username": self.username,
                "password": password,
            },
            timeout=self.timeout,
        )

        if not response.ok:
            raise HomelableAPIError(
                f"Authentication failed: HTTP {response.status_code}"
            )

        try:
            token_data = response.json()
        except ValueError as exc:
            raise HomelableAPIError(
                "Authentication response was not valid JSON"
            ) from exc

        token = token_data.get("access_token")

        if not token:
            raise HomelableAPIError(
                "Authentication response did not contain an access token"
            )

        self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Execute an authenticated API request."""

        response = self.session.request(
            method,
            f"{self.base_url}/{path.lstrip('/')}",
            timeout=self.timeout,
            **kwargs,
        )

        if not response.ok:
            raise HomelableAPIError(
                f"{method} {path} failed: "
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise HomelableAPIError(
                f"{method} {path} returned invalid JSON "
                f"(HTTP {response.status_code})"
            ) from exc

    def get_openapi(self) -> dict:
        """Retrieve the Homelable OpenAPI specification."""

        url = self.base_url.replace("/api/v1", "") + "/openapi.json"

        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Designs and canvas
    # ------------------------------------------------------------------

    def get_designs(self) -> list[dict]:
        return self._request("GET", "/designs")

    def get_canvas(self) -> dict:
        return self._request("GET", "/canvas")

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def get_nodes(self) -> list[dict]:
        return self._request("GET", "/nodes")

    def get_node(self, node_id: str) -> dict:
        return self._request("GET", f"/nodes/{node_id}")

    def create_node(self, payload: dict) -> dict:
        return self._request("POST", "/nodes", json=payload)

    def update_node(self, node_id: str, payload: dict) -> dict:
        return self._request("PATCH", f"/nodes/{node_id}", json=payload)

    def delete_node(self, node_id: str) -> Any:
        return self._request("DELETE", f"/nodes/{node_id}")

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def get_edges(self) -> list[dict]:
        return self._request("GET", "/edges")

    def create_edge(self, payload: dict) -> dict:
        return self._request("POST", "/edges", json=payload)

    def update_edge(self, edge_id: str, payload: dict) -> dict:
        return self._request("PATCH", f"/edges/{edge_id}", json=payload)

    def delete_edge(self, edge_id: str) -> Any:
        return self._request("DELETE", f"/edges/{edge_id}")

    # ------------------------------------------------------------------
    # Device inventory
    # ------------------------------------------------------------------

    def get_pending_devices(self) -> list[dict]:
        return self._request("GET", "/scan/pending")

    def get_hidden_devices(self) -> list[dict]:
        return self._request("GET", "/scan/hidden")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
