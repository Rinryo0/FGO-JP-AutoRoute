"""Optional MaaFramework bridge.

The desktop app can import this module without MaaFramework installed.  This
first integration step deliberately initializes a Resource/Tasker against an
already-created controller but does not dispatch game actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MaaRuntimeStatus:
    available: bool
    initialized: bool
    message: str


class MaaFrameworkAdapter:
    """Lazy, optional MaaFramework integration boundary.

    The caller owns the device/controller lifecycle.  This adapter only binds
    that controller to a MaaFramework Resource and Tasker.  Task execution is
    intentionally not exposed until the screen-state bridge and safety gate
    have been implemented and tested.
    """

    def __init__(self) -> None:
        self._resource: Any | None = None
        self._tasker: Any | None = None
        self._controller: Any | None = None
        self._status = MaaRuntimeStatus(
            available=self.is_available(),
            initialized=False,
            message="MaaFramework 尚未初始化",
        )

    @staticmethod
    def is_available() -> bool:
        """Return whether the MaaFramework Python binding can be imported."""
        try:
            from importlib.util import find_spec

            return find_spec("maa") is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    @property
    def status(self) -> MaaRuntimeStatus:
        return self._status

    def initialize(self, controller: Any, resource_path: str | Path) -> MaaRuntimeStatus:
        """Load a Maa resource bundle and bind an existing controller.

        No task is started and no input is sent to the device.
        """
        if controller is None:
            self._status = MaaRuntimeStatus(
                available=self.is_available(),
                initialized=False,
                message="尚未提供裝置控制器",
            )
            return self._status

        bundle_path = Path(resource_path).expanduser()
        if not bundle_path.is_dir():
            self._status = MaaRuntimeStatus(
                available=self.is_available(),
                initialized=False,
                message=f"找不到 Maa 資源資料夾：{bundle_path}",
            )
            return self._status

        try:
            from maa.resource import Resource
            from maa.tasker import Tasker

            resource = Resource()
            resource.post_bundle(str(bundle_path)).wait()

            tasker = Tasker()
            tasker.bind(resource, controller)
            if not tasker.inited:
                raise RuntimeError("MaaFramework Tasker 初始化失敗")

            self._resource = resource
            self._tasker = tasker
            self._controller = controller
            self._status = MaaRuntimeStatus(
                available=True,
                initialized=True,
                message="MaaFramework 已就緒（尚未啟用任務執行）",
            )
        except Exception as exc:  # optional runtime must not crash the desktop UI
            self.close()
            self._status = MaaRuntimeStatus(
                available=self.is_available(),
                initialized=False,
                message=f"MaaFramework 初始化失敗：{type(exc).__name__}: {exc}",
            )

        return self._status

    def close(self) -> None:
        """Release Python references; the caller remains owner of controller."""
        self._tasker = None
        self._resource = None
        self._controller = None
        if not self._status.initialized:
            return
        self._status = MaaRuntimeStatus(
            available=True,
            initialized=False,
            message="MaaFramework 已關閉",
        )
