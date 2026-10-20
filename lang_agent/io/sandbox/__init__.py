from .docker_executor import DockerSandbox
from .host_executor import BaseSandbox, HostSandbox, SandboxConfig


def build_sandbox(kind: str, config: SandboxConfig) -> BaseSandbox:
    normalized = (kind or "host").strip().lower()
    if normalized == "docker":
        return DockerSandbox.create(config)
    return HostSandbox(config)


__all__ = [
    "BaseSandbox",
    "build_sandbox",
    "DockerSandbox",
    "HostSandbox",
    "SandboxConfig",
]
