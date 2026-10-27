#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harness-audit 盘点器：列出审计面（技能/人格/ADR/协议/规范）的只读读数。

用法：
  python skills/harness-audit/scripts/inventory.py --root <仓根>
  python skills/harness-audit/scripts/inventory.py --root <仓根> --changed-since 2026-10-01

输出 JSON（默认）或 `--summary` 人读摘要。只读，不写盘；mtime 只作“可能变过”的线索，
不是 git 事实——Quick Scan 仍要对照上次审计记录。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LEGACY = {"航班信息", "set-航班信息"}
PERSONA_SKIP = {"README.md", "dispatch.md"}


def sha12(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def frontmatter(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def tracked_files(root: str) -> set | None:
    """git 跟踪清单；非 git 仓返回 None（“未跟踪”与“不知道”不能混）。"""
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    try:
        p = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    return {x.decode("utf-8", "replace").replace("\\", "/") for x in p.stdout.split(b"\0") if x}


def info(root: str, kind: str, path: str, tracked: set | None = None) -> dict:
    fm = frontmatter(path)
    rel = os.path.relpath(path, root).replace("\\", "/")
    try:
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc).isoformat()
        lines = sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
        size = os.path.getsize(path)
        digest = sha12(path)
    except OSError:
        mtime, lines, size, digest = "", 0, 0, ""
    return {
        "kind": kind,
        "name": fm.get("name") or os.path.splitext(os.path.basename(path))[0],
        "path": rel,
        "mtime": mtime,
        "lines": lines,
        "bytes": size,
        "sha256_12": digest,
        "version": fm.get("version", ""),
        "updated": fm.get("updated", ""),
        "tracked": (rel in tracked) if tracked is not None else None,
    }


def collect(root: str) -> dict:
    files = []
    tracked = tracked_files(root)
    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        for name in sorted(os.listdir(skills_dir)):
            p = os.path.join(skills_dir, name, "SKILL.md")
            if os.path.isfile(p):
                item = info(root, "skill", p, tracked)
                item["legacy"] = name in LEGACY
                files.append(item)
    agents_dir = os.path.join(root, "agents")
    if os.path.isdir(agents_dir):
        for name in sorted(os.listdir(agents_dir)):
            if name.endswith(".md") and name not in PERSONA_SKIP:
                files.append(info(root, "persona", os.path.join(agents_dir, name), tracked))
    adr_dir = os.path.join(root, "docs", "adr")
    if os.path.isdir(adr_dir):
        for name in sorted(os.listdir(adr_dir)):
            if name.endswith(".md"):
                files.append(info(root, "adr", os.path.join(adr_dir, name), tracked))
    loops_dir = os.path.join(root, "loops")
    if os.path.isdir(loops_dir):
        for name in sorted(os.listdir(loops_dir)):
            if name.endswith(".md"):
                files.append(info(root, "protocol", os.path.join(loops_dir, name), tracked))
    for rel in ("README.md", "AGENTS.md", "GLOSSARY.md", "handoff/README.md",
                "docs/skill-layout.md", "docs/canon.json"):
        p = os.path.join(root, *rel.split("/"))
        if os.path.isfile(p):
            files.append(info(root, "norm", p, tracked))
    return {
        "schema": "kai-mode-harness-audit/1",
        "root": os.path.abspath(root),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files": files,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="harness-audit 只读盘点")
    ap.add_argument("--root", default=".")
    ap.add_argument("--changed-since", default=None, help="ISO 日期；只保留 mtime 更晚的文件")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    data = collect(root)
    if a.changed_since:
        try:
            since = dt.datetime.fromisoformat(a.changed_since)
            if since.tzinfo is None:
                since = since.replace(tzinfo=dt.timezone.utc)
            data["changed_since"] = a.changed_since
            data["files"] = [f for f in data["files"]
                             if f["mtime"] and dt.datetime.fromisoformat(f["mtime"]) > since]
        except ValueError:
            print(f"--changed-since 不是 ISO 日期：{a.changed_since}", file=sys.stderr)
            return 2
    if a.summary:
        counts = {}
        for f in data["files"]:
            counts[f["kind"]] = counts.get(f["kind"], 0) + 1
        print(f"审计面 {len(data['files'])} 件： " + "、".join(f"{k} {v}" for k, v in sorted(counts.items())))
        for f in data["files"]:
            print(f"  {f['kind']:<8} {f['name']:<42} {f['lines']:>4} 行  {f['version']:<8} {f['path']}")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
