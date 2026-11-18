#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验冒险者地图（map.json）。

地图住数据根（<KAI_AGENT_DATA_ROOT>/kai-mode/map.json，untracked）；schema 与模板住框架仓。
本脚本只校**盘上既有**的地图：schema 形状、地区路径与入口落点、region-id 唯一。

用法：
  python scripts/map-check.py                        # 读 $KAI_AGENT_DATA_ROOT/kai-mode/map.json
  python scripts/map-check.py --map <map.json>
  python scripts/map-check.py --map <map.json> --json

校验项：
  ① schema：JSON Schema 2020-12（schemas/map.schema.json）逐条校验
  ② region-id / aliases 唯一（含与 id 的跨列冲突）
  ③ 每个地区的 path 存在且是目录；instance、guide 相对仓根解析后存在、不越出仓根
  ④ 攻略章节：guide.schema.json 的 x-guide-sections 逐节找 `## <title>`；缺节只提示
  ⑤ remote / default_branch 与 git 对账；只有 git 可读时才校，失配只提示

退出码：0 全绿（可含提示）／1 有红／2 缺件或无法解析（地图、schema、坏 JSON）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
MAP_SCHEMA = os.path.join(ROOT, "schemas", "map.schema.json")
GUIDE_SCHEMA = os.path.join(ROOT, "schemas", "guide.schema.json")
REGION_ID = re.compile(r"^[a-z][a-z0-9-]*$")


def default_map_path() -> str | None:
    root = os.environ.get("KAI_AGENT_DATA_ROOT")
    return os.path.join(root, "kai-mode", "map.json") if root else None


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def git(repo: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                             timeout=20, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def schema_errors(doc, schema) -> list[str]:
    """返回人读的错误列表；jsonschema 缺席时由调用方先拦。"""
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema)
    errs = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "<根>"
        errs.append(f"{where}: {err.message}")
    return errs


def inside(repo: str, rel: str) -> str | None:
    """relative → 绝对路径；越出仓根返回 None。"""
    if not isinstance(rel, str) or not rel:
        return None
    target = os.path.abspath(os.path.join(repo, *rel.replace("\\", "/").split("/")))
    try:
        if os.path.commonpath([repo, target]) != repo:
            return None
    except ValueError:
        return None
    return target


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str]] = []
        self.red = self.note = self.green = 0

    def add(self, level: str, text: str) -> None:
        self.rows.append((level, text))
        if level == "红":
            self.red += 1
        elif level == "注":
            self.note += 1
        else:
            self.green += 1

    def print(self) -> None:
        for level, text in self.rows:
            print(f"[{level}] {text}")
        print(f"总结：绿 {self.green} ｜ 红 {self.red} ｜ 提示 {self.note}")


