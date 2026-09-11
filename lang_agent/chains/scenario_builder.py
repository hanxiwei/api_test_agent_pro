from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..io.parser import Endpoint


@dataclass(frozen=True)
class Scenario:
    resource: str
    name: str
    endpoints: list[Endpoint]


def _resource_key(endpoint: Endpoint) -> str:
    if endpoint.tags:
        return endpoint.tags[0]
    parts = [p for p in endpoint.path.split("/") if p]
    if parts:
        return parts[0]
    return "default"


def build_scenarios(endpoints: Iterable[Endpoint]) -> list[Scenario]:
    by_resource: dict[str, list[Endpoint]] = {}
    for ep in endpoints:
        by_resource.setdefault(_resource_key(ep), []).append(ep)

    scenarios: list[Scenario] = []
    for resource, eps in sorted(by_resource.items(), key=lambda x: x[0]):
        method_map: dict[str, Endpoint] = {e.method: e for e in eps}

        crud_chain: list[Endpoint] = []
        for m in ["post", "get", "put", "delete"]:
            if m in method_map:
                crud_chain.append(method_map[m])
        if len(crud_chain) >= 2:
            scenarios.append(
                Scenario(resource=resource, name=f"{resource}_crud", endpoints=crud_chain)
            )

        for ep in eps:
            scenarios.append(
                Scenario(resource=resource, name=f"{resource}_{ep.operation_id}", endpoints=[ep])
            )

    return scenarios
