#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卸载 V1（机场体系）技能：探测 → 退役 → 复核 → 回执。

判据住本脚本，技能正文只写流程位。复用 magpie-sync 的库定位、落点面、
退役与注册档函数，不写第二把尺。

用法（在框架仓或任意目录跑）：
  python uninstall-v1.py                     # 只读探测，出下线清单
  python uninstall-v1.py --apply             # 退役：库目录→.retired、摘宿主链、清注册档
  python uninstall-v1.py --repo <项目仓>      # 顺带扫项目实例/自动化里的 V1 残留
  python uninstall-v1.py --json              # 机器读

退出码：0 全绿（可含待人工项）／1 失败／2 缺件。

边界（红线邻面，默认不动）：
- 宿主落点里的**实体目录**（非符号链接）只报告，不删不移；
- 宿主定时任务 / automation 只报告，不停用不删除；
- 项目配置实例的 V1 键只报告，迁移走 set-kai-mode 的 schema 迁移腿。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SYNC = os.path.join(HERE, "magpie-sync.py")

V1_SKILLS = ("ace", "copilot", "ground-crew", "loop", "pilot", "second-officer", "tower")
RETIRED_DIR = ".retired"


def load_sync():
    spec = importlib.util.spec_from_file_location("kai_magpie_sync", SYNC)
    if spec is None or spec.loader is None:
        raise SystemExit(f"读不到 magpie-sync.py：{SYNC}")
    mod = importlib.util.module_from_spec(spec)
    argv = sys.argv
    sys.argv = [SYNC]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = argv
    return mod


def probe(sync, library: str, home: str | None, repo: str | None) -> dict:
    faces = sync.find_faces(library, home)
    reg, err = sync.read_registry(library)
    reg_names = set()
    if isinstance(reg, dict):
        reg_names = {s.get("name") for s in reg.get("skills", []) if isinstance(s, dict)}
        for val in (reg.get("applied") or {}).values():
            if isinstance(val, dict):
                reg_names |= set(val.get("skills") or [])

    skills = []
    for name in V1_SKILLS:
        lib_dir = os.path.join(library, name)
        links, entities = [], []
        for face in faces:
            p = os.path.join(face, name)
            if not os.path.lexists(p):
                continue
            if os.path.islink(p):
                links.append(p)
            elif os.path.isdir(p):
                entities.append(p)
        skills.append({
            "name": name,
            "library_dir": lib_dir if os.path.isdir(lib_dir) else None,
            "registry": name in reg_names,
            "links": links,
            "entity_dirs": entities,
        })

    scheduled = scan_scheduled(home)
    project = scan_project(repo) if repo else []
    found = any(s["library_dir"] or s["registry"] or s["links"] or s["entity_dirs"] for s in skills)
    return {
        "library": library,
        "faces": faces,
        "registry_error": err,
        "skills": skills,
        "scheduled": scheduled,
        "project": project,
        "found": found,
    }


