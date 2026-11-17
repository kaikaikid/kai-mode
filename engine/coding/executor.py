"""执行器抽象（ADR-0035 D6）：把「谁去执行任务卡」从 auto 循环里拆出来。

三种实现，形状都是 `run(card) -> report`：

  · NativeExecutor      —— 交给宿主原生子代理；返回 `_needs_subagent`＋card。
  · HostCommandExecutor —— 复用 `auto._spawn_worker` 的宿主命令腿；返回 report 或 `_error`。
  · MessageExecutor     —— 交给消息面（异步任务卡）；返回 `_needs_message`＋card，**不实际发消息**。

默认选择（`executor=None`）保持旧行为：auto.drive 直接走 `_spawn_worker`，
即「配了宿主命令就跑命令、没配就报子代理缺件」。显式选择时才换成对应执行器。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

EXECUTOR_NAMES = ("native", "host-cmd", "message")


@runtime_checkable
class Executor(Protocol):
    """执行器接口：吃任务卡，吐报告（或如实报缺件）。"""

    name: str

    def run(self, card: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - 协议
        ...


class NativeExecutor:
    """宿主原生子代理：内核不 spawn，只把卡交出去。"""

    name = "native"

    def run(self, card: dict[str, Any]) -> dict[str, Any]:
        return {"_needs_subagent": True, "card": card}


class HostCommandExecutor:
    """宿主命令腿：与 auto 现有 `_spawn_worker` 同一实现，不复制第二份逻辑。"""

    name = "host-cmd"

    def __init__(self, host_cmd: str = "") -> None:
        self.host_cmd = host_cmd or ""

    def run(self, card: dict[str, Any]) -> dict[str, Any]:
        # 局部 import 避开 auto ←→ executor 的模块级环。
        from . import auto

        return auto._spawn_worker(card, self.host_cmd)


class MessageExecutor:
    """消息面执行器：只交卡，不发送。发送由宿主适配器在确认后自己走。"""

    name = "message"

    def run(self, card: dict[str, Any]) -> dict[str, Any]:
        return {"_needs_message": True, "card": card}


def get_executor(name: str, host_cmd: str = "") -> NativeExecutor | HostCommandExecutor | MessageExecutor:
    """按名字取执行器；未知名字直接报错，不猜默认。"""
    key = (name or "").strip()
    if key == "native":
        return NativeExecutor()
    if key == "host-cmd":
        return HostCommandExecutor(host_cmd)
    if key == "message":
        return MessageExecutor()
    raise ValueError(f"unknown executor: {name!r} (expected one of {', '.join(EXECUTOR_NAMES)})")
