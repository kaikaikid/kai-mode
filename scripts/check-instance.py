#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验项目仓里那份配置实例（schema 4）。

与 doctor 的 `config-instance` 分工：那一项实跑初始化器、校**新生成**的实例；本脚本校**盘上既有**的实例
（装机验收、迁移对账、日常改了实例之后跑一遍）。键口径直接 import doctor，不写第二把尺。

用法：
  python scripts/check-instance.py --repo <项目仓>
  python scripts/check-instance.py --repo <项目仓> --json     # 机器读（一份 JSON）

五条断言：
  ① 叶子键集与模板逐键相等（多一个少一个都算红）
  ② 零占位（值里没有 <尖括号>）
  ③ 零机器绝对路径（盘符 / UNC）
  ④ 登记落点逐个 stat：路径型键必须在盘上；门禁值按「脚本 + 子命令」解析后 stat 脚本；
     `issue.repo` 与 git remote 对账。按需生成的落点只提示不判红。
  ⑤ 日表对账：按 `day_table_pattern` + `lanes` 找文件——一个都匹配不上＝红（目录或 pattern 写错），
     匹配得上但今天没有＝提示（今天可能就是不排班）。

退出码：0 全绿（可含提示）／1 有红／2 缺件（仓根、实例或模板读不到）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TEMPLATE = os.path.join(ROOT, "templates", "kai-mode.project.json")
INSTANCE_REL = os.path.join(".ai", "kai-mode.project.json")

PATH_KEYS = (
    "paths.day_tables_dir", "paths.handoff_dir", "paths.ideas_dir", "paths.audit_dir",
    "paths.module_cards", "paths.dashboard",
    "registry.adrs.dir", "registry.rules.dir", "registry.skills.project_skills_dir",
)
ON_DEMAND_KEYS = ("paths.state_dir", "registry.skills.loop_dir")
# 问答答案型落点：刚装完还没建是正常的（塔台排班／地勤收想法时才生成），只提示不判红
PENDING_OK_KEYS = ("paths.day_tables_dir", "paths.ideas_dir", "paths.handoff_dir")
GATE_KEYS = ("gates.captain_preflight", "gates.scope_check", "gates.close_gate")
MAIN_TREE_REL_KEYS = ("runtime.backend_python.fallback.rel", "runtime.node.rel", "runtime.deps.check_dir_rel")
PLACEHOLDER = re.compile(r"<[^<>\n]{1,40}>")
MACHINE_PATH = re.compile(r"^([A-Za-z]:[\\/]|[\\\\]{2})")


