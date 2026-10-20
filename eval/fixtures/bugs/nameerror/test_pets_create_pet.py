from __future__ import annotations

import uuid

from api.pets_api import create_pet
from utils.assertions import assert_response_ok, response_json
from utils.data_loader import load_resource_data


def _prepare_payload(payload: dict, suffix: str) -> dict:
    out = dict(payload or {})
    if "name" in out and isinstance(out["name"], str):
        out["name"] = f"{out['name']}-{suffix}"
    if "title" in out and isinstance(out["title"], str):
        out["title"] = f"{out['title']}-{suffix}"
    return out


def test_pets_create_pet(base_url, request_session):
    resource_data = load_resource_data("pets")
    path_params = dict(resource_data.get("path_params") or {})
    create_payload = _prepare_payload(resource_data.get("create_payload") or {}, uuid.uuid4().hex[:6])
    update_payload = _prepare_payload(resource_data.get("update_payload") or {}, uuid.uuid4().hex[:6])
    entity_id = None

    response_1 = create_pett(request_session, base_url, payload=create_payload)
    assert_response_ok(response_1, expected=[201], context="POST /pets")
    created = response_json(response_1)
    entity_id = created.get("id") or entity_id or "1"
    for key in list(path_params):
        if key.lower().endswith('id'):
            path_params[key] = entity_id
    assert entity_id is not None
