
import getpass
import os
from typing import Any

import requests


class HomelableAPIError(Exception):
    """Raised when the Homelable API returns an unexpected response."""


class HomelableClient:
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

        token_data = response.json()
        token = token_data.get("access_token")

        if not token:
            raise HomelableAPIError(
                "Authentication response did not contain an access token"
            )

        self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
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

        if response.status_code == 204:
            return None

        return response.json()

    def get_openapi(self) -> dict:
        response = requests.get(
            self.base_url.replace("/api/v1", "") + "/openapi.json",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_designs(self) -> list[dict]:
        return self._request("GET", "/designs")

    def get_nodes(self) -> list[dict]:
        return self._request("GET", "/nodes")

    def get_edges(self) -> list[dict]:
        return self._request("GET", "/edges")

    def get_canvas(self) -> dict:
        return self._request("GET", "/canvas")

    def get_pending_devices(self) -> list[dict]:
        return self._request("GET", "/scan/pending")

    def get_hidden_devices(self) -> list[dict]:
        return self._request("GET", "/scan/hidden")

    def close(self) -> None:
        self.session.close()
