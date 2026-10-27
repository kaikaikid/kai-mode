#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kai-mode 装到别的项目：QA 初始化
==================================
一串问答 → 生成 `<目标仓>/.ai/kai-mode.project.json`（schema 4 实例）＋ 铺两个组件
（`handoff/` 交接与角色沟通面、`docs/` 长期正本面）。

用法：
  python scripts/init-project.py --repo <目标仓>              # 逐题问（每題有默认，回车即默认）
  python scripts/init-project.py --repo <目标仓> --yes        # 全默认，不提问
  python scripts/init-project.py --repo <目标仓> --answers a.json   # 机器填（CI/批处理）
  python scripts/init-project.py --repo <目标仓> --dry-run     # 只打印结果不写盘

十问（顺序固定，缺一不可）：
  1 项目名 2 票源 3 仓库 slug 4 日表目录 5 交接目录 6 想法目录
  7 ADR 目录 8 宿主 9 收工门禁脚本 10 想法池汇总票号
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
LAYOUT = os.path.join(ROOT, "manifests", "package-layout.json")
LAYOUT_SCHEMA = "kai-mode-package-layout/1"


def load_layout() -> dict:
    """项目骨架面的唯一清单：生成什么、从哪份源复制，只认 manifests/package-layout.json。"""
    try:
        with open(LAYOUT, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"读不出项目骨架清单 {LAYOUT}：{exc}")
    if not isinstance(data, dict) or data.get("schema") != LAYOUT_SCHEMA:
        raise SystemExit(f"{LAYOUT} schema 不是 {LAYOUT_SCHEMA}")
    spec = data.get("project_scaffold")
    if not isinstance(spec, dict):
        raise SystemExit(f"{LAYOUT} 缺 project_scaffold")
    return data


def guess_slug(repo: str) -> str:
    try:
        out = subprocess.run(["git", "-C", repo, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", out)
    return m.group(1) if m else ""


def ask(q: str, default: str, yes: bool) -> str:
    if yes:
        return default
    shown = f"{q} [{default}]: " if default else f"{q}: "
    try:
        v = input(shown).strip()
    except EOFError:
        v = ""
    return v or default


def safe_rel(value: str, field: str) -> str:
    """实例里的落点必须是仓内相对路径；`..` 与绝对路径直接拒绝（不写出仓外）。"""
    raw = str(value or "").strip()
    if not raw:
        return raw
    norm = os.path.normpath(raw)
    if os.path.isabs(norm) or norm == ".." or norm.startswith(".." + os.sep):
        raise SystemExit(f"{field} 必须是仓内相对路径，读到 {value!r}")
    return norm.replace(os.sep, "/")


def normalize_answers(ans: dict) -> dict:
    for key in ("day_tables_dir", "handoff_dir", "ideas_dir", "adr_dir", "preflight_gate"):
        if ans.get(key):
            ans[key] = safe_rel(ans[key], key)
    return ans


def build_answers(repo: str, a, yes: bool) -> dict:
    if a.answers:
        with open(a.answers, encoding="utf-8") as f:
            return json.load(f)
    auto_slug = guess_slug(repo)
    return {
        "project": ask("1/10 项目名", os.path.basename(os.path.abspath(repo)), yes),
        "ticket_source": ask("2/10 票源（github / none）", "github", yes),
        "repo_slug": ask("3/10 仓库 slug（owner/name，none 可留空）", auto_slug, yes),
        "day_tables_dir": ask("4/10 日表目录", ".ai/tasks", yes),
        "handoff_dir": ask("5/10 交接目录", "handoff", yes),
        "ideas_dir": ask("6/10 想法目录", "ideas", yes),
        "adr_dir": ask("7/10 ADR 目录", "docs/adr", yes),
        "host": ask("8/10 宿主（qoder / codex / opencode / claude / copilot / cursor）— 回车＝本机当前宿主，不确定就填你实际在用的那一个", "", yes),
        "preflight_gate": ask("9/10 收工门禁脚本（相对仓根；本项目没有就回车留 null，别抄别仓的门名）",
                             "", yes),
        "boom_summary_ticket": ask("10/10 想法池汇总票号（可留空）", "", yes),
    }


def drop_placeholders(node, path=""):
    """占位不落盘：值里还带 <尖括号> 的字段（＝没问出答案）一律改 null，返回被抹的键路径。"""
    wiped = []
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if str(k).startswith("_"):
                continue
            p = f"{path}.{k}" if path else str(k)
            if isinstance(v, str) and "<" in v and ">" in v:
                node[k] = None
                wiped.append(p)
            else:
                wiped.extend(drop_placeholders(v, p))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str) and "<" in v and ">" in v:
                node[i] = None
                wiped.append(f"{path}[{i}]")
            else:
                wiped.extend(drop_placeholders(v, f"{path}[{i}]"))
    return wiped


GUESS_PATHS = (  # 模板缺省＝框架猜测，不是问答答案：盘上没有就 null，别把猜测写成项目事实
    ("registry.rules.dir", "repo"),
    ("registry.skills.project_skills_dir", "repo"),
    ("registry.skills.loop_dir", "repo"),
    ("runtime.deps.check_dir_rel", "repo"),
    ("runtime.backend_python.fallback.rel", "main_tree"),
    ("runtime.node.rel", "main_tree"),
)
ON_DEMAND_PATHS = (  # 问答答案或框架自有命名空间：现在没有是正常的，按需生成，不抹成 null
    "paths.day_tables_dir", "paths.handoff_dir", "paths.ideas_dir", "paths.state_dir",
)


def _getpath(node, dotted):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _setpath(node, dotted, value):
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def main_tree_of(repo: str):
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "--git-common-dir"],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    common = out.stdout.strip()
    common = common if os.path.isabs(common) else os.path.join(repo, common)
    return os.path.abspath(os.path.join(common, ".."))


