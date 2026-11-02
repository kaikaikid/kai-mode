"""卡片渲染：全部确定性模板，不交给 AI 写。"""

from __future__ import annotations

from typing import Any

PHASE_CN = {
    "queued": "排队", "planning": "规划", "design": "设计", "delegating": "施工",
    "reviewing": "审查", "closing": "待发货", "done": "完成", "blocked": "卡住",
    "cancelled": "已取消", "failed": "失败",
}


def _md(text: str) -> dict[str, Any]:
    return {"tag": "div", "text": {"tag": "lark_md", "content": text}}


def _btn(label: str, value: dict[str, Any], kind: str = "default") -> dict[str, Any]:
    return {"tag": "button", "text": {"tag": "plain_text", "content": label},
            "type": kind, "value": value}


def card(title: str, body: str, buttons: "list[dict[str, Any]] | None" = None,
         template: str = "blue") -> dict[str, Any]:
    elements: list[dict[str, Any]] = [_md(body)]
    if buttons:
        elements.append({"tag": "action", "actions": buttons})
    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": {"template": template, "title": {"tag": "plain_text", "content": title}},
        "elements": elements,
    }


def board(rows: "list[dict[str, Any]]", title: str = "任务看板") -> dict[str, Any]:
    if not rows:
        return card(title, "现在没有在飞的任务。", template="grey")
    lines = ["| 任务 | 阶段 | 进度 | 下一步 |", "|---|---|---|---|"]
    for r in rows[:10]:
        phase = PHASE_CN.get(str(r.get("phase")), str(r.get("phase") or "—"))
        lines.append(f"| `{r.get('run_id', '—')}` | {phase} | {r.get('progress', '—')} | "
                     f"{str(r.get('next_action') or '—')[:40]} |")
    more = f"\n\n还有 {len(rows) - 10} 个未显示。" if len(rows) > 10 else ""
    return card(title, "\n".join(lines) + more)


def gate_request(run_id: str, gate: str, summary: str, nonce: str,
                 reminder: bool = False) -> dict[str, Any]:
    title = f"还在等你拍板 · {gate.upper()}" if reminder else f"等你拍板 · {gate.upper()}"
    return card(
        title,
        f"**run** `{run_id}`\n\n{summary}",
        buttons=[
            _btn("批准", {"kind": "gate", "run_id": run_id, "gate": gate,
                         "decision": "approve", "nonce": nonce}, "primary"),
            _btn("打回", {"kind": "gate", "run_id": run_id, "gate": gate,
                         "decision": "reject", "nonce": nonce}, "danger"),
        ],
        template="orange")


def ship_confirm(run_id: str, nonce: str) -> dict[str, Any]:
    return card(
        "确认发货？",
        f"run `{run_id}` 已通过验收。点「确认发货」才会 merge → push → 关票。",
        buttons=[
            _btn("确认发货", {"kind": "gate", "run_id": run_id, "gate": "g2",
                             "decision": "approve", "nonce": nonce}, "primary"),
            _btn("稍后", {"kind": "noop", "nonce": f"{nonce}-later"}),
        ],
        template="red")


def done(run_id: str, commit: str = "", tasks: int = 0) -> dict[str, Any]:
    body = f"`{run_id}` 已完成。"
    if commit:
        body += f"\n\ncommit `{commit}`"
    if tasks:
        body += f"　·　{tasks} 个任务通过验收"
    return card("完成", body, template="green")


def blocked(run_id: str, why: str) -> dict[str, Any]:
    return card("卡住了", f"`{run_id}`\n\n{why or '（没有给出原因）'}", template="red")


def text(title: str, body: str) -> dict[str, Any]:
    return card(title, body, template="grey")
