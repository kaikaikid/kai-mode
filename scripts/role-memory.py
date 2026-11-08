#!/usr/bin/env python3
"""角色经验记忆：追加式日志，单写者，可回滚，留审计。

裁决：docs/adr/0033-guild-role-layer.md D5。目录契约：roles/README.md「记忆」节。

硬判据（三条，全部机械执行，不靠提示词自觉）：
1. **只有 `archivist` 能写**。其他角色的写入一律拒绝并返回非零——包括康娜。
   别的角色只能提候选：把候选写成一段文本交给人或交回知识管理角色，不走本工具。
2. **追加式**。日志只追加，不改旧行；回滚是再追加一条反向记录，原记录永久保留。
3. **无证据不写**。每条至少一个 `evidence_refs`，且不得是空串或「我确认过」这类自述。

用法：
  python scripts/role-memory.py append   --log <路> --writer archivist --scope task_fact \
         --statement "…" --evidence "path/to/evidence:行号" [--conflicts "m-0002"]
  python scripts/role-memory.py rollback --log <路> --writer archivist --target m-0001 --reason "…"
  python scripts/role-memory.py check    --log <路> [--json]
  python scripts/role-memory.py show     --log <路> [--json]

退出码：0 成功；2 参数/格式错；3 非授权写者；4 校验不过。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WRITER = "archivist"
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
            f"别的角色只能提候选，不走本工具（ADR-0033 D5）。")


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
        if r.get("writer") != WRITER:
            bad.append(f"{rid} 的写者是 {r.get('writer')!r}，只许 {WRITER}")
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
              f"写者只有 {WRITER}，每条都有可核验证据")
    return 4 if bad else 0


def cmd_show(a: argparse.Namespace) -> int:
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
        sp.add_argument("--log", required=True, help="日志文件路径（JSONL）")
        sp.add_argument("--json", action="store_true", help="机器可读输出")
        if name == "append":
            sp.add_argument("--writer", required=True)
            sp.add_argument("--scope", required=True, choices=SCOPES)
            sp.add_argument("--statement", required=True)
            sp.add_argument("--evidence", action="append", default=[])
            sp.add_argument("--before", default="")
            sp.add_argument("--after", default="")
            sp.add_argument("--conflicts", action="append", default=[])
        if name == "rollback":
            sp.add_argument("--writer", required=True)
            sp.add_argument("--target", required=True)
            sp.add_argument("--reason", required=True)
    a = p.parse_args()
    try:
        return {"append": cmd_append, "rollback": cmd_rollback,
                "check": cmd_check, "show": cmd_show}[a.cmd](a)
    except PermissionError as e:
        print(str(e), file=sys.stderr)
        return 3
    except (MemoryError_, OSError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())