def check(doc, map_schema, guide_sections) -> Report:
    rep = Report()

    errs = schema_errors(doc, map_schema)
    if errs:
        shown = "；".join(errs[:5]) + (f"（共 {len(errs)} 处）" if len(errs) > 5 else "")
        rep.add("红", f"① schema 不合规：{shown}")
    else:
        rep.add("绿", "① schema 合规（JSON Schema 2020-12，schemas/map.schema.json）")

    regions = doc.get("regions") if isinstance(doc, dict) else None
    if not isinstance(regions, list):
        rep.add("红", "① regions 不是数组，后续检查跳过")
        return rep

    seen: dict[str, str] = {}
    dup_ids, dup_alias = [], []
    for i, region in enumerate(regions):
        if not isinstance(region, dict):
            continue
        rid = region.get("id")
        if isinstance(rid, str):
            if rid in seen:
                dup_ids.append(rid)
            else:
                seen[rid] = f"regions[{i}]"
        aliases = region.get("aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                if not isinstance(alias, str):
                    continue
                if alias in seen and alias != rid:
                    dup_alias.append(f"{rid} 的别名 {alias} 撞了地区 {seen[alias]}")
                elif alias in seen:
                    dup_alias.append(f"{rid} 的别名与自身 id 重复")
                else:
                    seen[alias] = f"regions[{i}].aliases"
    if dup_ids or dup_alias:
        parts = []
        if dup_ids:
            parts.append("重复 region-id：" + "、".join(sorted(set(dup_ids))))
        if dup_alias:
            parts.append("别名冲突：" + "；".join(dup_alias))
        rep.add("红", "② " + "；".join(parts))
    else:
        rep.add("绿", f"② region-id 唯一（{len(regions)} 个地区，含别名去重）")

    for i, region in enumerate(regions):
        if not isinstance(region, dict):
            continue
        rid = region.get("id", f"regions[{i}]")
        repo = region.get("path")
        if not isinstance(repo, str) or not repo:
            rep.add("红", f"③ {rid}：path 缺失")
            continue
        if not os.path.isdir(repo):
            rep.add("红", f"③ {rid}：path 不存在或不是目录：{repo}")
            continue
        rep.add("绿", f"③ {rid}：path 在盘上：{repo}")

        for key in ("instance", "guide"):
            rel = region.get(key)
            target = inside(repo, rel) if isinstance(rel, str) else None
            if target is None:
                rep.add("红", f"③ {rid}：{key} = {rel!r} 不是仓内相对路径")
            elif not os.path.isfile(target):
                rep.add("红", f"③ {rid}：{key} = {rel} 不在盘上")
            else:
                rep.add("绿", f"③ {rid}：{key} = {rel}")

        guide_rel = region.get("guide")
        guide_path = inside(repo, guide_rel) if isinstance(guide_rel, str) else None
        if guide_path and os.path.isfile(guide_path) and guide_sections:
            try:
                with open(guide_path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                text = ""
            missing = [s["title"] for s in guide_sections
                       if s.get("required", True) and f"## {s['title']}" not in text]
            if missing:
                rep.add("注", f"④ {rid}：GUIDE 缺章节（只提示，不判红）：" + "、".join(missing))
            else:
                rep.add("绿", f"④ {rid}：GUIDE 章节齐全（{len(guide_sections)} 节）")

        if os.path.isdir(os.path.join(repo, ".git")):
            remote = region.get("remote")
            actual = git(repo, "remote", "get-url", "origin")
            if isinstance(remote, str) and remote and actual and remote != actual:
                rep.add("注", f"⑤ {rid}：remote 记录 {remote}，git origin 是 {actual}（只提示）")
            branch = region.get("default_branch")
            if isinstance(branch, str) and branch:
                found = git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}") or \
                    git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
                if not found:
                    rep.add("注", f"⑤ {rid}：default_branch = {branch} 在本地/远端分支里没找到（只提示）")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="校验冒险者地图 map.json")
    ap.add_argument("--map", help="地图路径；缺省读 $KAI_AGENT_DATA_ROOT/kai-mode/map.json")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    map_path = a.map or default_map_path()
    if not map_path:
        print("[缺件] 缺什么：地图路径｜谁需要：map-check｜怎么补：设 KAI_AGENT_DATA_ROOT，或用 --map <map.json>")
        return 2
    map_path = os.path.abspath(map_path)
    for label, path in (("地图 map.json", map_path), ("地图 schema", MAP_SCHEMA), ("攻略 schema", GUIDE_SCHEMA)):
        if not os.path.exists(path):
            print(f"[缺件] 缺什么：{label}（{path}）｜谁需要：map-check｜怎么补：确认数据根/框架仓路径")
            return 2

    try:
        map_schema = load_json(MAP_SCHEMA)
        guide_schema = load_json(GUIDE_SCHEMA)
    except (OSError, ValueError) as exc:
        print(f"[缺件] 缺什么：schema 可解析｜怎么补：修 {MAP_SCHEMA} 或 {GUIDE_SCHEMA}：{exc}")
        return 2
    try:
        with open(map_path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"[缺件] 缺什么：地图 JSON 可解析（{map_path}）｜怎么补：修 JSON 语法：{exc}")
        return 2

    try:
        rep = check(doc, map_schema, guide_schema.get("x-guide-sections", []))
    except ImportError:
        print("[缺件] 缺什么：jsonschema 包｜谁需要：map-check｜怎么补：pip install jsonschema")
        return 2

    if a.json:
        print(json.dumps({"map": map_path, "red": rep.red, "note": rep.note, "green": rep.green,
                          "rows": [{"level": lv, "text": tx} for lv, tx in rep.rows]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"地图 {map_path}（schema {doc.get('schema') if isinstance(doc, dict) else '?'}）")
        rep.print()
    return 1 if rep.red else 0


if __name__ == "__main__":
    raise SystemExit(main())
