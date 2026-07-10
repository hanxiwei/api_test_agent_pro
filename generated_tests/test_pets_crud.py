import os
import uuid

import pytest
import requests

BASE_URL = os.getenv("API_BASE_URL", 'http://localhost:8000').rstrip("/")


def _format_path(path: str, **params: str) -> str:
    for k, v in params.items():
        path = path.replace("{" + k + "}", str(v))
    return path


def test_pets_crud_createpet():
    url = BASE_URL + "/pets"
    payload = {"name": "test-" + uuid.uuid4().hex[:8]}
    r = requests.post(url, json=payload, timeout=10)
    assert r.status_code < 500


def test_pets_crud_getpet():
    url = BASE_URL + _format_path("/pets/{petId}", petId="1")
    r = requests.get(url, timeout=10)
    assert r.status_code < 500


def test_pets_crud_updatepet():
    url = BASE_URL + _format_path("/pets/{petId}", petId="1")
    payload = {"name": "test-" + uuid.uuid4().hex[:8]}
    r = requests.put(url, json=payload, timeout=10)
    assert r.status_code < 500


def test_pets_crud_deletepet():
    url = BASE_URL + _format_path("/pets/{petId}", petId="1")
    r = requests.delete(url, timeout=10)
    assert r.status_code < 500
