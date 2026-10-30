#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worktree —— 车道工作树的只读体检。

用法：
  python worktree.py list [--root <repo>] [--json]
  python worktree.py status --lane main|deputy|second|ace [--slot a|b] [--root <repo>] [--json]

正常车道两固定槽（`lane-<lane>-a`／`-b`），王牌道仍一棵 `lane-ace`；
旧槽 `lane-<lane>` 视为 `-a`（迁移前查脏，脏则停手问人）。
只读：不建树、不切分支、不删树。缺槽位就如实报，不猜。
退出码：0 槽位存在；1 槽位缺失；2 git 起不来。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LANES = ("main", "deputy", "second", "ace")
SLOT_LANES = ("main", "deputy", "second")
SLOTS = ("a", "b")


def slot_path(root: str, lane: str, slot: str) -> str:
    return os.path.join(root, ".worktrees", f"lane-{lane}-{slot}")


def legacy_path(root: str, lane: str) -> str:
    return os.path.join(root, ".worktrees", f"lane-{lane}")


def git(root: str, *args: str):
    try:
        p = subprocess.run(["git", "-C", root, *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"git 起不来：{exc}"
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip()[:300]
    return p.stdout, None


def repo_root(root: str | None) -> str:
    base = os.path.abspath(root or os.getcwd())
    out, err = git(base, "rev-parse", "--show-toplevel")
    if err:
        raise SystemExit(f"不是 git 仓库或读不到根：{err}")
    return out.strip()


def parse_porcelain(text: str) -> list:
    items, cur = [], {}
    for line in text.splitlines():
        if not line.strip():
            if cur:
                items.append(cur)
                cur = {}
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            if cur:
                items.append(cur)
            cur = {"path": val}
        elif key in ("HEAD", "branch", "locked", "prunable"):
            cur[key] = val or True
        elif key == "detached":
            cur["detached"] = True
    if cur:
        items.append(cur)
    return items


def classify(path: str, root: str) -> str:
    norm = os.path.normcase(os.path.abspath(path))
    for lane in SLOT_LANES:
        for slot in SLOTS:
            if norm == os.path.normcase(slot_path(root, lane, slot)):
                return f"lane-{lane}-{slot}"
        if norm == os.path.normcase(legacy_path(root, lane)):
            return f"lane-{lane}-a"
    if norm == os.path.normcase(legacy_path(root, "ace")):
        return "lane-ace"
    base = os.path.basename(os.path.normpath(path)).lower()
    if base == "_push" or base.startswith("kai-push-station") or base.startswith("tower-push"):
        return "push-station"
    return "other"


def is_legacy(path: str, root: str) -> bool:
    norm = os.path.normcase(os.path.abspath(path))
    return any(norm == os.path.normcase(legacy_path(root, lane)) for lane in SLOT_LANES)


def dirty(path: str) -> tuple:
    out, err = git(path, "status", "--porcelain")
    if err:
        return None, err
    lines = [x for x in out.splitlines() if x.strip()]
    return lines, None


def status(root: str, lane: str, slot: str = "a") -> dict:
    out, err = git(root, "worktree", "list", "--porcelain")
    if err:
        raise SystemExit(f"git worktree list 失败：{err}")
    if lane == "ace":
        want = legacy_path(root, lane)
        candidates = [want]
        canonical = "lane-ace"
    else:
        want = slot_path(root, lane, slot)
        candidates = [want]
        if slot == "a":
            candidates.append(legacy_path(root, lane))
        canonical = f"lane-{lane}-{slot}"
    entry = None
    found_path = want
    for item in parse_porcelain(out):
        ip = os.path.normcase(os.path.abspath(item.get("path", "")))
        for cand in candidates:
            if ip == os.path.normcase(cand):
                entry = item
                found_path = cand
                break
        if entry:
            break
    if not entry:
        rel = os.path.join(".worktrees", canonical)
        return {"lane": lane, "slot": canonical, "path": want,
                "exists": False, "ok": False,
                "hint": f"git worktree add {rel} dev"}
    files, derr = dirty(found_path)
    return {
        "lane": lane,
        "slot": canonical,
        "path": found_path,
        "legacy": lane != "ace" and found_path == legacy_path(root, lane),
        "exists": True,
        "ok": files is not None and not files,
        "branch": (entry.get("branch") or "").replace("refs/heads/", "") or None,
        "head": entry.get("HEAD"),
        "detached": bool(entry.get("detached")),
        "dirty": bool(files),
        "files": (files or [])[:20],
        "dirty_error": derr,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="车道工作树只读体检")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--root")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn="list")
    p = sub.add_parser("status")
    p.add_argument("--lane", choices=LANES, required=True)
    p.add_argument("--slot", choices=SLOTS, default="a")
    p.add_argument("--root")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn="status")
    a = ap.parse_args(argv)

    root = repo_root(a.root)
    if a.fn == "list":
        out, err = git(root, "worktree", "list", "--porcelain")
        if err:
            print(f"git worktree list 失败：{err}")
            return 2
        items = []
        for item in parse_porcelain(out):
            files, _ = dirty(item["path"]) if os.path.isdir(item["path"]) else (None, None)
            items.append({"path": item["path"], "slot": classify(item["path"], root),
                          "legacy": is_legacy(item["path"], root),
                          "branch": (item.get("branch") or "").replace("refs/heads/", "") or None,
                          "head": item.get("HEAD"), "detached": bool(item.get("detached")),
                          "dirty": bool(files), "files": len(files or [])})
        if a.json:
            print(json.dumps({"root": root, "worktrees": items}, ensure_ascii=False, indent=2))
        else:
            for it in items:
                name = it["slot"] + (" (legacy)" if it.get("legacy") else "")
                print(f"{name:<22} {it['branch'] or '(detached)':<28} "
                      f"{'脏' if it['dirty'] else '净'} {it['path']}")
        return 0

    info = status(root, a.lane, a.slot)
    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    elif not info["exists"]:
        print(f"{info['slot']}：槽位缺失 {info['path']}；{info['hint']}")
    else:
        legacy = " (legacy)" if info.get("legacy") else ""
        print(f"{info['slot']}{legacy}：{info['branch'] or '(detached)'} @ {str(info['head'])[:10]} "
              f"{'脏 ' + str(len(info['files'])) + ' 件' if info['dirty'] else '净'}")
    return 0 if info["exists"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
