from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

from ...core.utils import SandboxViolationError


@dataclass(frozen=True)
class SandboxConfig:
    writable_roots: tuple[str, ...] = ()
    allow_network: bool = False
    network_allowlist: tuple[str, ...] = ()
    timeout_seconds: int | None = None
    memory_limit_mb: int | None = None
    cpu_limit: int | None = None

    def resolved_writable_roots(self) -> tuple[Path, ...]:
        return tuple(Path(root).resolve() for root in self.writable_roots if root)

    @classmethod
    def from_policy_file(
        cls,
        policy_path: str | Path,
        *,
        writable_roots: tuple[str, ...] = (),
    ) -> "SandboxConfig":
        policy_file = Path(policy_path)
        raw = yaml.safe_load(policy_file.read_text(encoding="utf-8")) or {}
        network = raw.get("network", {}) or {}
        resources = raw.get("resources", {}) or {}
        allowlist = tuple(str(host).strip().lower() for host in (network.get("allowlist", []) or []) if host)
        return cls(
            writable_roots=writable_roots,
            allow_network=bool(network.get("allow_all", False)),
            network_allowlist=allowlist,
            timeout_seconds=int(resources["timeout_seconds"]) if resources.get("timeout_seconds") else None,
            memory_limit_mb=int(resources["memory_limit_mb"]) if resources.get("memory_limit_mb") else None,
            cpu_limit=int(resources["cpu_limit"]) if resources.get("cpu_limit") else None,
        )


class BaseSandbox(ABC):
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config

    def build_env(self, base_env: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(base_env or os.environ)
        env["SANDBOX"] = "1"
        env["API_TEST_AGENT_SANDBOX_KIND"] = self.kind
        env["API_TEST_AGENT_SANDBOX_NETWORK"] = "1" if self.config.allow_network else "0"
        env["API_TEST_AGENT_SANDBOX_NETWORK_ALLOWLIST"] = ",".join(self.config.network_allowlist)
        env["API_TEST_AGENT_SANDBOX_WRITABLE_ROOTS"] = os.pathsep.join(
            str(root) for root in self.config.resolved_writable_roots()
        )
        return env

    @property
    @abstractmethod
    def kind(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def validate_write_path(self, target: str | Path) -> Path:
        raise NotImplementedError

    @abstractmethod
    def validate_network_target(self, target: str) -> str:
        raise NotImplementedError

    def validate_runtime(self) -> None:
        return None


class HostSandbox(BaseSandbox):
    @property
    def kind(self) -> str:
        return "host"

    def validate_write_path(self, target: str | Path) -> Path:
        target_path = Path(target).resolve()
        writable_roots = self.config.resolved_writable_roots()
        if not writable_roots:
            return target_path
        for root in writable_roots:
            try:
                target_path.relative_to(root)
                return target_path
            except ValueError:
                continue
        raise SandboxViolationError(
            f"目标路径不在白名单目录内：{target_path}",
            user_hint="请仅将生成结果、报告和临时文件写入 output 目录下的任务子目录。",
            details={
                "target_path": str(target_path),
                "writable_roots": [str(root) for root in writable_roots],
            },
        )

    def validate_network_target(self, target: str) -> str:
        raw = target.strip().lower()
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        host = (parsed.hostname or raw).strip().lower()
        if self.config.allow_network or host in self.config.network_allowlist:
            return host
        raise SandboxViolationError(
            f"目标网络地址不在沙箱白名单内：{host}",
            user_hint="当前首发版默认关闭外网访问；如需放行，请将目标域名加入 sandbox policy allowlist。",
            details={
                "target_host": host,
                "network_allowlist": list(self.config.network_allowlist),
                "allow_all_network": self.config.allow_network,
            },
        )