def load_doctor():
    spec = importlib.util.spec_from_file_location("kai_doctor", os.path.join(HERE, "doctor.py"))
    mod = importlib.util.module_from_spec(spec)
    argv = sys.argv
    sys.argv = ["doctor.py"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = argv
    return mod


def getpath(node, dotted):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def git(repo, *args):
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def main_tree(repo):
    common = git(repo, "rev-parse", "--git-common-dir")
    if not common:
        return None
    common = common if os.path.isabs(common) else os.path.join(repo, common)
    return os.path.abspath(os.path.join(common, ".."))


class Report:
    def __init__(self):
        self.rows = []
        self.red = self.note = self.green = 0

    def add(self, level, text):
        self.rows.append((level, text))
        if level == "红":
            self.red += 1
        elif level == "注":
            self.note += 1
        else:
            self.green += 1

    def print(self):
        for level, text in self.rows:
            mark = {"绿": "[绿]", "红": "[红]", "注": "[注]"}[level]
            print(f"{mark} {text}")
        print(f"总结：绿 {self.green} ｜ 红 {self.red} ｜ 提示 {self.note}")


def main() -> int:
    ap = argparse.ArgumentParser(description="校验项目仓的配置实例")
    ap.add_argument("--repo", required=True, help="项目仓根")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    repo = os.path.abspath(a.repo)
    inst_path = os.path.join(repo, INSTANCE_REL)
    for label, path in (("项目仓根", repo), ("配置实例 " + INSTANCE_REL, inst_path), ("框架模板", TEMPLATE)):
        if not os.path.exists(path):
            print(f"[缺件] 缺什么：{label}｜谁需要：装机方与角色技能｜怎么补：确认路径，或在框架仓跑 scripts/init-project.py --repo <该仓>")
            return 2

    doc = load_doctor()
    with open(inst_path, encoding="utf-8") as f:
        cfg = json.load(f)
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = json.load(f)

    rep = Report()
    tkeys, ckeys = doc._cfg_leaves(tpl), doc._cfg_leaves(cfg)
    extra, missing = sorted(ckeys - tkeys), sorted(tkeys - ckeys)
    if extra or missing:
        rep.add("红", f"① 键集：模板 {len(tkeys)} ／ 实例 {len(ckeys)}；多 {extra}；少 {missing}")
    else:
        rep.add("绿", f"① 键集逐键相等（{len(ckeys)} 个叶子键，doctor._cfg_leaves 口径）")
    if cfg.get("schema") != tpl.get("schema"):
        rep.add("红", f"① schema：实例 {cfg.get('schema')!r} ≠ 模板 {tpl.get('schema')!r}")

    vals = doc._cfg_values(cfg)
    ph = [(p, v) for p, v in vals if isinstance(v, str) and PLACEHOLDER.search(v)]
    rep.add("红" if ph else "绿", f"② 占位值 {len(ph)} 处" + (f"：{ph[:4]}" if ph else ""))
    mp = [(p, v) for p, v in vals if isinstance(v, str) and MACHINE_PATH.match(v)]
    rep.add("红" if mp else "绿", f"③ 机器绝对路径 {len(mp)} 处" + (f"：{mp[:4]}" if mp else ""))

    statted = 0
    for key in PATH_KEYS:
        v = getpath(cfg, key)
        if not v:
            rep.add("注", f"④ {key} = null（如实缺件，读取端会点名报缺）")
            continue
        p = os.path.join(repo, *str(v).split("/"))
        statted += 1
        if os.path.exists(p):
            rep.add("绿", f"④ {key} = {v}")
        elif key in PENDING_OK_KEYS:
            rep.add("注", f"④ {key} = {v}（尚未创建，按需生成）")
        else:
            rep.add("红", f"④ {key} = {v}（盘上没有）")
    for key in ON_DEMAND_KEYS:
        v = getpath(cfg, key)
        if v:
            p = os.path.join(repo, *str(v).split("/"))
            rep.add("绿" if os.path.exists(p) else "注",
                    f"④ {key} = {v}" + ("（按需生成，尚未创建）" if not os.path.exists(p) else ""))
    for key in GATE_KEYS:
        v = getpath(cfg, key)
        if not v:
            rep.add("注", f"④ {key} = null（本项目无此门）")
            continue
        script = str(v).split()[0]
        p = os.path.join(repo, *script.split("/"))
        statted += 1
        rep.add("绿" if os.path.isfile(p) else "红",
                f"④ {key} = {v}" + ("（脚本在盘上）" if os.path.isfile(p) else f"（脚本 {script} 不在盘上）"))
    tree = main_tree(repo)
    for key in MAIN_TREE_REL_KEYS:
        v = getpath(cfg, key)
        if not v:
            continue
        if not tree:
            rep.add("注", f"④ {key} = {v}（解析不出主树，跳过 stat）")
            continue
        p = os.path.join(tree, *str(v).split("/"))
        rep.add("绿" if os.path.exists(p) else "注",
                f"④ {key} = {v}" + ("" if os.path.exists(p) else "（主树上没有；工作树里本就无运行时，按缺件登记）"))

    if getpath(cfg, "issue.platform") == "github" and getpath(cfg, "issue.repo"):
        url = git(repo, "remote", "get-url", "origin")
        m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
        slug = m.group(1) if m else ""
        want = str(getpath(cfg, "issue.repo"))
        rep.add("绿" if slug.lower() == want.lower() else "红",
                f"④ issue.repo = {want}" + (f"（git remote 一致：{slug}）" if slug.lower() == want.lower()
                                            else f"（git remote 是 {slug or '解析不出'}）"))

    dtd = getpath(cfg, "paths.day_tables_dir")
    pat = getpath(cfg, "paths.day_table_pattern")
    lanes = getpath(cfg, "paths.lanes") or []
    known_lanes = ("main", "deputy", "second", "ace")
    if lanes:
        unknown = [x for x in lanes if x not in known_lanes]
        if unknown:
            rep.add("红", f"⑤ paths.lanes 有不认识的道：{unknown}（只认 main/deputy/second/ace）")
        if "main" not in lanes:
            rep.add("红", "⑤ paths.lanes 必须含 main（主机长道是兜底，关掉它排班无处可去）")
    if dtd and pat and lanes:
        d = os.path.join(repo, *str(dtd).split("/"))
        if not os.path.isdir(d):
            rep.add("注", f"⑤ 日表：{dtd} 尚未创建（塔台排班时生成，pattern {pat} 暂无从验证）")
        else:
            names = os.listdir(d)
            rx = re.compile("^" + re.escape(str(pat)).replace(re.escape("YYYY"), r"\d{4}")
                            .replace(re.escape("MM"), r"\d{2}").replace(re.escape("DD"), r"\d{2}")
                            .replace(re.escape("{lane}"), "(" + "|".join(re.escape(str(x)) for x in lanes) + ")")
                            .replace(re.escape("*"), r"[^/]*") + "$")
            matched = [n for n in names if rx.match(n)]
            today = dt.date.today().strftime("%Y-%m-%d")
            todays = [n for n in matched if n.startswith(today)]
            if not matched:
                rep.add("红", f"⑤ 日表：{dtd} 下 {len(names)} 个文件，按 pattern {pat}＋lanes {lanes} 匹配上 0 个（目录或 pattern 写错）")
            elif not todays:
                rep.add("注", f"⑤ 日表：pattern 匹配上 {len(matched)} 个，今天（{today}）没有——塔台排班后才有")
            else:
                rep.add("绿", f"⑤ 日表：匹配 {len(matched)} 个，今天 {len(todays)} 张（{', '.join(sorted(todays))}）")
            statted += len(matched)

    if a.json:
        print(json.dumps({"repo": repo, "red": rep.red, "note": rep.note, "green": rep.green,
                          "rows": [{"level": lv, "text": tx} for lv, tx in rep.rows]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"实例 {os.path.relpath(inst_path, repo)}（schema {cfg.get('schema')}）；stat 过 {statted} 个落点")
        rep.print()
    return 1 if rep.red else 0


if __name__ == "__main__":
    raise SystemExit(main())
