from __future__ import annotations

from pathlib import Path

from ...core.utils import DockerNotAvailableError, SandboxViolationError
from .host_executor import BaseSandbox, SandboxConfig


class DockerSandbox(BaseSandbox):
    def __init__(self, config: SandboxConfig, client: object) -> None:
        super().__init__(config)
        self.client = client

    @property
    def kind(self) -> str:
        return "docker"

    @classmethod
    def create(cls, config: SandboxConfig) -> "DockerSandbox":
        try:
            import docker  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - import branch via tests
            raise DockerNotAvailableError(
                "当前环境未安装 docker SDK，无法启用 docker 沙箱。",
                user_hint="请先安装 `docker` Python 包，并确保本机 Docker Desktop / daemon 正常运行；否则请改用 host 沙箱。",
                details={"missing_dependency": "docker"},
            ) from exc
        try:
            client = docker.from_env()
        except Exception as exc:  # pragma: no cover - runtime branch via tests
            raise DockerNotAvailableError(
                "当前环境无法连接 Docker daemon，无法启用 docker 沙箱。",
                user_hint="请确认 Docker 已启动，或暂时使用 host 沙箱。",
                details={"error_type": type(exc).__name__},
            ) from exc
        return cls(config, client)

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
            f"目标路径不在 docker 沙箱白名单目录内：{target_path}",
            user_hint="请仅将生成结果、报告和临时文件写入 output 目录下的任务子目录。",
            details={
                "target_path": str(target_path),
                "writable_roots": [str(root) for root in writable_roots],
            },
        )

    def validate_network_target(self, target: str) -> str:
        return target.strip().lower()

    def validate_runtime(self) -> None:
        if self.client is None:
            raise DockerNotAvailableError(
                "DockerSandbox 尚未初始化完成。",
                user_hint="请确认 Docker 已启动，或暂时改用 host 沙箱。",
                details={},
            )
