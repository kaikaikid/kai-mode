"""角色实例的入口归属：本宿主自己的口可以拉，别家的不可以。

裁决：docs/adr/0033-guild-role-layer.md D3。
一句话判据：**角色实例的入口必须属于当前宿主**。在 A 宿主里拉 B 宿主的一次性进程属于
跨宿主借兵、消耗别家额度，机械拦。

**内核不写宿主名**（engine/tests/test_purity.py 守着这条）。宿主→程序名的映射是
宿主差异数据，唯一家是 `adapters/role-hosts.json`；装机时导出成项目侧的
`.coding/host-programs.json`，内核只读这份数据。没有这份数据 ⇒ 归不了属，
如实回报 `unverified`，不静默当已核。

三种裁决：
- ``ok``         程序属于当前宿主，或不在映射表里（工具类命令，归不了属）。
- ``block``      程序属于**另一个**已知宿主 ⇒ 抛 ``CrossHostError``，不执行。
- ``unverified`` 不知道当前宿主，或没有映射表 ⇒ 放行但如实回报。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

OK, BLOCK, UNVERIFIED = "ok", "block", "unverified"
TABLE_REL = ("host-programs.json",)  # 住在 .coding/ 下


class CrossHostError(RuntimeError):
    """角色实例的入口不属于当前宿主。"""


def program_of(host_cmd: str) -> str:
    """从命令行里取程序名（去目录、去 .exe/.cmd/.bat 后缀、小写）。"""
    first = (host_cmd or "").strip().split()[0] if (host_cmd or "").strip() else ""
    base = first.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base


def load_table(root: Path | str) -> dict[str, frozenset[str]]:
    """读 ``<root>/.coding/host-programs.json``：{宿主: [程序名, ...]}。没有就返回空表。"""
    p = Path(root) / ".coding" / TABLE_REL[0]
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
    out: dict[str, frozenset[str]] = {}
    for host, progs in (data.items() if isinstance(data, dict) else []):
        if isinstance(progs, str):
            progs = [progs]
        try:
            out[str(host).strip().lower()] = frozenset(
                str(x).strip().lower() for x in progs if str(x).strip())
        except TypeError:
            continue
    return out


def owner_of(program: str, table: dict[str, frozenset[str]]) -> str | None:
    prog = (program or "").lower()
    if not prog:
        return None
    for host, progs in table.items():
        if prog in progs:
            return host
    return None


def current_host(root: Path | str) -> str:
    """当前宿主：项目配置实例的 ``host`` 优先，其次环境变量 ``KAI_HOST``。读不到返回空串。"""
    p = Path(root) / ".coding" / "config.json"
    if p.is_file():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            cfg = {}
        val = str(cfg.get("host") or "").strip().lower()
        if val:
            return val
    return os.environ.get("KAI_HOST", "").strip().lower()


def check(host_cmd: str, host: str, table: dict[str, frozenset[str]]) -> tuple[str, str]:
    """返回 (裁决, 人话理由)。不抛异常，便于回执登记。"""
    prog = program_of(host_cmd)
    if not prog:
        return OK, "空命令，无从归属"
    if not table:
        return UNVERIFIED, ("没有 .coding/host-programs.json（宿主→程序名映射未装），"
                            "无法核对；放行但记 host-unverified")
    owner = owner_of(prog, table)
    if owner is None:
        return OK, f"`{prog}` 不在宿主映射表里，归不了属，不按跨宿主处理"
    if not host:
        return UNVERIFIED, ("不知道当前宿主（项目配置实例的 host 与环境变量 KAI_HOST 都没写），"
                            f"无法核对 `{prog}` 是否属于本宿主；放行但记 host-unverified")
    if owner == host:
        return OK, f"`{prog}` 属于当前宿主 {host}"
    return BLOCK, (f"跨宿主借兵：当前宿主是 {host}，却在拉 {owner} 的 `{prog}`。"
                   f"角色实例的入口必须属于当前宿主（ADR-0033 D3）；"
                   f"要换宿主就在那个宿主里起会话，别在这里拉别家的 CLI。")


def assert_own_host(host_cmd: str, host: str, table: dict[str, frozenset[str]]) -> None:
    verdict, why = check(host_cmd, host, table)
    if verdict == BLOCK:
        raise CrossHostError(why)


def receipt(host_cmd: str, host: str, table: dict[str, frozenset[str]]) -> dict:
    """机器可读回执：装机与派工都留这一行。"""
    prog = program_of(host_cmd)
    verdict, why = check(host_cmd, host, table)
    return {
        "host": host or "",
        "program": prog,
        "owner": owner_of(prog, table) or "",
        "verdict": verdict,
        "reason": why,
    }