def resolve_guesses(cfg: dict, repo: str):
    """模板猜测型落点按盘上实情核实：不存在 ⇒ null。返回 (转 null 的, 按需生成还没建的)。"""
    tree = main_tree_of(repo)
    nulled, pending = [], []
    for dotted, kind in GUESS_PATHS:
        value = _getpath(cfg, dotted)
        if not isinstance(value, str) or not value.strip():
            continue
        base = tree if kind == "main_tree" else repo
        if not base:
            _setpath(cfg, dotted, None)
            nulled.append(f"{dotted}（解析不出主树）")
            continue
        if not os.path.exists(os.path.join(base, *value.split("/"))):
            _setpath(cfg, dotted, None)
            nulled.append(f"{dotted}={value}")
    for dotted in ON_DEMAND_PATHS:
        value = _getpath(cfg, dotted)
        if isinstance(value, str) and value.strip():
            if not os.path.exists(os.path.join(repo, *value.split("/"))):
                pending.append(f"{dotted}={value}")
    return nulled, pending


def apply(cfg: dict, ans: dict) -> dict:
    cfg["project"] = ans.get("project") or cfg.get("project")
    cfg["ship_mode"] = "tower"
    reg = cfg.setdefault("registry", {})
    reg.setdefault("adrs", {})["dir"] = ans.get("adr_dir") or "docs/adr"
    paths = cfg.setdefault("paths", {})
    paths["day_tables_dir"] = ans.get("day_tables_dir") or ".ai/tasks"
    paths["day_table_pattern"] = "YYYY-MM-DD-{lane}.md"
    paths["lanes"] = ["main", "deputy", "ace"]
    paths["handoff_dir"] = ans.get("handoff_dir") or "handoff"
    paths["ideas_dir"] = ans.get("ideas_dir") or "ideas"
    gates = cfg.setdefault("gates", {})
    gate = (ans.get("preflight_gate") or "").strip()
    gates["captain_preflight"] = gate or None
    issue = cfg.setdefault("issue", {})
    issue["platform"] = "none" if ans.get("ticket_source") == "none" else "github"
    if ans.get("repo_slug"):
        issue["repo"] = ans["repo_slug"]
    ticket = str(ans.get("boom_summary_ticket") or ans.get("ideas_pool_issue") or "").strip()
    issue["boom_summary_ticket"] = ticket or None
    if ans.get("host"):
        cfg.setdefault("host", {})["adapter"] = ans["host"]
    return cfg


