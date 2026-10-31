#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成使用手册的技能数据
========================
用法：
    python scripts/manual-gen.py

做三件事：
  1. 从 marketplace.json 取插件顺序，从各插件 skills/*/SKILL.md 取技能名、版本、描述；
  2. 从各插件 commands/*.md 反查技能对应的斜杠命令；
  3. 读 manual/skills-plain.json 的人话覆盖，写出 manual/assets/skills-data.js。

输出只有数据，页面壳与侧栏在 manual/ 下手写；不联网、不装依赖。
技能数与 plugins.lock.json 不一致时返回 1，提醒先修清单。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
LOCK = ROOT / "manifests" / "plugins.lock.json"
PLAIN = ROOT / "manual" / "skills-plain.json"
OUT = ROOT / "manual" / "assets" / "skills-data.js"

# 没有 commands/ 的插件里，这些技能本身就是口令
SELF_COMMAND_SKILLS = {
    "bridge",
    "producer",
    "lead-writer",
    "lead-artist",
    "director",
    "final-review",
    "marketing",
}

GROUP_BY_PLUGIN = {
    "core": "舰桥与安装",
    "v2": "执行内核",
    "methods": "方法库",
    "studio": "文娱集团",
    "intake": "支持能力",
    "ops": "支持能力",
    "board": "支持能力",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    if not match:
        return {}
    data: dict[str, str] = {}
    key = None
    buffer: list[str] = []
    for line in match.group(1).splitlines():
        top = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
        if top:
            if key is not None:
                data[key] = "\n".join(buffer).strip()
            key = top.group(1)
            buffer = [top.group(2).strip()]
        elif key is not None:
            buffer.append(line)
    if key is not None:
        data[key] = "\n".join(buffer).strip()
    return data


def clean_text(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"^[>|]\s*", "", value)
    value = value.replace("**", "").replace("`", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def first_sentence(value: str, limit: int = 110) -> str:
    value = clean_text(value)
    if not value:
        return ""
    parts = re.split(r"(?<=[。！？；])", value)
    sentence = parts[0].strip()
    if len(sentence) > limit:
        sentence = sentence[:limit].rstrip("，,、；; ") + "…"
    return sentence


def extract_trigger(description: str) -> str:
    match = re.search(r"触发[：:]\s*(.+)", description)
    if not match:
        return ""
    trigger = re.split(r"[。]", match.group(1))[0]
    trigger = clean_text(trigger)
    if len(trigger) > 90:
        trigger = trigger[:90].rstrip("，,、；; ") + "…"
    return trigger


def command_map(plugin_dir: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    commands_dir = plugin_dir / "commands"
    if not commands_dir.is_dir():
        return mapping
    for command_file in sorted(commands_dir.glob("*.md")):
        text = read_text(command_file)
        match = re.search(r"skills/([A-Za-z0-9_-]+)/SKILL\.md", text)
        if match:
            mapping.setdefault(match.group(1), "/" + command_file.stem)
    return mapping


def main() -> int:
    marketplace = json.loads(read_text(MARKETPLACE))
    lock = json.loads(read_text(LOCK))
    plain = json.loads(read_text(PLAIN)) if PLAIN.exists() else {}

    rows = []
    missing_plain = []

    for plugin in marketplace["plugins"]:
        plugin_dir = ROOT / plugin["source"].lstrip("./")
        skills_dir = plugin_dir / "skills"
        if not skills_dir.is_dir():
            continue
        commands = command_map(plugin_dir)

        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            front = parse_frontmatter(read_text(skill_file))
            skill = clean_text(front.get("name", "")) or skill_dir.name
            version = clean_text(front.get("version", ""))
            description = front.get("description", "")

            override = plain.get(skill)
            if isinstance(override, str):
                override = {"oneLine": override}
            if not isinstance(override, dict):
                override = {}
                missing_plain.append(skill)

            one_line = override.get("oneLine") or first_sentence(description)
            trigger = override.get("trigger") or extract_trigger(description)

            command = commands.get(skill, "")
            if not command and skill in SELF_COMMAND_SKILLS:
                command = "/" + skill
            if not command and skill == "harness-audit":
                command = "手动技能"
            if not trigger:
                if skill == "coding":
                    trigger = "由舰桥触发 /jump"
                elif skill == "studio":
                    trigger = "随六个创作口令自动带入"
                elif skill.startswith("principle-"):
                    trigger = "自动带入"
                else:
                    trigger = "—"

            rows.append(
                {
                    "group": GROUP_BY_PLUGIN.get(plugin["name"], "支持能力"),
                    "plugin": plugin.get("displayName", plugin["name"]),
                    "pluginId": plugin["name"],
                    "skill": skill,
                    "oneLine": one_line,
                    "trigger": trigger,
                    "command": command,
                    "version": version,
                }
            )

    expected = sum(len(item["skills"]) for item in lock["plugins"].values())
    if len(rows) != expected:
        print(
            f"技能数不一致：生成 {len(rows)} 条，锁文件 {expected} 条；"
            "先跑 python scripts/plugin-check.py --bump 或修清单。",
            file=sys.stderr,
        )
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    OUT.write_text(
        "/* 自动生成：python scripts/manual-gen.py；不要手改。 */\n"
        "window.KAI_SKILLS = " + payload + ";\n",
        encoding="utf-8",
    )

    if missing_plain:
        print("没有手写人话、暂用 description 首句的技能：")
        for name in missing_plain:
            print("  -", name)
    print(
        f"写入 {OUT.relative_to(ROOT)}：{len(rows)} 个技能"
        f"（插件 {len(marketplace['plugins'])} 个）。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
