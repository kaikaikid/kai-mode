# -*- coding: utf-8 -*-
"""采集编排：跑每个源 → 记账 → 按 uid 合并 → 判阶段 → 落库。

本模块是唯一知道「有哪几个源、怎么合并、判据从哪来」的地方。
源模块不认识彼此，也不认识数据库。
"""
from __future__ import annotations

from . import db, stage
from .sources import collect as collect_source
from .sources import get as get_source

MERGE_FIRST = ("title", "ticket", "assignee", "milestone", "url",
               "owner", "persona", "last_comment", "table_note")

# 掌机归属三源，按「事实优先」排：日表车道 → 票面指派 → 阶段推断。
# 推断只给「塔台独占发货」这类协议事实用，且必须标 owner_from=infer，
# 界面上要能看出这一格是推出来的、不是有人认领的。
DEFAULT_OWNER_INFER = {"to_ship": "tower"}


def ticket_key(value) -> str:
    """'#1711' / '1711' / 'issue:1711' → '1711'（对票号用的是一把尺）。"""
    s = str(value or "").strip()          # 先去空白，再剥 # ——顺序反了 " #12 " 会漏剥
    if ":" in s:
        s = s.rsplit(":", 1)[-1].strip()
    return s.lstrip("#").strip()


def lane_index(schedules: list[dict]) -> dict[str, str]:
    """票号 → 车道。只认**最新那张日表**：历史表里的排班不算今天的归属。"""
    if not schedules:
        return {}
    latest = max((s.get("table_date") or "") for s in schedules)
    idx: dict[str, str] = {}
    for s in schedules:
        if (s.get("table_date") or "") != latest:
            continue
        k = ticket_key(s.get("ticket"))
        if k and k not in idx and s.get("lane"):
            idx[k] = s["lane"]
    return idx


def resolve_owner(rec: dict, lane: str | None, role_labels: dict,
                  infer_map: dict) -> tuple[str, str]:
    """返回 (显示名, 来源标记)。认不到就 ("", "")——空格子比假名字诚实。"""
    for raw, from_ in ((lane, "lane"), (rec.get("owner"), "lane"),
                       (rec.get("assignee"), "assignee"),
                       ((infer_map or {}).get(rec.get("stage")), "infer")):
        if not raw:
            continue
        return (role_labels.get(raw) or raw), from_
    return "", ""


def merge_flights(records: list[dict]) -> dict[str, dict]:
    """同 uid 合并：证据取并集，展示字段取第一个非空。"""
    out: dict[str, dict] = {}
    for r in records:
        uid = r.get("uid")
        if not uid:
            continue
        cur = out.get(uid)
        if cur is None:
            cur = out[uid] = dict(r)
            cur["_sources"] = [r.get("source", "?")]
            cur["labels"] = list(r.get("labels") or [])
            cur["branches"] = list(r.get("branches") or [])
            continue
        cur["_sources"].append(r.get("source", "?"))
        for k in MERGE_FIRST:
            if not cur.get(k) and r.get(k):
                cur[k] = r[k]
        cur["labels"] = sorted(set(cur.get("labels") or []) | set(r.get("labels") or []))
        cur["branches"] = sorted(set(cur.get("branches") or []) | set(r.get("branches") or []))
        cur["closed"] = bool(cur.get("closed")) or bool(r.get("closed"))
        cur["planned"] = bool(cur.get("planned")) or bool(r.get("planned"))
        if (r.get("updated_at") or "") > (cur.get("updated_at") or ""):
            cur["updated_at"] = r["updated_at"]
    return out


def _evidence_kinds(rec: dict) -> list[tuple[str, str]]:
    ev = []
    if rec.get("closed"):
        ev.append(("state", "closed"))
    for lb in rec.get("labels") or []:
        ev.append(("label", lb))
    for br in rec.get("branches") or []:
        ev.append(("branch", br))
    if rec.get("table_note"):
        ev.append(("table_note", rec["table_note"]))
    if rec.get("last_comment"):
        ev.append(("comment", rec["last_comment"][:120]))
    if rec.get("assignee"):
        ev.append(("assignee", rec["assignee"]))
    return ev


