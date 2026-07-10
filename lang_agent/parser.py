from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal

try:
    from prance import ResolvingParser
except Exception:  # type: ignore[no-redef]
    ResolvingParser = None  # type: ignore[assignment]

import yaml


HttpMethod = Literal["get", "post", "put", "patch", "delete", "head", "options"]


@dataclass(frozen=True)
class Endpoint:
    method: HttpMethod
    path: str
    operation_id: str
    tags: list[str]
    parameters: list[dict[str, Any]]
    request_schema: dict[str, Any] | None
    responses: dict[str, Any]


def load_openapi_spec(openapi_path: str | Path) -> dict[str, Any]:
    openapi_path = Path(openapi_path)
    if ResolvingParser is not None:
        try:
            parser = ResolvingParser(str(openapi_path), lazy=True, strict=False)
            parser.parse()
            spec: dict[str, Any] = parser.specification  # type: ignore[assignment]
            return spec
        except Exception:
            pass

    text = openapi_path.read_text(encoding="utf-8")
    if openapi_path.suffix.lower() in {".json"}:
        obj = json.loads(text)
    else:
        obj = yaml.safe_load(text)
    if not isinstance(obj, dict):
        return {}
    return obj


def parse_openapi(openapi_path: str | Path) -> list[Endpoint]:
    spec = load_openapi_spec(openapi_path)

    paths: dict[str, Any] = spec.get("paths", {}) or {}
    endpoints: list[Endpoint] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        common_parameters = path_item.get("parameters", []) or []

        for method, op in path_item.items():
            m = str(method).lower()
            if m not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(op, dict):
                continue

            operation_id = str(op.get("operationId") or f"{m}_{path.strip('/').replace('/', '_')}")
            tags = [str(x) for x in (op.get("tags", []) or [])]
            parameters = []
            if isinstance(common_parameters, list):
                parameters.extend(common_parameters)
            if isinstance(op.get("parameters"), list):
                parameters.extend(op.get("parameters", []) or [])

            request_schema = None
            request_body = op.get("requestBody") or {}
            if isinstance(request_body, dict):
                content = request_body.get("content") or {}
                if isinstance(content, dict):
                    app_json = content.get("application/json") or {}
                    if isinstance(app_json, dict):
                        schema = app_json.get("schema")
                        if isinstance(schema, dict):
                            request_schema = schema

            responses = op.get("responses", {}) or {}
            if not isinstance(responses, dict):
                responses = {}

            endpoints.append(
                Endpoint(
                    method=m,  # type: ignore[arg-type]
                    path=str(path),
                    operation_id=operation_id,
                    tags=tags,
                    parameters=parameters,
                    request_schema=request_schema,
                    responses=responses,
                )
            )

    return endpoints
