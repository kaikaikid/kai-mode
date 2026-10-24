#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新技能脚手架 —— 别手写 frontmatter 和 registry，跑这个。
===========================================================
干三件事：复制骨架模板 → 填 frontmatter 八字段 → 往 registry.json 插一行。
省 token（AI 不用背八字段与顺序）、防漂移（字段与顺序由脚本保证）。

用法：
  python scripts/new-skill.py <技能名> --summary "一句话：这个技能干什么"
                              [--title "标题后缀"] [--kind framework|personal]
                              [--install auto|manual|none] [--tags a,b]
                              [--source "handoff/README.md|裁决来源"] [--dry-run]

约定：
  · 目录名＝技能名＝frontmatter name＝registry name（三处一致，doctor 会查）
  · 框架件（角色/协议/闭环）一律 framework + auto；只给自己用的才 personal + manual
  · 生成后照骨架里的 `<...>` 占位补全正文，再跑 `python scripts/doctor.py` 到绿
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TPL = os.path.join(ROOT, "templates", "skill", "SKILL.md")
REGISTRY = os.path.join(ROOT, "registry.json")
NAME_RE = re.compile(r"^[A-Za-z0-9一-龥][A-Za-z0-9一-龥_-]*$")


def render(name, title, summary, source, today):
    with open(TPL, encoding="utf-8") as f:
        text = f.read()
    desc = (f"  {summary}\n"
            f"  触发：<触发口令或自然语言关键词>。")
    text = text.replace("<技能名> —— <一句话定位>", f"{name} —— {title}")
    text = text.replace("<技能名>", name)
    text = text.replace("<YYYY-MM-DD>", today)
    # sources：默认指向调用方给的裁决来源，没给就留占位提示
    if source:
        res, _, note = source.partition("|")
        text = text.replace(
            '  - resource: "项目配置实例 registry.adrs.dir 指向的 ADR（ADR-xxxx-<裁决名>）"\n'
            '    note: "裁决来源：这份技能凭什么这么定；落点读项目配置实例（ADR-0004 D2），读不到实例 ⇒ 按 D4 报缺件"',
            f'  - resource: "{res.strip()}"\n    note: "{note.strip() or "裁决来源"}"')
    # description 折叠块：整块替换（正则只换首行会留下重复的第二行）
    old_desc = ("description: >\n"
                "  一句话：做什么 / 不做什么 / 触发词。\n"
                "  触发：<触发口令或自然语言关键词>。")
    text = text.replace(old_desc,
                        f"description: >\n  {summary}\n  触发：<触发口令或自然语言关键词>。")
    return text


def registry_add(entry, dry):
    """文本插入，保持 registry.json 原格式与行尾。

    不用 json.dump 重写——那会把整个文件重排（实测 diff 74+/15-），淹掉真正的改动。
    """
    raw = open(REGISTRY, "rb").read().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    if f'"name": "{entry["name"]}"' in raw:
        return None, f"registry 里已经有 {entry['name']}，不重复加"
    block = json.dumps(entry, ensure_ascii=False, indent=2).replace("\n", eol)
    block = eol.join("    " + ln for ln in block.split(eol))
    marker = '"skills": [' + eol
    i = raw.find(marker)
    if i < 0:
        return None, 'registry.json 里找不到 "skills": ['
    pos = i + len(marker)
    if not dry:
        open(REGISTRY, "wb").write((raw[:pos] + block + "," + eol + raw[pos:]).encode("utf-8"))
    return entry, None


def main() -> int:
    ap = argparse.ArgumentParser(description="新技能脚手架（骨架 + frontmatter + registry 一条龙）")
    ap.add_argument("name", help="技能名＝目录名（中英文均可，不含空格）")
    ap.add_argument("--summary", required=True, help="一句话：这个技能干什么（进 description 与 registry）")
    ap.add_argument("--title", default=None, help="标题后缀，默认＝summary 前 12 字")
    ap.add_argument("--kind", default="framework", choices=("framework", "personal"))
    ap.add_argument("--install", default=None, help="auto|manual|none，默认随 kind（framework→auto）")
    ap.add_argument("--tags", default="", help="逗号分隔，如 handoff,board")
    ap.add_argument("--source", default=None, help='裁决来源，格式 "路径|说明"')
    ap.add_argument("--since", default=None, help="起始版本，默认读 VERSION")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写盘")
    a = ap.parse_args()

    if not NAME_RE.match(a.name):
        return f"技能名不合法：{a.name}（只允许中英文、数字、- 与 _）"
    dest = os.path.join(ROOT, "skills", a.name)
    if os.path.exists(dest):
        return f"目录已存在：skills/{a.name}"

    today = dt.date.today().isoformat()
    install = a.install or ("auto" if a.kind == "framework" else "manual")
    if a.kind == "framework" and install != "auto":
        print(f"提示：框架件通常 install=auto，你给了 {install}（不进中央库）")
    since = a.since or (open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
                        if os.path.isfile(os.path.join(ROOT, "VERSION")) else "0.0.0")
    title = a.title or a.summary[:12]

    body = render(a.name, title, a.summary, a.source, today)
    if not a.dry_run:
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(body)
        entry = {
            "name": a.name, "path": f"skills/{a.name}", "kind": a.kind,
            "scope": "global" if a.kind == "framework" else "owner",
            "install": install, "summary": a.summary,
        }
        if a.tags:
            entry["tags"] = [t for t in a.tags.split(",") if t]
        entry["since"] = since
        entry, err = registry_add(entry, a.dry_run)
        if err:
            return err
    else:
        entry = {"name": a.name, "path": f"skills/{a.name}", "kind": a.kind, "install": install}

    print(f"已生成 skills/{a.name}/SKILL.md（frontmatter 八字段已填，approved/updated={today}）")
    print(f"registry 已登记：{json.dumps(entry, ensure_ascii=False)}")
    print("\n下一步：")
    print(f"  1. 编辑 skills/{a.name}/SKILL.md，把骨架里的 <...> 占位全替换掉")
    print("  2. python scripts/doctor.py    # 全绿才算加完")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