def run_sources(config: dict, ctx: dict, conn, run_id: str) -> dict:
    """跑全部源，返回 {"sources": {...}, "flights": n, "schedules": n,
    "handoffs": n}。源除 flights/schedules 外可带 handoffs（非航班形态的记录）。"""
    all_records, all_schedules, all_handoffs, report = [], [], [], {}
    runtime = {"queue": None, "tower": None}

    for sc in config.get("sources") or []:
        sid = sc.get("id") or sc.get("type")
        typ = sc.get("type")
        try:
            get_source(typ)
        except KeyError as e:
            report[sid] = {"status": "fail", "rows": 0, "detail": str(e)}
            db.record_source(conn, run_id, sid, typ or "?", "fail", 0, str(e))
            continue
        try:
            res = collect_source(typ, sc, ctx)
        except Exception as e:                      # 单源炸不拖垮整页
            detail = f"{type(e).__name__}: {e}"
            report[sid] = {"status": "fail", "rows": 0, "detail": detail}
            db.record_source(conn, run_id, sid, typ, "fail", 0, detail)
            continue
        if res.get("queue") is not None:
            runtime["queue"] = res["queue"]
        if res.get("tower") is not None:
            runtime["tower"] = res["tower"]
        flights = res.get("flights") or []
        schedules = res.get("schedules") or []
        handoffs = res.get("handoffs") or []
        status = res.get("status") or "ok"
        detail = res.get("detail") or ""
        all_records.extend(flights)
        all_schedules.extend(schedules)
        all_handoffs.extend(handoffs)
        n_rows = len(flights) + len(schedules) + len(handoffs)
        report[sid] = {"status": status, "rows": n_rows, "detail": detail}
        db.record_source(conn, run_id, sid, typ, status, n_rows, detail)

    db.replace_handoffs(conn, run_id, all_handoffs)

    merged = merge_flights(all_records)
    rules = config.get("stage_rules") or []
    # 阶段名要对得上号：链上阶段与链外阶段（可领／挡住）都算，别让它们掉成「未定」
    labels = {}
    for s in list(config.get("stages") or []) + list(config.get("off_chain_stages") or []):
        labels[s["key"]] = s.get("label") or s["key"]

    role_labels = config.get("role_labels") or {}
    infer_map = config.get("owner_infer") or DEFAULT_OWNER_INFER
    stale_after = config.get("stale_after") or {}
    lanes = lane_index(all_schedules)

    stale_n = 0
    for uid, rec in merged.items():
        ev = {"closed": rec.get("closed"), "labels": rec.get("labels"),
              "last_comment": rec.get("last_comment"), "branches": rec.get("branches"),
              "table_note": rec.get("table_note"), "assignee": rec.get("assignee"),
              "url": rec.get("url")}
        st, why = stage.decide(rules, ev)
        st = st or "undefined"
        # 二道闸：有在飞证据但已经不动了 → 停滞；别让"挂着分支"冒充"有人在敲"
        st, why, prev, days = stage.apply_stale(st, why, rec.get("updated_at"), stale_after)
        if st != prev and prev:
            stale_n += 1
        rec["stage"] = st
        rec["stage_label"] = labels.get(st) or ("未定" if st == "undefined" else st)
        rec["why"] = why
        rec["prev_stage"] = prev or None
        rec["stale_days"] = days
        owner, owner_from = resolve_owner(rec, lanes.get(ticket_key(rec.get("ticket"))),
                                          role_labels, infer_map)
        rec["owner"] = owner
        rec["owner_from"] = owner_from or None
        db.upsert_flight(conn, rec, run_id)
        for kind, value in _evidence_kinds(rec):
            db.add_evidence(conn, uid, kind, value, run_id)

    if all_schedules:
        db.replace_schedules(conn, run_id, all_schedules)
    if runtime["queue"] is not None or runtime["tower"] is not None:
        db.replace_runtime(conn, run_id, runtime)

    db.commit(conn)
    return {"sources": report, "flights": len(merged),
            "schedules": len(all_schedules), "handoffs": len(all_handoffs),
            "stale": stale_n}
