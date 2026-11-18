"""唤醒：一条消息 → 一次执行器调用（可续接），带预算与超时。

旧实现走已删除的 travel 宿主适配器；现在统一走 `engine/coding/executor.py`：
  · host-cmd（默认）——配置里给宿主命令（OpenBot 用 kai-run.ps1），
    `{brief}` 占位符由执行内核替换成整段提示词；
  · native / message —— 只交卡，桥把「未接线」如实回报，不假装已执行。

绑定只写配置：`feishu.json` 的 `executor.kind` / `executor.host_cmd`，
或环境变量 `KAI_FEISHU_EXECUTOR` / `KAI_FEISHU_HOST_CMD`。缺 host_cmd 时
执行器返回 `_needs_subagent`，这里转成「未接线」文本，不静默。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from . import execution


def _answer(text: str, report: dict[str, Any]) -> str:
    notes = str(report.get("notes") or "")
    if notes and notes != "report not parseable; read diff" and "not parseable" not in notes:
        return str(report.get("answer") or report.get("summary") or notes)
    return (text or "").strip()


def _chat_prompt(brief: str, cwd: str, timeout_s: int) -> str:
    """飞书对话腿只送用户原话，绝不让内核的施工卡泄漏给值守 agent。"""
    return (
        "这是飞书用户发来的一句话。你是值守前台：只回答这句话，等康娜必要时再转接。\n"
        "不要写 report.json，不要解释 touchset／report_path，不要回内部任务卡。\n"
        f"工作目录：{cwd}\n超时秒数：{timeout_s}\n\n"
        f"用户原话：\n{brief}\n"
    )


def make_wake(cfg: dict[str, Any], root: "Path | str", spawn=None, wait=None, read=None):
    """返回 wake(brief, cwd, resume) -> {text, session_id, tokens, adapter, rc}。

    spawn/wait/read 可注入（测试用）；默认真实走 engine 的 Executor。
    """
    wake_cfg = cfg.get("wake") or {}
    root = Path(root)

    def wake(brief: str, cwd: str, resume: "str | None" = None) -> dict[str, Any]:
        if spawn is not None:
            handle = spawn(brief, cwd, resume)
            rc, text = wait(handle), read(handle)
            adapter_name = str(handle.get("adapter") or "injected")
            report: dict[str, Any] = execution.parse_report(text)
        else:
            executor = execution.pick_executor(cfg)
            sid = f"wake-{int(time.time() * 1000)}"
            sdir = root / ".coding" / "feishu" / "wake" / sid
            sdir.mkdir(parents=True, exist_ok=True)
            card = {
                "brief": brief,
                "prompt": _chat_prompt(brief, str(cwd), int(wake_cfg.get("timeout_s") or 600)),
                "worktree": str(cwd),
                "report_path": str(sdir / "report.json"),
                "session_id": resume or "",
                "tier": str(wake_cfg.get("tier") or "light"),
                "timeout_s": int(wake_cfg.get("timeout_s") or 600),
                "read_only": True,
            }
            try:
                report = execution.run_card(executor, card)
            except Exception as e:                        # noqa: BLE001
                report = {"_error": f"{type(e).__name__}: {e}"}
            adapter_name = getattr(executor, "name", "executor")
            text = str(report.get("answer") or report.get("summary")
                       or report.get("notes") or report.get("raw") or "")
            if report.get("_needs_subagent") or report.get("_needs_message"):
                text = ("未接线：当前执行器只交卡、不执行。"
                        "在 feishu.json 配 `executor.host_cmd`（宿主自己的命令腿）后重试。")
                rc = 2
            elif report.get("_error"):
                text = f"执行失败：{report['_error']}"
                rc = 1
            else:
                rc = 0

        session_id = str(report.get("session_id") or resume or "")
        tokens = execution.usage_tokens(report)
        limit = int(wake_cfg.get("max_tokens") or 0)
        return {"text": _answer(text, report), "session_id": session_id,
                "tokens": tokens, "adapter": adapter_name, "rc": rc,
                "over_budget": bool(limit and tokens > limit)}

    return wake
