"""分诊：一句话 → 确定性动作 or 唤醒一次 AI。

规则先于模型：能脚本判定的绝不叫醒 AI（省 token，也少幻觉）。
"""

from __future__ import annotations

import re
from typing import Any

RUN_ID = r"([A-Za-z0-9][A-Za-z0-9._-]{0,63})"
GATE = r"(g[012])"

_CMD = re.compile(
    r"^(?P<verb>新话题|重开|reset|new|"
    r"记住|remember|"
    r"状态|进度|status|"
    r"看板|board|"
    r"想法|idea|"
    r"票|开票|ticket|"
    r"曲速|warp|跃迁|jump|"
    r"批|同意|approve|拒|驳回|reject|"
    r"确认发货|发货|ship|"
    r"停|停止|stop)"
    r"(?:\s+(?P<rest>.*))?$", re.S | re.I)


def _gate_args(rest: str) -> dict[str, Any]:
    m = re.match(rf"^{GATE}\s+{RUN_ID}\s*$", rest or "", re.I)
    if m:
        return {"gate": m.group(1).lower(), "run_id": m.group(2)}
    m = re.match(rf"^{RUN_ID}\s*$", rest or "")
    if m:
        return {"gate": "", "run_id": m.group(1)}
    return {}


def decide(text: str) -> dict[str, Any]:
    """返回 {kind, needs_ai, args, text}。认不出就当对话处理。"""
    raw = (text or "").strip()
    m = _CMD.match(raw)
    if not m:
        return {"kind": "chat", "needs_ai": True, "args": {}, "text": raw}

    verb = m.group("verb").lower()
    rest = (m.group("rest") or "").strip()
    out: dict[str, Any] = {"kind": "chat", "needs_ai": True, "args": {}, "text": raw}

    if verb in {"新话题", "重开", "reset", "new"}:
        out.update(kind="new_topic", needs_ai=False, args={"carry": rest})
    elif verb in {"记住", "remember"}:
        out.update(kind="remember", needs_ai=False, args={"note": rest})
    elif verb in {"状态", "进度", "status"}:
        out.update(kind="status", needs_ai=False, args={"run_id": rest})
    elif verb in {"看板", "board"}:
        out.update(kind="board", needs_ai=False, args={})
    elif verb in {"想法", "idea"}:
        out.update(kind="idea", needs_ai=False, args={"text": rest})
    elif verb in {"票", "开票", "ticket"}:
        out.update(kind="ticket", needs_ai=True, args={"text": rest})
    elif verb in {"曲速", "warp", "跃迁", "jump"}:
        urgent = verb in {"跃迁", "jump"}
        out.update(kind="run", needs_ai=True, args={"urgent": urgent, "text": rest})
    elif verb in {"批", "同意", "approve", "拒", "驳回", "reject"}:
        decision = "approve" if verb in {"批", "同意", "approve"} else "reject"
        args = _gate_args(rest)
        out.update(kind="gate", needs_ai=False,
                   args={**args, "decision": decision, "gate": args.get("gate") or "g2"})
    elif verb in {"发货", "ship"}:
        args = _gate_args(rest)
        out.update(kind="ship_confirm", needs_ai=False,
                   args={"run_id": args.get("run_id", ""), "gate": "g2"})
    elif verb in {"确认发货"}:
        args = _gate_args(rest)
        out.update(kind="gate", needs_ai=False,
                   args={"run_id": args.get("run_id", ""), "gate": "g2", "decision": "approve"})
    elif verb in {"停", "停止", "stop"}:
        out.update(kind="stop", needs_ai=False, args={"run_id": rest})
    return out


def six_pieces(text: str) -> dict[str, bool]:
    """开票六件套的粗判（只做提示，不替人做决定）。"""
    t = text or ""
    return {
        "target": any(k in t for k in ("目标", "做什么", "goal")),
        "ac": any(k in t for k in ("AC", "验收", "acceptance")),
        "allow": any(k in t for k in ("允许",)),
        "deny": any(k in t for k in ("禁止",)),
        "verify": any(k in t for k in ("验证", "测试")),
        "deps": any(k in t for k in ("依赖", "红线")),
    }


def missing_pieces(text: str) -> list[str]:
    return [k for k, ok in six_pieces(text).items() if not ok]