def scan_scheduled(home: str | None) -> list:
    """宿主自动化里的 V1 塔台轮巡：只报告，不停用。"""
    home = home or os.path.expanduser("~")
    hits = []
    auto_root = os.path.join(home, ".codex", "automations")
    if os.path.isdir(auto_root):
        for name in sorted(os.listdir(auto_root)):
            d = os.path.join(auto_root, name)
            toml = os.path.join(d, "automation.toml")
            if not os.path.isfile(toml):
                continue
            try:
                text = open(toml, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "tower" in text.lower() or "塔台" in text:
                hits.append({"kind": "codex-automation", "path": d, "how": "移到 .retired 或在宿主停用"})
    return hits


def scan_project(repo: str) -> list:
    """项目侧 V1 残留：配置实例的退役键、qoder 定时任务。只报告。"""
    hits = []
    inst = os.path.join(repo, ".ai", "kai-mode.project.json")
    if os.path.isfile(inst):
        try:
            cfg = json.load(open(inst, encoding="utf-8"))
        except (OSError, ValueError):
            cfg = {}
        retired = ("ship_mode", "paths.day_tables_dir", "paths.day_table_pattern", "paths.lanes",
                   "tower_cron", "issue.verdict_marker", "registry.skills.loop_dir",
                   "gates.captain_preflight", "gates.scope_check", "gates.close_gate")

        def _get(node, dotted):
            for part in dotted.split("."):
                if not isinstance(node, dict) or part not in node:
                    return None
                node = node[part]
            return node

        live = [k for k in retired if _get(cfg, k) is not None]
        if live:
            hits.append({"kind": "project-instance", "path": inst, "keys": live,
                         "how": "走 set-kai-mode 的 schema 迁移腿，逐键 diff 后升 schema 5"})
    qoder = os.path.join(repo, ".qoder", "scheduled_tasks.json")
    if os.path.isfile(qoder):
        try:
            text = open(qoder, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        if "tower" in text.lower() or "塔台" in text:
            hits.append({"kind": "qoder-scheduled", "path": qoder,
                         "how": "在宿主停用或删除该任务"})
    return hits


def apply_retire(sync, library: str, names: list, home: str | None, rep: dict) -> dict:
    backup = sync.backup_library(library)
    removed, moved, unlinked, skipped = [], [], [], []
    present = [n for n in names
               if os.path.isdir(os.path.join(library, n))
               or _in_registry(sync, library, n)]
    if present:
        removed = sync.retire_registry_entries(library, present)
        moved, unlinked, skipped = sync.retire_names(library, present, home, dry=False)
    receipt = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "retired": present,
        "registry_removed": removed,
        "moved": moved,
        "unlinked": unlinked,
        "skipped": skipped,
        "backup": backup,
        "entity_dirs_left": [p for s in rep["skills"] for p in s["entity_dirs"]],
        "scheduled_left": rep["scheduled"],
        "project_left": rep["project"],
    }
    out = os.path.join(sync.library_root(library), RETIRED_DIR,
                       "uninstall-v1-" + time.strftime("%Y%m%d-%H%M%S") + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write("\n")
    receipt["receipt"] = out
    return receipt


def _in_registry(sync, library: str, name: str) -> bool:
    reg, _ = sync.read_registry(library)
    if not isinstance(reg, dict):
        return False
    names = {s.get("name") for s in reg.get("skills", []) if isinstance(s, dict)}
    for val in (reg.get("applied") or {}).values():
        if isinstance(val, dict):
            names |= set(val.get("skills") or [])
    return name in names


def verify(sync, library: str, home: str | None) -> list:
    """复核：V1 名字不应再出现在库目录、注册档与任何宿主链接里。"""
    bad = []
    for name in V1_SKILLS:
        if os.path.isdir(os.path.join(library, name)):
            bad.append(f"库目录仍在：{name}")
        if _in_registry(sync, library, name):
            bad.append(f"注册档仍在：{name}")
        for face in sync.find_faces(library, home):
            p = os.path.join(face, name)
            if os.path.islink(p):
                bad.append(f"宿主链接仍在：{p}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="卸载 V1（机场体系）技能")
    ap.add_argument("--apply", action="store_true", help="执行退役（缺省只读探测）")
    ap.add_argument("--library", help="中央库 skills 目录（缺省沿 kai-mode 链接反查）")
    ap.add_argument("--home", help="宿主家目录（缺省 ~）")
    ap.add_argument("--repo", help="项目仓根：顺带扫配置实例与定时任务里的 V1 残留")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sync = load_sync()
    home = a.home
    library = a.library or sync.find_library(home)
    if not library:
        print("缺件：读不出中央库（设 KAI_MAGPIE_LIBRARY 或 --library）｜"
              "谁需要：卸载 V1 的探测与退役｜怎么补：指向 <...>/library/skills")
        return 2
    if not os.path.isdir(library):
        print(f"缺件：库目录不存在：{library}")
        return 2

    rep = probe(sync, library, home, a.repo)
    if a.json and not a.apply:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["found"] or rep["scheduled"] or rep["project"] else 0

    lines = [f"库={rep['library']}  宿主落点面={len(rep['faces'])} 家"]
    for s in rep["skills"]:
        parts = []
        if s["library_dir"]:
            parts.append("库目录")
        if s["registry"]:
            parts.append("注册档")
        if s["links"]:
            parts.append(f"链接×{len(s['links'])}")
        if s["entity_dirs"]:
            parts.append(f"实体目录×{len(s['entity_dirs'])}（不动，要人拍）")
        lines.append(f"  {s['name']:<14} {'、'.join(parts) if parts else '—'}")
    for h in rep["scheduled"] + rep["project"]:
        lines.append(f"  [待人工] {h['kind']}: {h['path']}  → {h.get('how', '')}")
    if rep["registry_error"]:
        lines.append(f"  [注] 注册档：{rep['registry_error']}")

    if not a.apply:
        lines.append("（只读探测；加 --apply 执行退役）")
        print("\n".join(lines))
        return 0

    present = [s["name"] for s in rep["skills"]
               if s["library_dir"] or s["registry"] or s["links"]]
    if not present:
        lines.append("没有可退役的 V1 技能（可能已卸载）")
        print("\n".join(lines))
        return 0
    receipt = apply_retire(sync, library, present, home, rep)
    if a.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        lines.append(f"回执 {receipt['receipt']}")
    bad = verify(sync, library, home)
    if bad:
        lines.append("复核有残留：" + "；".join(bad))
        print("\n".join(lines))
        return 1
    lines.append("复核通过：库目录、注册档、宿主链接里都没有 V1 技能了")
    if not a.json:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
