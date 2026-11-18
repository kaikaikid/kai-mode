#!/usr/bin/env python3
"""角色经验记忆：追加式日志，单写者，可回滚，留审计。

裁决：docs/adr/0033-guild-role-layer.md D5；写者迁移见 docs/adr/0035-universal-role-projection.md D4
（记忆治理归青铜龙的 `dream` skill，`coordinator` 旧记录兼容读）。

硬判据（三条，全部机械执行，不靠提示词自觉）：
1. **只有 `archivist`（青铜龙）能写**。其他角色的写入一律拒绝并返回非零。
   别的角色只能提候选：把候选写成一段文本交给人或交回康娜，不走本工具。
   旧日志里 `writer=coordinator` 的记录**兼容读**（历史不追溯改写）；`inspect` 两者都认，
   但新写入只收 `archivist`。
2. **追加式**。日志只追加，不改旧行；回滚是再追加一条反向记录，原记录永久保留。
3. **无证据不写**。每条至少一个 `evidence_refs`，且不得是空串或「我确认过」这类自述。

两种存储（ADR-0037 D9）：
- `--db <SQLite>`：v1 目标形态。append 转 propose+commit 写账本；show/check 读账本；
  `import` 把旧 JSONL 导入账本并保留 `legacy_id`。
- `--log <JSONL>`：v0 兼容路径，行为与旧版一致（历史可追溯，不静默改写）。

用法：
  python scripts/role-memory.py append   --db <库> --writer archivist --scope task_fact \
         --statement "…" --evidence "path/to/evidence:行号" [--conflicts "m-0002"]
  python scripts/role-memory.py append   --log <路> …（旧 JSONL 路径）
  python scripts/role-memory.py rollback --db <库> --writer archivist --target m-0001 --reason "…"
  python scripts/role-memory.py check    --db <库> [--json]
  python scripts/role-memory.py show     --db <库> [--json]
  python scripts/role-memory.py import   --db <库> --from-jsonl <旧路> --writer archivist

退出码：0 成功；2 参数/格式错；3 非授权写者；4 校验不过。
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# 写者：ADR-0035 D4 修订后记忆治理归青铜龙（archivist）。旧日志的 coordinator 记录兼容读，
# 但不再接受 coordinator 写入——历史可追溯，正本不追溯改写。
WRITER = "archivist"
LEGACY_WRITERS = ("coordinator",)
KNOWN_WRITERS = (WRITER, *LEGACY_WRITERS)
SCOPES = ("task_fact", "preference", "skill", "relationship", "failure_lesson")
LAYER = "ego"  # light 变更只能落自我层（V1.5 R11）
REQUIRED = ("id", "ts", "writer", "scope", "layer", "statement",
            "evidence_refs", "before", "after", "conflicts_with", "rollback_of")
SELF_EVIDENCE = re.compile(
    r"^(已确认|确认过|自述|无|none|-|n/?a)$"
    r"|^(我|本人|咱)(?![^:：/\\]*[:：/\\])[^:：/\\]{0,12}$",
    re.I)


class MemoryError_(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError as e:
            raise MemoryError_(f"第 {i} 行不是合法 JSON：{e}")
        if not isinstance(rec, dict):
            raise MemoryError_(f"第 {i} 行不是对象")
        out.append(rec)
    return out


def next_id(records: list[dict]) -> str:
    nums = [int(m.group(1)) for r in records
            if (m := re.fullmatch(r"m-(\d+)", str(r.get("id", ""))))]
    return f"m-{(max(nums) + 1) if nums else 1:04d}"


def append_line(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def require_writer(writer: str) -> None:
    if writer != WRITER:
        raise PermissionError(
            f"拒绝写入：记忆的唯一读写改者是 `{WRITER}`，收到的是 `{writer}`。"
            f"别的角色只能提候选，不走本工具（ADR-0035 D4）。")


# -- 账本模式（ADR-0037 D9） -------------------------------------------------

def _open_ledger(db: str):
    """惰性导入 engine/memory；没装包时只在用 --db 时才需要。"""
    engine_dir = Path(__file__).resolve().parents[1] / "engine"
    if str(engine_dir) not in sys.path:
        sys.path.insert(0, str(engine_dir))
    from memory.engine import FTS5Engine
    from memory.ledger import Ledger
    return Ledger(db, engine=FTS5Engine(db))


def ledger_append(a: argparse.Namespace) -> int:
    require_writer(a.writer)
    statement = a.statement.strip()
    if not statement:
        raise MemoryError_("--statement 不能为空")
    evidence = clean_evidence(a.evidence or [])
    with _open_ledger(a.db) as ledger:
        prop = ledger.propose(
            actor_role=a.writer, namespace=a.namespace or "shared",
            kind=a.scope, statement=statement, evidence_refs=evidence,
            source=a.source or "role-memory", layer=LAYER,
            before=(a.before or "").strip(), after=(a.after or "").strip(),
            conflicts_with=[c.strip() for c in (a.conflicts or []) if c.strip()])
        rec = ledger.commit(actor_role=WRITER, proposal_id=prop["memory_id"])
    out = dict(rec)
    out["writer"] = rec.get("actor_role")
    out["scope"] = rec.get("kind")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def ledger_rollback(a: argparse.Namespace) -> int:
    require_writer(a.writer)
    if not a.reason.strip():
        raise MemoryError_("回滚必须写 --reason（审计要能看出为什么撤）")
    with _open_ledger(a.db) as ledger:
        rec = ledger.rollback(actor_role=a.writer, target=a.target,
                              reason=a.reason.strip())
    out = dict(rec)
    out["writer"] = rec.get("actor_role")
    out["scope"] = rec.get("kind")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def ledger_problems(ledger) -> list[str]:
    bad: list[str] = []
    events = ledger.events()
    ids = {e.get("memory_id") for e in events}
    for i, e in enumerate(events, 1):
        rid = e.get("memory_id") or f"#{i}"
        if e.get("kind") not in SCOPES:
            bad.append(f"{rid} 的 scope 非法：{e.get('kind')!r}")
        if e.get("layer") not in (None, LAYER):
            bad.append(f"{rid} 的 layer 是 {e.get('layer')!r}，light 变更只许 {LAYER}")
        if e.get("event_type") in ("commit", "import"):
            if e.get("committed_by") != WRITER:
                bad.append(f"{rid} 的 committed_by 是 {e.get('committed_by')!r}，只许 {WRITER}")
            if e.get("actor_role") not in KNOWN_WRITERS:
                bad.append(
                    f"{rid} 的写者是 {e.get('actor_role')!r}，只许 {WRITER}"
                    f"（旧日志兼容 {'/'.join(LEGACY_WRITERS)}）")
        if e.get("event_type") in ("propose", "commit", "import"):
            ev = e.get("evidence_refs") or []
            if not ev:
                bad.append(f"{rid} 没有证据引用")
            for x in ev:
                if SELF_EVIDENCE.match(str(x).strip()):
                    bad.append(f"{rid} 的证据是自述类：{x!r}")
        if e.get("rollback_of") and e["rollback_of"] not in ids:
            bad.append(f"{rid} 回滚了不存在的记录 {e['rollback_of']}")
    return bad


def ledger_check(a: argparse.Namespace) -> int:
    with _open_ledger(a.db) as ledger:
        bad = ledger_problems(ledger)
        records = ledger.count_events()
        active = sorted(r["memory_id"] for r in ledger.current_rows(status="active"))
    if a.json:
        print(json.dumps({"log": str(a.db), "records": records, "active": active,
                          "ok": not bad, "problems": bad},
                         ensure_ascii=False, indent=2))
    elif bad:
        print(f"记忆账本校验不过（{len(bad)} 处）：")
        for b in bad:
            print(f"  - {b}")
    else:
        print(f"记忆账本通过：{records} 个事件，活跃 {len(active)} 条，"
              f"写者只有 {WRITER}（旧 {'/'.join(LEGACY_WRITERS)} 记录兼容读），"
              "每条都有可核验证据")
    return 4 if bad else 0


def ledger_show(a: argparse.Namespace) -> int:
    with _open_ledger(a.db) as ledger:
        rows = ledger.current_rows(status="active")
    out = []
    for r in rows:
        out.append({**r, "id": r["memory_id"], "scope": r.get("kind"),
                    "writer": r.get("actor_role")})
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    else:
        for r in out:
            print(f"{r['id']} [{r['scope']}] {r['statement']}")
            print(f"    证据：{'; '.join(r.get('evidence_refs') or [])}")
    return 0


def ledger_import(a: argparse.Namespace) -> int:
    require_writer(a.writer)
    records = read_log(Path(a.from_jsonl))
    with _open_ledger(a.db) as ledger:
        result = ledger.import_legacy(records)
    if a.json:
        print(json.dumps({**result, "db": str(a.db),
                          "from": str(a.from_jsonl)}, ensure_ascii=False, indent=2))
    else:
        print(f"导入完成：新增 {result['imported']}，跳过 {result['skipped']}，"
              f"账本共 {result['events']} 个事件（legacy_id 已保留）")
    return 0


def clean_evidence(items: list[str]) -> list[str]:
    out = []
    for raw in items:
        s = str(raw).strip()
        if not s:
            continue
        if SELF_EVIDENCE.match(s):
            raise MemoryError_(f"证据不可为自述类：{s!r}；要可核验的指针（文件:行号、URL、命令输出）")
        out.append(s)
    if not out:
        raise MemoryError_("至少给一个证据引用（--evidence）；无证据不得写入")
    return out


def cmd_append(a: argparse.Namespace) -> int:
    if a.db:
        return ledger_append(a)
    require_writer(a.writer)
    if a.scope not in SCOPES:
        raise MemoryError_(f"--scope 必须是 {SCOPES} 之一")
    statement = a.statement.strip()
    if not statement:
        raise MemoryError_("--statement 不能为空")
    path = Path(a.log)
    records = read_log(path)
    rec = {
        "id": next_id(records),
        "ts": now(),
        "writer": a.writer,
        "scope": a.scope,
        "layer": LAYER,
        "statement": statement,
        "evidence_refs": clean_evidence(a.evidence or []),
        "before": (a.before or "").strip(),
        "after": (a.after or "").strip(),
        "conflicts_with": [c.strip() for c in (a.conflicts or []) if c.strip()],
        "rollback_of": None,
    }
    append_line(path, rec)
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


def cmd_rollback(a: argparse.Namespace) -> int:
    if a.db:
        return ledger_rollback(a)
    require_writer(a.writer)
    path = Path(a.log)
    records = read_log(path)
    target = next((r for r in records if r.get("id") == a.target), None)
    if target is None:
        raise MemoryError_(f"找不到要回滚的记录：{a.target}")
    if not a.reason.strip():
        raise MemoryError_("回滚必须写 --reason（审计要能看出为什么撤）")
    rec = {
        "id": next_id(records),
        "ts": now(),
        "writer": a.writer,
        "scope": target.get("scope", "task_fact"),
        "layer": LAYER,
        "statement": f"回滚 {a.target}：{a.reason.strip()}",
        "evidence_refs": [f"role-memory:{a.target}"],
        "before": target.get("after") or target.get("statement", ""),
        "after": target.get("before") or "",
        "conflicts_with": [],
        "rollback_of": a.target,
    }
    append_line(path, rec)
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


def active_ids(records: list[dict]) -> set[str]:
    rolled = {r.get("rollback_of") for r in records if r.get("rollback_of")}
    return {r["id"] for r in records if r.get("id") and r.get("id") not in rolled}


def inspect(records: list[dict]) -> list[str]:
    bad: list[str] = []
    seen: set[str] = set()
    for i, r in enumerate(records, 1):
        rid = r.get("id")
        for k in REQUIRED:
            if k not in r:
                bad.append(f"第 {i} 条缺字段 {k}")
        if rid in seen:
            bad.append(f"id 重复：{rid}")
        seen.add(rid)
        if r.get("writer") not in KNOWN_WRITERS:
            bad.append(f"{rid} 的写者是 {r.get('writer')!r}，只许 {WRITER}"
                       f"（旧日志兼容 {'/'.join(LEGACY_WRITERS)}）")
        if r.get("layer") != LAYER:
            bad.append(f"{rid} 的 layer 是 {r.get('layer')!r}，light 变更只许 {LAYER}")
        if r.get("scope") and r.get("scope") not in SCOPES:
            bad.append(f"{rid} 的 scope 非法：{r.get('scope')!r}")
        ev = r.get("evidence_refs") or []
        if not ev:
            bad.append(f"{rid} 没有证据引用")
        for e in ev:
            if SELF_EVIDENCE.match(str(e).strip()):
                bad.append(f"{rid} 的证据是自述类：{e!r}")
        if r.get("rollback_of"):
            tgt = next((x for x in records if x.get("id") == r["rollback_of"]), None)
            if tgt is None:
                bad.append(f"{rid} 回滚了不存在的记录 {r['rollback_of']}")
    return bad


def cmd_check(a: argparse.Namespace) -> int:
    if a.db:
        return ledger_check(a)
    path = Path(a.log)
    records = read_log(path)
    bad = inspect(records)
    if a.json:
        print(json.dumps({"log": str(path), "records": len(records),
                          "active": sorted(active_ids(records)),
                          "ok": not bad, "problems": bad}, ensure_ascii=False, indent=2))
    elif bad:
        print(f"记忆日志校验不过（{len(bad)} 处）：")
        for b in bad:
            print(f"  - {b}")
    else:
        print(f"记忆日志通过：{len(records)} 条，活跃 {len(active_ids(records))} 条，"
              f"写者只有 {WRITER}（旧 {'/'.join(LEGACY_WRITERS)} 记录兼容读），每条都有可核验证据")
    return 4 if bad else 0


def cmd_show(a: argparse.Namespace) -> int:
    if a.db:
        return ledger_show(a)
    records = read_log(Path(a.log))
    live = active_ids(records)
    rows = [r for r in records if r.get("id") in live and not r.get("rollback_of")]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['id']} [{r['scope']}] {r['statement']}")
            print(f"    证据：{'; '.join(r.get('evidence_refs') or [])}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="角色经验记忆（单写者／追加／可回滚）")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("append", "rollback", "check", "show"):
        sp = sub.add_parser(name)
        sp.add_argument("--log", default=None, help="旧 JSONL 日志路径（v0 兼容）")
        sp.add_argument("--db", default=None, help="SQLite 账本路径（v1 目标形态）")
        sp.add_argument("--json", action="store_true", help="机器可读输出")
        if name == "append":
            sp.add_argument("--writer", required=True)
            sp.add_argument("--scope", required=True, choices=SCOPES)
            sp.add_argument("--statement", required=True)
            sp.add_argument("--evidence", action="append", default=[])
            sp.add_argument("--before", default="")
            sp.add_argument("--after", default="")
            sp.add_argument("--conflicts", action="append", default=[])
            sp.add_argument("--namespace", default="shared",
                            help="账本模式命名空间（默认 shared）")
            sp.add_argument("--source", default=None,
                            help="账本模式来源标识（默认 role-memory）")
        if name == "rollback":
            sp.add_argument("--writer", required=True)
            sp.add_argument("--target", required=True)
            sp.add_argument("--reason", required=True)

    sp = sub.add_parser("import", help="把旧 JSONL 导入 SQLite 账本（保留 legacy_id）")
    sp.add_argument("--db", required=True, help="SQLite 账本路径")
    sp.add_argument("--from-jsonl", required=True, help="旧 JSONL 路径")
    sp.add_argument("--writer", required=True)
    sp.add_argument("--json", action="store_true", help="机器可读输出")

    a = p.parse_args()
    try:
        if a.cmd != "import":
            if not (getattr(a, "db", None) or getattr(a, "log", None)):
                raise MemoryError_("必须给 --db（账本）或 --log（旧 JSONL）")
        return {"append": cmd_append, "rollback": cmd_rollback,
                "check": cmd_check, "show": cmd_show,
                "import": ledger_import}[a.cmd](a)
    except PermissionError as e:
        print(str(e), file=sys.stderr)
        return 3
    except (MemoryError_, OSError, ValueError, sqlite3.Error) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    except Exception as e:  # engine/memory 的异常类名为保持包独立，不在此处 import
        kind = type(e).__name__
        if kind == "PermissionDenied":
            print(str(e), file=sys.stderr)
            return 3
        if kind in ("MemoryError", "NotFound", "ConflictError"):
            print(f"错误：{e}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    raise SystemExit(main())