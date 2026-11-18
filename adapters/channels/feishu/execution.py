"""通道执行面：把「这条消息交给谁跑」接到 engine 的 Executor 抽象。

旧实现直接 POST 已删除的 travel HTTP API（`serve.url` + `KAI_TRAVEL_TOKEN`），
现在统一走 `engine/coding/executor.py` 的三个执行器：

  native    —— 交宿主原生子代理（只交卡，不 spawn）
  host-cmd  —— 宿主自己的命令腿（OpenBot 用 kai-run.ps1；配置里给 host_cmd）
  message   —— 交消息面（只交卡，不发送）

绑定只写配置，不写死宿主：`feishu.json` 的 `executor.kind` / `executor.host_cmd`，
或环境变量 `KAI_FEISHU_EXECUTOR` / `KAI_FEISHU_HOST_CMD` 覆盖。缺 host_cmd 时
HostCommandExecutor 如实返回 `_needs_subagent`，桥把它当作「未接线」上报，不假装已跑。

gate / stop 这类运行控制不是 Executor 协议的一部分：执行器没提供就如实说「未接线」，
不再偷偷回落到已删除的 HTTP 服务。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:              # 仓根入路径：adapters/ 不是常规包，按脚本跑也能导入
    sys.path.insert(0, str(_REPO))

from engine.coding.executor import Executor, get_executor  # noqa: E402


def pick_executor(cfg: dict[str, Any]):
    """按配置取执行器；未知 kind 直接报错，不猜默认。"""
    ec = cfg.get("executor") or {}
    kind = str(os.environ.get("KAI_FEISHU_EXECUTOR") or ec.get("kind") or "host-cmd").strip()
    host_cmd = str(os.environ.get("KAI_FEISHU_HOST_CMD") or ec.get("host_cmd") or "").strip()
    return get_executor(kind, host_cmd)


def run_card(executor: Executor, card: dict[str, Any]) -> dict[str, Any]:
    """执行一张卡，并把「宿主命令只有 stdout、没写 report.json」收敛成答案。

    OpenBot 的 kai-run.ps1 只回文本，不写执行内核的 report 文件；这不是失败，
    把 stdout 当答案返回，避免把一次成功的执行误报成「缺 report」。
    """
    report = executor.run(card)
    if not isinstance(report, dict):
        return {"answer": str(report or ""), "result": "done"}
    err = str(report.get("_error") or "")
    out = str(report.get("_stdout") or "").strip()
    if err and out and "did not write report" in err:
        return {"answer": out, "result": "done", "notes": "", "_stdout": out}
    return report


def serve(executor: Executor, path: str, body: dict[str, Any]) -> "tuple[bool, str]":
    """运行控制面：能接就接，接不了就明说未接线。

    旧 travel API 的 `/api/runs/<id>/gate|stop` 不再存在；执行器若自带同名方法
    （自定义执行器可提供），就调用它；否则返回失败原因，让回执里看得见。
    """
    action = path.rstrip("/").rsplit("/", 1)[-1]
    fn = getattr(executor, action, None)
    if callable(fn):
        try:
            out = fn((body or {}).get("run_id"), body or {}) if action == "stop" else fn(body or {})
        except Exception as e:                        # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"
        if isinstance(out, tuple) and len(out) == 2:
            return bool(out[0]), str(out[1])
        return True, "ok"
    return False, (f"未接线：执行器 `{getattr(executor, 'name', '?')}` 不提供 {action} 接口"
                   "（旧 travel 服务已删除；需要 gate/stop 时由宿主执行器实现同名方法）")


def parse_report(text: str) -> dict[str, Any]:
    """执行器输出 → 报告字典。非 JSON 也保留原文，不丢结果。"""
    import json

    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {"notes": "report not parseable; read diff", "raw": raw[-2000:]}
    return data if isinstance(data, dict) else {"raw": raw[-2000:]}


def usage_tokens(report: dict[str, Any]) -> int:
    usage = report.get("usage") or {}
    total = 0
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens"):
        try:
            total += int(usage.get(k) or 0)
        except Exception:
            continue
    return total
