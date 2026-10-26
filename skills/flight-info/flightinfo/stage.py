# -*- coding: utf-8 -*-
"""阶段判据：把「证据包」判成阶段。

判据是**配置**（board.config.json 的 stage_rules），不是代码。
本模块只负责解释判据、按配置顺序取第一条命中的规则。

证据包（dict）约定：
    closed        bool        票已关
    labels        list[str]   票的标签
    last_comment  str         最新一条评论正文
    branches      list[str]   匹配到的分支名
    table_note    str         日表里的备注
    assignee      str         指派对象
    url           str         票面链接（空＝只有分支、GitHub 上认不到这张票）
"""
from __future__ import annotations

import re
from datetime import datetime

WHEN_KINDS = (
    "state_closed", "label_equals", "comment_contains",
    "branch_exists", "table_note_contains", "assignee_exists",
    "no_issue", "else",
)

STALE_KEY = "_to"          # stale_after 里保留键：降级成哪个阶段（默认 stale）
DEFAULT_STALE_TO = "stale"


def dwell_days(updated_at: str | None, now: datetime | None = None) -> int | None:
    """距上次更新几天。认三种写法：带时区 ISO、不带时区 ISO、纯日期。

    解析不出来返回 None（＝不知道，绝不猜成 0 天——猜 0 就是把停滞看成活跃）。
    """
    if not updated_at:
        return None
    s = str(updated_at).strip().replace("T", " ")[:19]
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(s if len(s) > 10 else updated_at[:10], fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    base = now or datetime.now().astimezone()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=base.tzinfo)
    return max(0, (base - parsed).days)


def apply_stale(stage_key: str, why: str, updated_at: str | None,
                stale_after: dict | None, now: datetime | None = None):
    """按阶段分档把「在飞／审查／待发货…」降级成停滞。

    返回 (stage, why, prev_stage, days)。阈值按阶段给，是因为各阶段的"正常等待时长"
    本来就不同：待发货压一天就该喊，排队一周不动才是常态。
    """
    if not stale_after or stage_key in ("closed", "undefined"):
        return stage_key, why, "", None
    limit = stale_after.get(stage_key)
    if limit is None:
        return stage_key, why, "", None
    days = dwell_days(updated_at, now)
    if days is None or days < int(limit):
        return stage_key, why, "", days
    to = stale_after.get(STALE_KEY) or DEFAULT_STALE_TO
    if stage_key == to:
        return stage_key, why, "", days
    label = {"flying": "在飞", "review": "审查", "to_ship": "待发货",
             "queued": "排队", "ready": "可领", "hold": "挡住"}.get(stage_key, stage_key)
    return to, f"{why} · 原{label} {days} 天没动", stage_key, days


def validate_rules(rules: list[dict]) -> list[str]:
    """返回问题清单（空＝通过）。最后一条必须是 else。"""
    problems = []
    if not rules:
        return ["stage_rules 为空（至少要有 {when:else} 兜底）"]
    for i, r in enumerate(rules):
        w = (r or {}).get("when")
        if w not in WHEN_KINDS:
            problems.append(f"stage_rules[{i}]：未知 when={w!r}（只许 {'/'.join(WHEN_KINDS)}）")
            continue
        if w != "else" and not r.get("stage"):
            problems.append(f"stage_rules[{i}]：缺 stage")
        if w in ("label_equals", "comment_contains", "table_note_contains") and not r.get("value"):
            problems.append(f"stage_rules[{i}]：{w} 需要 value")
    if rules[-1].get("when") != "else":
        problems.append("stage_rules 最后一条必须是 {when:'else'}（兜底）")
    return problems


def _hit(rule: dict, ev: dict) -> tuple[bool, str]:
    """命中返回 (True, why)。why 支持 {branch}/{note}/{assignee}/{label} 占位。"""
    when = rule.get("when")
    val = rule.get("value")
    why = rule.get("why") or ""

    if when == "state_closed":
        return bool(ev.get("closed")), why

    if when == "label_equals":
        labels = ev.get("labels") or []
        return (val in labels), why.replace("{label}", str(val))

    if when == "comment_contains":
        text = ev.get("last_comment") or ""
        flags = re.IGNORECASE if rule.get("ignore_case") else 0
        try:
            return bool(re.search(val or "", text, flags)), why
        except re.error:
            return (val or "") in text, why

    if when == "branch_exists":
        br = (ev.get("branches") or [None])[0]
        return bool(br), why.replace("{branch}", str(br))

    if when == "table_note_contains":
        note = ev.get("table_note") or ""
        try:
            return bool(re.search(val or "", note)), why.replace("{note}", note)
        except re.error:
            return (val or "") in note, why

    if when == "assignee_exists":
        who = ev.get("assignee")
        return bool(who), why.replace("{assignee}", str(who))

    if when == "no_issue":
        # 有分支、却没取到票面（无 url）＝残留分支，不该冒充在飞的航班
        branches = ev.get("branches") or []
        hit = bool(branches) and not (ev.get("url") or "")
        br = branches[0] if branches else ""
        return hit, why.replace("{branch}", str(br))

    return False, why


def decide(rules: list[dict], ev: dict) -> tuple[str, str]:
    """按配置顺序判阶段。永不抛异常：判不出来返回 ('', '')，由调用方标「未定」。"""
    for rule in rules or []:
        when = rule.get("when")
        if when == "else":
            why = (rule.get("why") or "").replace(
                "{note}", str(ev.get("table_note") or ""))
            return rule.get("stage") or "", why
        ok, why = _hit(rule, ev)
        if ok:
            return rule.get("stage") or "", why
    return "", ""


def stage_chain(stages: list[dict]) -> str:
    """「排队 → 在飞 → 审查 → 待发货 → 已收尾」。"""
    return " → ".join(s.get("label") or s.get("key") or "" for s in stages or [])
