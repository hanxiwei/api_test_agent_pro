import os
import uuid

import pytest
import requests

BASE_URL = os.getenv("API_BASE_URL", 'http://localhost:8000').rstrip("/")


def _format_path(path: str, **params: str) -> str:
    for k, v in params.items():
        path = path.replace("{" + k + "}", str(v))
    return path


def test_pets_deletepet_deletepet():
    url = BASE_URL + _format_path("/pets/{petId}", petId="1")
    r = requests.delete(url, timeout=10)
    assert r.status_code < 500
