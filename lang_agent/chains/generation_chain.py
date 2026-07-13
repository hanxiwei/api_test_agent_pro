from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except Exception:  # type: ignore[no-redef]
    def retry(*args, **kwargs):  # type: ignore[no-redef]
        def deco(fn):
            return fn

        return deco

    def stop_after_attempt(*args, **kwargs):  # type: ignore[no-redef]
        return None

    def wait_exponential(*args, **kwargs):  # type: ignore[no-redef]
        return None

from ..config import Settings
from ..parser import Endpoint
from ..scenario_builder import Scenario
from .llm_factory import build_chat_llm
from .prompts import generation_prompt


def _extract_code(text: str) -> str:
    if "```" not in text:
        return text.strip() + "\n"
    parts = text.split("```")
    for i in range(len(parts) - 1):
        block = parts[i + 1]
        if block.lstrip().startswith("python"):
            block = block.lstrip()[6:]
        code = block.strip("\n")
        if code:
            return code.strip() + "\n"
    return text.strip() + "\n"


def _snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    value = value.strip("_").lower()
    return value or "default"


def _resource_name(resource: str) -> str:
    return _snake_case(resource)


def _operation_name(endpoint: Endpoint) -> str:
    return _snake_case(endpoint.operation_id or f"{endpoint.method}_{endpoint.path}")


def _path_parameters(endpoint: Endpoint) -> list[str]:
    out: list[str] = []
    for param in endpoint.parameters:
        if not isinstance(param, dict):
            continue
        if str(param.get("in") or "") != "path":
            continue
        name = str(param.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def _success_codes(endpoint: Endpoint) -> list[int]:
    out: list[int] = []
    for code in (endpoint.responses or {}).keys():
        text = str(code)
        if not text.startswith("2"):
            continue
        try:
            out.append(int(text))
        except ValueError:
            continue
    return out or [200]


def _sample_scalar(schema: dict[str, Any] | None, *, fallback_key: str = "value") -> Any:
    if not isinstance(schema, dict):
        return f"sample-{fallback_key}"
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    schema_type = str(schema.get("type") or "")
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1
    if schema_type == "boolean":
        return False
    if schema_type == "array":
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            return [_sample_scalar(item_schema, fallback_key=fallback_key)]
        return []
    if schema_type == "object":
        return _payload_from_schema(schema, resource=fallback_key)
    if fallback_key.lower().endswith("id"):
        return "1"
    if "name" in fallback_key.lower():
        return f"{fallback_key}-demo"
    return f"sample-{fallback_key}"


def _payload_from_schema(schema: dict[str, Any] | None, *, resource: str) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"name": f"{resource}-demo"}
    if "$ref" in schema:
        return {"name": f"{resource}-demo"}

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {"name": f"{resource}-demo"}

    payload: dict[str, Any] = {}
    for key, value in properties.items():
        if not isinstance(value, dict):
            continue
        if key == "id":
            continue
        payload[key] = _sample_scalar(value, fallback_key=key)

    if not payload:
        payload["name"] = f"{resource}-demo"
    return payload


def _resource_seed_data(resource: str, endpoints: list[Endpoint]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "resource": resource,
        "path_params": {},
        "create_payload": {"name": f"{resource}-demo"},
        "update_payload": {"name": f"{resource}-updated"},
    }

    for endpoint in endpoints:
        for name in _path_parameters(endpoint):
            data["path_params"].setdefault(name, "1")
        if endpoint.method == "post":
            data["create_payload"] = _payload_from_schema(endpoint.request_schema, resource=resource)
        elif endpoint.method in {"put", "patch"}:
            data["update_payload"] = _payload_from_schema(endpoint.request_schema, resource=resource)

    if not data["path_params"] and resource:
        data["path_params"][f"{resource}_id"] = "1"
    return data


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean_previous_generated_tests(output_dir: Path) -> None:
    for folder in ["config", "api", "testcases", "utils", "data", "reports"]:
        target = output_dir / folder
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    for file_name in ["conftest.py", "pytest.ini"]:
        (output_dir / file_name).unlink(missing_ok=True)
    for file_path in output_dir.glob("test_*.py"):
        file_path.unlink(missing_ok=True)


