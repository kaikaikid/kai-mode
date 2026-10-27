#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新技能脚手架 —— 别手写 frontmatter，跑这个。
================================================
干两件事：复制骨架模板 → 填 frontmatter 八字段 → 放进指定插件的 skills/ 目录。
插件的技能清单由目录现场派生，不再维护 registry。

用法：
  python scripts/new-skill.py <技能名> --summary "一句话：这个技能干什么"
                              [--plugin core] [--title "标题后缀"]
                              [--source "路径|说明"] [--dry-run]

约定：
  · 目录名＝技能名＝frontmatter name（三处一致，doctor 会查）
  · 放哪：<plugin>/skills/<名>/SKILL.md；插件必须是 marketplace.json 里已有的
  · 生成后照骨架里的 `<...>` 占位补全正文，再跑 plugin-check 与 doctor 到绿
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TPL = os.path.join(ROOT, "templates", "skill", "SKILL.md")
MARKET = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
NAME_RE = re.compile(r"^[A-Za-z0-9一-龥][A-Za-z0-9一-龥_-]*$")


def plugins() -> list:
    with open(MARKET, encoding="utf-8") as f:
        data = json.load(f)
    return [p.get("name") for p in data.get("plugins") or [] if isinstance(p, dict)]


def render(name, title, summary, source, today):
    with open(TPL, encoding="utf-8") as f:
        text = f.read()
    text = text.replace("<技能名> —— <一句话定位>", f"{name} —— {title}")
    text = text.replace("<技能名>", name)
    text = text.replace("<YYYY-MM-DD>", today)
    if source:
        res, _, note = source.partition("|")
        old = ('sources:\n'
               '  - resource: "项目配置实例 registry.adrs.dir 指向的 ADR（ADR-xxxx-<裁决名>）"\n'
               '    note: "裁决来源：这份技能凭什么这么定；落点读项目配置实例（ADR-0004 D2），读不到实例 ⇒ 按 D4 报缺件"')
        text = text.replace(old, f'sources:\n  - resource: "{res.strip()}"\n    note: "{note.strip() or "裁决来源"}"')
    else:
        text = re.sub(r"sources:\n(?:  - resource:.*\n    note:.*\n)+", "sources: []\n", text)
    old_desc = ("description: >\n"
                "  一句话：做什么 / 不做什么 / 触发词。\n"
                "  触发：<触发口令或自然语言关键词>。")
    text = text.replace(old_desc,
                        f"description: >\n  {summary}\n  触发：<触发口令或自然语言关键词>。")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description="新技能脚手架（骨架 + frontmatter，放指定插件）")
    ap.add_argument("name", help="技能名＝目录名（kebab-case 英文优先）")
    ap.add_argument("--summary", required=True, help="一句话：这个技能干什么")
    ap.add_argument("--plugin", default="core", help="放进哪个插件（默认 core）")
    ap.add_argument("--title", default=None, help="标题后缀，默认＝summary 前 12 字")
    ap.add_argument("--source", default=None, help='出处，格式 "路径|说明"')
    ap.add_argument("--dry-run", action="store_true", help="只打印不写盘")
    a = ap.parse_args()

    if not NAME_RE.match(a.name):
        return f"技能名不合法：{a.name}（只允许中英文、数字、- 与 _）"
    known = plugins()
    if a.plugin not in known:
        return f"插件不存在：{a.plugin}（可选：{', '.join(known)}）"
    dest = os.path.join(ROOT, a.plugin, "skills", a.name)
    if os.path.exists(dest):
        return f"目录已存在：{a.plugin}/skills/{a.name}"

    today = dt.date.today().isoformat()
    title = a.title or a.summary[:12]
    body = render(a.name, title, a.summary, a.source, today)
    rel = f"{a.plugin}/skills/{a.name}/SKILL.md"
    if not a.dry_run:
        os.makedirs(dest, exist_ok=True)
        with open(os.path.join(dest, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(body)

    print(f"已生成 {rel}（frontmatter 八字段已填，approved/updated={today}）")
    print("\n下一步：")
    print(f"  1. 编辑 {rel}，把骨架里的 <...> 占位全替换掉")
    print("  2. python scripts/plugin-check.py --bump   # 刷新版本/摘要锁")
    print("  3. python scripts/doctor.py                # 全绿才算加完")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
