#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""protocol —— 按节取协议，避免整份 30KB 正文每次都进上下文。

用法：
  python protocol.py --list
  python protocol.py --section 三
  python protocol.py --section "停点闭集"

退出码：0 找到；1 没找到；2 协议文件缺失。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PROTOCOL = os.path.normpath(os.path.join(HERE, "..", "references", "loop-protocol.md"))
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
NUMERALS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "十一": 11, "十二": 12, "十三": 13}


def load() -> tuple:
    if not os.path.isfile(PROTOCOL):
        print(f"协议缺失：{PROTOCOL}")
        raise SystemExit(2)
    with open(PROTOCOL, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def headings(lines: list) -> list:
    out = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            out.append((i, m.group(1)))
    return out


def find(lines: list, want: str):
    want = want.strip().lstrip("§").strip()
    hs = headings(lines)
    if not hs:
        return None
    # 纯数字/中文数字：按序号找
    num = None
    if want.isdigit():
        num = int(want)
    elif want in NUMERALS:
        num = NUMERALS[want]
    if num is not None and 0 <= num < len(hs):
        return hs[num]
    # 标题文本包含
    for item in hs:
        if want in item[1]:
            return item
    return None


def section_text(lines: list, idx: int) -> list:
    end = len(lines)
    for j in range(idx + 1, len(lines)):
        if HEADING_RE.match(lines[j]):
            end = j
            break
    return lines[idx:end]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="按节读取单票闭环协议")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--section")
    a = ap.parse_args(argv)
    lines = load()
    if a.list:
        for _, title in headings(lines):
            print(title)
        return 0
    if not a.section:
        print("给 --list 或 --section")
        return 1
    hit = find(lines, a.section)
    if not hit:
        print(f"没找到：{a.section}")
        return 1
    print("\n".join(section_text(lines, hit[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