def project_has_own_handoff(base: str) -> bool:
    """项目已有自己的交接约定 ⇒ True：`<handoff>/README.md` 在、且没有「槽位表」。
    这种仓里铺框架八槽＝两套存放约定并存，还会撞它自己的提交门（实测：某仓把非 `templates`
    的子目录判为 problem 并硬拦）。判据只用一个词「槽位表」，与交接技能读的是同一张表。"""
    own = os.path.join(base, "README.md")
    if not os.path.isfile(own):
        return False
    try:
        with open(own, encoding="utf-8", errors="replace") as f:
            return "槽位表" not in f.read()
    except OSError:
        return False


def gen_handoff(repo: str, ans: dict, layout: dict) -> list:
    """铺交接组件：按清单的八槽 + 规范 + 模板；只复制列名件，历史记录一概不碰。"""
    import datetime as _dt
    done = []
    month = _dt.date.today().strftime("%Y-%m")
    spec = layout["project_scaffold"]["handoff"]
    base_rel = ans.get("handoff_dir") or "handoff"
    base = os.path.join(repo, base_rel)
    if project_has_own_handoff(base):
        print(f"[跳过交接骨架] {base_rel}/README.md 已在且没有槽位表 ⇒ 该仓有自己的交接约定，"
              f"不铺框架八槽（两套存放约定会打架，还可能被该仓自己的提交门硬拦）。"
              f"要用八槽：先在该 README 补 §2 槽位表，再重跑本初始化器。此处按缺件登记，不静默。")
        return []
    board_slot = spec["board_slot"]
    for slot in spec["slots"]:
        subs = spec["board_children"] if slot == board_slot else [month]
        for sub in subs:
            d = os.path.join(base, slot, sub)
            os.makedirs(d, exist_ok=True)
            keep = os.path.join(d, layout["project_scaffold"]["placeholder"])
            if not os.path.exists(keep):
                with open(keep, "w", encoding="utf-8", newline="") as f:
                    f.write(f"{slot}/{sub} 占位；规范见 {base_rel}/README.md\n")
    for src_rel, dst_rel in spec["files"].items():
        s = os.path.join(ROOT, *src_rel.split("/"))
        if not os.path.isfile(s):
            continue
        rel = base_rel + dst_rel[len("handoff"):] if dst_rel.startswith("handoff/") else dst_rel
        d = os.path.join(repo, *rel.split("/"))
        if os.path.exists(d):
            continue
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        done.append(rel)
    return done


