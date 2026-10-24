# -*- coding: utf-8 -*-
"""采集编排：跑每个源 → 记账 → 按 uid 合并 → 判阶段 → 落库。

本模块是唯一知道「有哪几个源、怎么合并、判据从哪来」的地方。
源模块不认识彼此，也不认识数据库。
"""
from __future__ import annotations

from . import db, stage
from .sources import get as get_source

MERGE_FIRST = ("title", "ticket", "assignee", "milestone", "url",
               "owner", "persona", "last_comment", "table_note")


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
    """跑全部源，返回 {"sources": {...}, "flights": n, "schedules": n}。"""
    all_records, all_schedules, report = [], [], {}

    for sc in config.get("sources") or []:
        sid = sc.get("id") or sc.get("type")
        typ = sc.get("type")
        try:
            mod = get_source(typ)
        except KeyError as e:
            report[sid] = {"status": "fail", "rows": 0, "detail": str(e)}
            db.record_source(conn, run_id, sid, typ or "?", "fail", 0, str(e))
            continue
        try:
            res = mod.collect(sc, ctx)
        except Exception as e:                      # 单源炸不拖垮整页
            detail = f"{type(e).__name__}: {e}"
            report[sid] = {"status": "fail", "rows": 0, "detail": detail}
            db.record_source(conn, run_id, sid, typ, "fail", 0, detail)
            continue
        flights = res.get("flights") or []
        schedules = res.get("schedules") or []
        status = res.get("status") or "ok"
        detail = res.get("detail") or ""
        all_records.extend(flights)
        all_schedules.extend(schedules)
        report[sid] = {"status": status, "rows": len(flights) + len(schedules),
                       "detail": detail}
        db.record_source(conn, run_id, sid, typ, status,
                         len(flights) + len(schedules), detail)

    merged = merge_flights(all_records)
    rules = config.get("stage_rules") or []
    # 阶段名要对得上号：链上阶段与链外阶段（可领／挡住）都算，别让它们掉成「未定」
    labels = {}
    for s in list(config.get("stages") or []) + list(config.get("off_chain_stages") or []):
        labels[s["key"]] = s.get("label") or s["key"]

    for uid, rec in merged.items():
        ev = {"closed": rec.get("closed"), "labels": rec.get("labels"),
              "last_comment": rec.get("last_comment"), "branches": rec.get("branches"),
              "table_note": rec.get("table_note"), "assignee": rec.get("assignee")}
        st, why = stage.decide(rules, ev)
        rec["stage"] = st or "undefined"
        rec["stage_label"] = labels.get(rec["stage"]) or (
            "未定" if rec["stage"] == "undefined" else rec["stage"])
        rec["why"] = why
        db.upsert_flight(conn, rec, run_id)
        for kind, value in _evidence_kinds(rec):
            db.add_evidence(conn, uid, kind, value, run_id)

    if all_schedules:
        db.replace_schedules(conn, run_id, all_schedules)

    db.commit(conn)
    return {"sources": report, "flights": len(merged), "schedules": len(all_schedules)}
