"""Thin HTTP client for the backend API.

Replaces the old save_system.py (flat-file JSON) and the in-process
World/environment_generator calls that used to live in main.py: the client
now sends/reads slot state over local HTTP instead of touching a save file
or generating environments itself.
"""

import requests
from config import BACKEND_BASE_URL, BACKEND_REQUEST_TIMEOUT_SECONDS

_session = requests.Session()


class BackendUnavailableError(Exception):
    """Raised when the backend can't be reached or returns an error."""


def _request(method: str, path: str, **kwargs) -> dict:
    url = f"{BACKEND_BASE_URL}{path}"
    try:
        response = _session.request(method, url, timeout=BACKEND_REQUEST_TIMEOUT_SECONDS, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise BackendUnavailableError(str(exc)) from exc


def health_check() -> dict:
    return _request("GET", "/health")


def list_slots() -> list[dict]:
    return _request("GET", "/slots")


def get_slot(slot_id: int) -> dict:
    return _request("GET", f"/slots/{slot_id}")


def new_slot(slot_id: int) -> dict:
    return _request("POST", f"/slots/{slot_id}/new")


def reset_slot(slot_id: int) -> dict:
    return _request("POST", f"/slots/{slot_id}/reset")


def patch_slot(slot_id: int, **fields) -> dict:
    return _request("PATCH", f"/slots/{slot_id}", json=fields)