def gen_docs(repo: str, ans: dict, layout: dict) -> list:
    """铺长期正本组件：空 ADR 目录（带占位）+ GLOSSARY.md 骨架（不覆盖已有的）。"""
    done = []
    spec = layout["project_scaffold"]
    adr_rel = ans.get("adr_dir") or spec["adr_dir"]
    adr_dir = os.path.join(repo, *adr_rel.split("/"))
    os.makedirs(adr_dir, exist_ok=True)
    keep = os.path.join(adr_dir, spec["placeholder"])
    # 已有 ADR 的仓（编号不从 0001 起）不写占位：那句「从 0001 起编号」在该仓是假话
    if not os.path.exists(keep) and not any(fn != spec["placeholder"] for fn in os.listdir(adr_dir)):
        with open(keep, "w", encoding="utf-8", newline="") as f:
            f.write("ADR 目录占位；从 0001 起编号。\n")
        done.append(f"{adr_rel}/{spec['placeholder']}")
    g_spec = spec["glossary"]
    g = os.path.join(repo, *g_spec["to"].split("/"))
    if not os.path.exists(g):
        src = os.path.join(ROOT, *g_spec["from"].split("/"))
        os.makedirs(os.path.dirname(g), exist_ok=True)
        shutil.copy2(src, g)
        done.append(g_spec["to"])
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description="kai-mode 装到别的项目：QA 初始化")
    ap.add_argument("--repo", required=True, help="目标仓根")
    ap.add_argument("--answers", default=None, help="答案 JSON 文件（跳过提问）")
    ap.add_argument("--yes", action="store_true", help="全默认，不提问")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写盘")
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    if not os.path.isdir(repo):
        print(f"目标仓不存在：{repo}")
        return 2
    layout = load_layout()
    spec = layout["project_scaffold"]
    cfg_src_rel = spec["config"]["from"]
    cfg_src = os.path.join(ROOT, *cfg_src_rel.split("/"))
    if not os.path.isfile(cfg_src):
        print(f"缺模板：{cfg_src_rel}（清单 {os.path.relpath(LAYOUT, ROOT)} 指的文件不在）")
        return 2

    ans = normalize_answers(build_answers(repo, a, a.yes))
    scaffold_sources = [cfg_src_rel, spec["glossary"]["from"], *spec["handoff"]["files"]]
    missing_src = [rel for rel in scaffold_sources
                   if not os.path.isfile(os.path.join(ROOT, *rel.split("/")))]
    if missing_src:
        print("缺件：框架仓项目骨架源件不全，未生成半成品实例：")
        for rel in missing_src:
            print(f"  - {rel}")
        return 2
    with open(cfg_src, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg = apply(cfg, ans)
    wiped = drop_placeholders(cfg)
    if wiped:
        print("占位没答上来，已按 null 落盘（读取端会如实报缺件，不猜路径）：" + "、".join(wiped))
    nulled, pending = resolve_guesses(cfg, repo)
    if nulled:
        print("盘上没有的模板缺省已按 null 落盘（框架猜测不冒充项目事实，读取端会如实报缺件）：" + "、".join(nulled))
    if pending:
        print("问答答案型落点尚未创建（按需生成，保留原值）：" + "、".join(pending))

    missing = []
    if not ans.get("project"):
        missing.append("项目名")
    if ans.get("ticket_source") == "github" and not ans.get("repo_slug"):
        missing.append("仓库 slug（票源选 github 时必填）")
    if missing:
        print("缺件：")
        for m in missing:
            print("  -", m)
        return 1

    out = os.path.join(repo, *spec["config"]["to"].split("/"))
    adr_rel = ans.get("adr_dir") or spec["adr_dir"]
    adr_dir = os.path.join(repo, *adr_rel.split("/"))
    if not os.path.isdir(adr_dir) or not os.listdir(adr_dir):
        adr_state = "新建空目录 + 占位"
    else:
        adr_state = "已有 ADR，不动（不写「从 0001 起编号」占位）"
    print("== 将生成 ==")
    print(" ", os.path.relpath(out, repo))
    h_spec = spec["handoff"]
    own_handoff = project_has_own_handoff(os.path.join(repo, ans.get("handoff_dir") or "handoff"))
    if own_handoff:
        print("  handoff 跳过——该仓有自己的交接约定（README 在、无槽位表），不铺八槽")
    else:
        print(f"  handoff {len(h_spec['slots'])} 槽（{h_spec['board_slot']} 用子目录；其余按月）")
    print(f"  {adr_rel}/（{adr_state}）+ {spec['glossary']['to']}（已存在则不覆盖）")
    print("\n== 关键取值 ==")
    for k in ("project", "ship_mode"):
        print(f"  {k} = {cfg.get(k)}")
    for k, v in (cfg.get("paths") or {}).items():
        if not k.startswith("_note"):
            print(f"  paths.{k} = {v}")
    print(f"  registry.adrs.dir = {(cfg.get('registry') or {}).get('adrs', {}).get('dir')}")
    print(f"  gates.captain_preflight = {cfg.get('gates', {}).get('captain_preflight')}")

    if a.dry_run:
        print("\n（dry-run，未写盘）")
        return 0

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    files = gen_handoff(repo, ans, layout) + gen_docs(repo, ans, layout)

    print(f"\n已写 {os.path.relpath(out, repo)}（{len(files)} 个组件文件）")
    print("\n== 下一棒 ==")
    print("  1) 补门禁：gates 三键（captain_preflight/scope_check/close_gate）按本仓实情填，缺的留 null；项目要加别的门就扩键")
    print("     值可带子命令（读取端按 `python <值>` 直接插值），例：scripts/scope-check.py close-gate")
    print("  2) 补记录面：paths.audit_dir / module_cards / dashboard 填本仓实有落点，没有的留 null（读取端如实报缺件，不猜路径）")
    print("  3) 跑 python <kai-mode 仓>/scripts/doctor.py 确认本仓绿；在目标仓跑一轮角色自证")
    print("  4) 日表目录下写今日 -main.md / -deputy.md，再由塔台排班")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