def _scaffold_files(output_dir: Path, settings: Settings) -> None:
    for folder in ["config", "api", "testcases", "utils", "data", "reports"]:
        (output_dir / folder).mkdir(parents=True, exist_ok=True)
    for pkg in ["api", "testcases", "utils"]:
        _write_file(output_dir / pkg / "__init__.py", "")

    settings_yaml = yaml.safe_dump(
        {"base_url": settings.base_url, "timeout": 10},
        allow_unicode=True,
        sort_keys=False,
    )
    _write_file(output_dir / "config" / "settings.yaml", settings_yaml)
    _write_file(output_dir / "reports" / ".gitkeep", "")

    _write_file(
        output_dir / "utils" / "http_client.py",
        """from __future__ import annotations

from typing import Any


def build_url(base_url: str, path: str, path_params: dict[str, Any] | None = None) -> str:
    out = path
    for key, value in (path_params or {}).items():
        out = out.replace("{" + key + "}", str(value))
    return base_url.rstrip("/") + out


def api_request(
    session,
    method: str,
    base_url: str,
    path: str,
    *,
    path_params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    timeout: int = 10,
):
    url = build_url(base_url, path, path_params=path_params)
    return session.request(method=method.upper(), url=url, json=json, timeout=timeout)
""",
    )

    _write_file(
        output_dir / "utils" / "assertions.py",
        """from __future__ import annotations


def assert_response_ok(response, *, expected: list[int] | None = None, context: str = "") -> None:
    message = f"{context} status={response.status_code}, body={response.text}"
    assert response.status_code < 500, message
    if expected:
        assert response.status_code in expected, message


def response_json(response):
    if not response.text:
        return {}
    try:
        return response.json()
    except Exception:
        return {}
""",
    )

    _write_file(
        output_dir / "utils" / "data_loader.py",
        """from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_resource_data(resource: str) -> dict:
    path = PROJECT_ROOT / "data" / f"{resource}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(data, dict):
        return data
    return {}
""",
    )

    _write_file(
        output_dir / "conftest.py",
        """from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import requests
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_settings() -> dict:
    path = PROJECT_ROOT / "config" / "settings.yaml"
    if not path.exists():
        return {"base_url": "http://localhost:8000", "timeout": 10}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(data, dict):
        return data
    return {"base_url": "http://localhost:8000", "timeout": 10}


@pytest.fixture(scope="session")
def settings() -> dict:
    return _load_settings()


@pytest.fixture(scope="session")
def base_url(settings: dict) -> str:
    return str(os.getenv("API_BASE_URL", settings.get("base_url", "http://localhost:8000"))).rstrip("/")


@pytest.fixture(scope="session")
def request_timeout(settings: dict) -> int:
    return int(settings.get("timeout", 10))


@pytest.fixture()
def request_session():
    with requests.Session() as session:
        yield session
""",
    )

    _write_file(
        output_dir / "pytest.ini",
        """[pytest]
testpaths = testcases
python_files = test_*.py
addopts = -q
""",
    )


