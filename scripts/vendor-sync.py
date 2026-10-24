#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""辅助技能原样拉取（vendor/）
================================
工作流要用的通用方法技能，**原样复制源仓库那一份**到 `vendor/skills/`，不改一个字、
不改名、不登记 registry。它们是「辅助件」：用的时候读，不当作本仓的裁决。

用法：
  python scripts/vendor-sync.py            # 拉取/刷新 vendor/skills/
  python scripts/vendor-sync.py --check    # 只校验：源变了没、vendor 被改过没

源：本机 `~/.workbuddy/skills/`（两个上游的本地镜像：mattpocock/skills 六个 ＋
cloudflare/security-audit-skill 一个；来源见 docs/skill-sources/sources.json）
清单正本：`vendor/manifest.json`（每次 sync 重写，记每个文件的 sha256）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
VENDOR = os.path.join(ROOT, "vendor")
DEST = os.path.join(VENDOR, "skills")
MANIFEST = os.path.join(VENDOR, "manifest.json")
SOURCE = os.path.expanduser(os.path.join("~", ".workbuddy", "skills"))

SKILLS = ["tdd", "code-review", "diagnosing-bugs",
          "domain-modeling", "to-tickets", "writing-for-agents",
          "security-audit"]

SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")


def sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def tree(path: str) -> dict:
    out = {}
    for base, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            full = os.path.join(base, name)
            out[os.path.relpath(full, path).replace("\\", "/")] = sha(full)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="辅助技能原样拉取")
    ap.add_argument("--check", action="store_true", help="只校验不写盘")
    a = ap.parse_args()

    if not os.path.isdir(SOURCE):
        print(f"源目录不存在：{SOURCE}")
        return 2

    missing = [n for n in SKILLS if not os.path.isfile(os.path.join(SOURCE, n, "SKILL.md"))]
    if missing:
        print("源里缺这些技能：" + "、".join(missing))
        return 2

    manifest = {"source": "~/.workbuddy/skills（mattpocock/skills 六个 ＋ cloudflare/security-audit-skill 一个）",
                "note": "原样复制，不改内容；本仓只做辅助引用，不做裁决", "skills": {}}

    drift = []
    for name in SKILLS:
        src = os.path.join(SOURCE, name)
        dst = os.path.join(DEST, name)
        src_tree = tree(src)
        manifest["skills"][name] = src_tree
        if a.check:
            if not os.path.isdir(dst):
                drift.append(f"{name}: vendor 缺件")
                continue
            dst_tree = tree(dst)
            if dst_tree != src_tree:
                only_src = sorted(set(src_tree) - set(dst_tree))
                only_dst = sorted(set(dst_tree) - set(src_tree))
                diff = sorted(k for k in set(src_tree) & set(dst_tree)
                              if src_tree[k] != dst_tree[k])
                drift.append(f"{name}: 源与 vendor 不一致（源多 {only_src} / vendor 多 {only_dst} / 内容差 {diff}）")
            continue
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=SKIP)
        print(f"拉取 {name:20} {len(src_tree)} 文件 → vendor/skills/{name}")

    if a.check:
        if drift:
            print("漂移：")
            for d in drift:
                print("  -", d)
            print("修：python scripts/vendor-sync.py")
            return 1
        print(f"vendor 与源一致（{len(SKILLS)} 个技能）")
        return 0

    os.makedirs(VENDOR, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"清单已写：vendor/manifest.json（{len(SKILLS)} 个技能）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
