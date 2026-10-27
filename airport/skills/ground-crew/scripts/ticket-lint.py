#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ticket-lint —— 开票前查六件套，缺件直接红。

用法：
  python ticket-lint.py --body-file ticket.md [--labels ready-for-agent,risk:low] [--json]
  python ticket-lint.py --text "..." [--json]

六件：目标 / AC / 允许修改 / 禁止修改 / 验证命令 / 依赖或红线。
退出码：0 齐全；1 缺件；2 输入读不出。
"""
from __future__ import annotations

import argparse
import json
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(.*)$")
CODE_RE = re.compile(r"`([^`]+)`")

PIECES = {
    "目标": ("目标",),
    "AC": ("AC", "验收"),
    "允许修改": ("允许修改", "允许"),
    "禁止修改": ("禁止修改", "禁止"),
    "验证命令": ("验证命令", "验证"),
    "依赖或红线": ("依赖", "红线"),
}


def sections(text: str) -> dict:
    out, cur = {}, None
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            cur = m.group(1).strip()
            out.setdefault(cur, [])
            continue
        if cur is not None:
            out[cur].append(line)
    return out


def content(secs: dict, keys) -> list:
    for name, lines in secs.items():
        if any(k.lower() in name.lower() for k in keys):
            items = []
            for line in lines:
                m = LIST_RE.match(line)
                if m and m.group(1).strip():
                    items.append(m.group(1).strip())
                elif line.strip() and not line.lstrip().startswith("#"):
                    items.append(line.strip())
            return items
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="开票前六件套自检")
    ap.add_argument("--body-file")
    ap.add_argument("--text")
    ap.add_argument("--labels", default="")
    ap.add_argument("--require-label", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.body_file:
        try:
            with open(a.body_file, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as exc:
            print(f"票面读不出：{exc}")
            return 2
    else:
        text = a.text or ""

    secs = sections(text)
    found, missing = {}, []
    for label, keys in PIECES.items():
        items = content(secs, keys)
        found[label] = items
        if not items:
            missing.append(label)
    if a.require_label:
        labels = [x.strip() for x in a.labels.split(",") if x.strip()]
        if a.require_label not in labels:
            missing.append(f"标签 {a.require_label}")
    out = {"ok": not missing, "missing": missing,
           "counts": {k: len(v) for k, v in found.items()}}
    print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else
          ("六件套齐全" if out["ok"] else "缺件：" + "、".join(missing)))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