def _api_module_code(resource: str, endpoints: list[Endpoint]) -> str:
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from utils.http_client import api_request",
        "",
    ]
    seen: set[str] = set()
    for endpoint in endpoints:
        function_name = _operation_name(endpoint)
        if function_name in seen:
            continue
        seen.add(function_name)

        path_params = _path_parameters(endpoint)
        signature_parts = ["session", "base_url"]
        if endpoint.method in {"post", "put", "patch"}:
            signature_parts.append("payload")
        signature_parts.extend(path_params)
        signature = ", ".join(signature_parts)

        lines.append(f"def {function_name}({signature}):")
        if path_params:
            path_map = ", ".join(f'"{name}": {name}' for name in path_params)
            lines.append(f"    path_params = {{{path_map}}}")
        else:
            lines.append("    path_params = None")

        if endpoint.method in {"post", "put", "patch"}:
            lines.append(
                f'    return api_request(session, "{endpoint.method}", base_url, "{endpoint.path}", path_params=path_params, json=payload)'
            )
        else:
            lines.append(
                f'    return api_request(session, "{endpoint.method}", base_url, "{endpoint.path}", path_params=path_params)'
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _payload_var_for_method(method: str) -> str | None:
    if method == "post":
        return "create_payload"
    if method in {"put", "patch"}:
        return "update_payload"
    return None


def _call_expression(endpoint: Endpoint) -> str:
    function_name = _operation_name(endpoint)
    args = ["request_session", "base_url"]
    payload_var = _payload_var_for_method(endpoint.method)
    if payload_var is not None:
        args.append(f"payload={payload_var}")
    for name in _path_parameters(endpoint):
        args.append(f'{name}=path_params.get("{name}", "1")')
    return f"{function_name}({', '.join(args)})"


def _bootstrap_create_endpoint(
    scenario: Scenario,
    resource_endpoints: list[Endpoint],
) -> Endpoint | None:
    scenario_methods = {endpoint.method for endpoint in scenario.endpoints}
    if "post" in scenario_methods:
        return None
    if not any(endpoint.method in {"get", "put", "patch", "delete"} for endpoint in scenario.endpoints):
        return None
    for endpoint in resource_endpoints:
        if endpoint.method == "post":
            return endpoint
    return None


def _template_testcase_code(scenario: Scenario, resource_endpoints: list[Endpoint]) -> str:
    resource = _resource_name(scenario.resource)
    import_names = [_operation_name(ep) for ep in scenario.endpoints]
    bootstrap_endpoint = _bootstrap_create_endpoint(scenario, resource_endpoints)
    if bootstrap_endpoint is not None:
        import_names.append(_operation_name(bootstrap_endpoint))
    imports = ", ".join(dict.fromkeys(import_names))
    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "import uuid",
        "",
        f"from api.{resource}_api import {imports}",
        "from utils.assertions import assert_response_ok, response_json",
        "from utils.data_loader import load_resource_data",
        "",
        "",
        "def _prepare_payload(payload: dict, suffix: str) -> dict:",
        "    out = dict(payload or {})",
        '    if "name" in out and isinstance(out["name"], str):',
        '        out["name"] = f"{out[\'name\']}-{suffix}"',
        '    if "title" in out and isinstance(out["title"], str):',
        '        out["title"] = f"{out[\'title\']}-{suffix}"',
        "    return out",
        "",
        "",
        f"def test_{_snake_case(scenario.name)}(base_url, request_session):",
        f'    resource_data = load_resource_data("{resource}")',
        '    path_params = dict(resource_data.get("path_params") or {})',
        '    create_payload = _prepare_payload(resource_data.get("create_payload") or {}, uuid.uuid4().hex[:6])',
        '    update_payload = _prepare_payload(resource_data.get("update_payload") or {}, uuid.uuid4().hex[:6])',
        "    entity_id = None",
        "",
    ]

    if bootstrap_endpoint is not None:
        lines.append(f"    bootstrap_response = {_call_expression(bootstrap_endpoint)}")
        lines.append(
            f'    assert_response_ok(bootstrap_response, expected={_success_codes(bootstrap_endpoint)!r}, context="{bootstrap_endpoint.method.upper()} {bootstrap_endpoint.path} (bootstrap)")'
        )
        lines.append("    created = response_json(bootstrap_response)")
        lines.append('    entity_id = created.get("id") or entity_id or "1"')
        lines.append("    for key in list(path_params):")
        lines.append("        if key.lower().endswith('id'):")
        lines.append("            path_params[key] = entity_id")
        lines.append("    assert entity_id is not None")
        lines.append("")

    for index, endpoint in enumerate(scenario.endpoints, start=1):
        response_var = f"response_{index}"
        lines.append(f"    {response_var} = {_call_expression(endpoint)}")
        lines.append(
            f'    assert_response_ok({response_var}, expected={_success_codes(endpoint)!r}, context="{endpoint.method.upper()} {endpoint.path}")'
        )

        if endpoint.method == "post":
            lines.append(f"    created = response_json({response_var})")
            lines.append('    entity_id = created.get("id") or entity_id or "1"')
            for name in _path_parameters(endpoint):
                lines.append(f'    path_params["{name}"] = entity_id')
            if not _path_parameters(endpoint):
                lines.append("    for key in list(path_params):")
                lines.append("        if key.lower().endswith('id'):")
                lines.append("            path_params[key] = entity_id")
            lines.append("    assert entity_id is not None")
        elif endpoint.method in {"get", "put", "patch"}:
            lines.append(f"    payload = response_json({response_var})")
            lines.append("    if isinstance(payload, dict) and entity_id is not None:")
            lines.append("        if 'id' in payload:")
            lines.append("            assert str(payload['id']) == str(entity_id)")
        elif endpoint.method == "delete":
            lines.append("    if entity_id is not None:")
            lines.append("        for key in list(path_params):")
            lines.append("            if key.lower().endswith('id'):")
            lines.append("                path_params[key] = entity_id")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _llm_generate_testcase(settings: Settings, scenario: Scenario) -> str:
    llm = build_chat_llm(settings.model)
    if llm is None:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法使用 LLM 生成")
    resource = _resource_name(scenario.resource)
    api_functions = [_operation_name(endpoint) for endpoint in scenario.endpoints]
    prompt = generation_prompt(
        settings.base_url,
        scenario,
        resource_key=resource,
        api_module=f"api.{resource}_api",
        api_functions=api_functions,
        data_file=f"data/{resource}.yaml",
    )
    msg = llm.invoke(prompt)
    code = _extract_code(str(getattr(msg, "content", msg)))
    if f"def test_{_snake_case(scenario.name)}" not in code:
        raise ValueError("LLM 生成结果缺少预期测试函数")
    return code


def _write_resource_files(output_dir: Path, resource: str, endpoints: list[Endpoint]) -> None:
    resource_name = _resource_name(resource)
    _write_file(output_dir / "api" / f"{resource_name}_api.py", _api_module_code(resource_name, endpoints))
    seed_data = _resource_seed_data(resource_name, endpoints)
    yaml_text = yaml.safe_dump(seed_data, allow_unicode=True, sort_keys=False)
    _write_file(output_dir / "data" / f"{resource_name}.yaml", yaml_text)


def _group_endpoints_by_resource(scenarios: list[Scenario]) -> dict[str, list[Endpoint]]:
    grouped: dict[str, list[Endpoint]] = {}
    for scenario in scenarios:
        for endpoint in scenario.endpoints:
            bucket = grouped.setdefault(scenario.resource, [])
            if endpoint not in bucket:
                bucket.append(endpoint)
    return grouped


def generate_pytest_project(settings: Settings, scenarios: list[Scenario], output_dir: str | Path) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _clean_previous_generated_tests(output_dir)
    _scaffold_files(output_dir, settings)

    for resource, endpoints in _group_endpoints_by_resource(scenarios).items():
        _write_resource_files(output_dir, resource, endpoints)

    generated_files: list[Path] = []
    llm = build_chat_llm(settings.model)
    grouped_endpoints = _group_endpoints_by_resource(scenarios)
    for scenario in scenarios:
        file_path = output_dir / "testcases" / f"test_{_snake_case(scenario.name)}.py"
        resource_endpoints = grouped_endpoints.get(scenario.resource, scenario.endpoints)
        if llm is None:
            code = _template_testcase_code(scenario, resource_endpoints)
        else:
            try:
                code = _llm_generate_testcase(settings, scenario)
            except Exception:
                code = _template_testcase_code(scenario, resource_endpoints)
        _write_file(file_path, code)
        generated_files.append(file_path)
    return generated_files
