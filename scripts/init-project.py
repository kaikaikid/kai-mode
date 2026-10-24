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

十一问（顺序固定，缺一不可）：
  1 项目名 2 票源 3 仓库 slug 4 日表目录 5 交接目录 6 想法目录
  7 ADR 目录 8 宿主 9 收工门禁脚本 10 想法池汇总票号
  11 子代理模型（逐人格，可留空＝宿主默认）
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
        "project": ask("1/11 项目名", os.path.basename(os.path.abspath(repo)), yes),
        "ticket_source": ask("2/11 票源（github / none）", "github", yes),
        "repo_slug": ask("3/11 仓库 slug（owner/name，none 可留空）", auto_slug, yes),
        "day_tables_dir": ask("4/11 日表目录", ".ai/tasks", yes),
        "handoff_dir": ask("5/11 交接目录", "handoff", yes),
        "ideas_dir": ask("6/11 想法目录", "ideas", yes),
        "adr_dir": ask("7/11 ADR 目录", "docs/adr", yes),
        "host": ask("8/11 宿主（qoder / codex / opencode / claude / copilot / cursor）", "qoder", yes),
        "preflight_gate": ask("9/11 收工门禁脚本（相对仓根；本项目没有就回车留 null，别抄别仓的门名）",
                             "", yes),
        "boom_summary_ticket": ask("10/11 想法池汇总票号（可留空）", "", yes),
        "agent_models": ask_models(yes),
    }


def discover_personas() -> list:
    """人格名从 agents/*.md 派生（排除 README/dispatch），不写第二份名单。"""
    d = os.path.join(ROOT, "agents")
    if not os.path.isdir(d):
        return []
    return sorted(fn[:-3] for fn in os.listdir(d)
                  if fn.endswith(".md") and fn not in ("README.md", "dispatch.md"))


def norm_model(v):
    """''／默认／inherit／宿主默认 → None（不写 model）；其余去掉首尾空白原样保留。"""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("inherit", "default", "none", "null", "默认", "宿主默认"):
        return None
    return s


def ask_models(yes: bool):
    """第 11 问：返回 None（六个都用宿主默认）｜模型名字符串（六个同值）｜{人格: 模型|None}。"""
    names = discover_personas()
    if yes or not names:
        return None
    print(f"11/11 子代理模型：{' / '.join(names)}")
    print("     回车 = 六个都用宿主默认（不写 model）｜输入一个模型名 = 六个都用｜输入 n = 逐个填")
    v = ask("     选", "", False)
    if v.strip().lower() in ("n", "no", "逐个"):
        out = {}
        for n in names:
            out[n] = norm_model(ask(f"     {n} 模型（回车=宿主默认）", "", False))
        return out
    return norm_model(v)


def apply_models(cfg: dict, ans: dict) -> list:
    """把第 11 问的答案落成 models.agents（模板 _note 保留）。返回被忽略的多余人格键。"""
    names = discover_personas()
    if not names:
        return []
    raw = ans.get("agent_models")
    extra = []
    if isinstance(raw, dict):
        per = {n: norm_model(raw.get(n)) for n in names}
        extra = sorted(k for k in raw if k not in names)
    elif raw is None or raw == "":
        per = {n: None for n in names}
    else:
        m = norm_model(raw)
        per = {n: m for n in names}
    note = (cfg.get("models") or {}).get("_note")
    models = {}
    if note:
        models["_note"] = note
    models["agents"] = {n: {"model": per[n]} for n in names}
    cfg["models"] = models
    return extra


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


def apply(cfg: dict, ans: dict) -> dict:
    cfg["project"] = ans.get("project") or cfg.get("project")
    cfg["ship_mode"] = "tower"
    reg = cfg.setdefault("registry", {})
    reg.setdefault("adrs", {})["dir"] = ans.get("adr_dir") or "docs/adr"
    paths = cfg.setdefault("paths", {})
    paths["day_tables_dir"] = ans.get("day_tables_dir") or ".ai/tasks"
    paths["day_table_pattern"] = "YYYY-MM-DD-{lane}.md"
    paths["lanes"] = ["main", "deputy"]
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
    extra = apply_models(cfg, ans)
    if extra:
        print("忽略未知人格键（不在 agents/ 里）：" + "、".join(extra))
    return cfg


def gen_handoff(repo: str, ans: dict, layout: dict) -> list:
    """铺交接组件：按清单的八槽 + 规范 + 模板；只复制列名件，历史记录一概不碰。"""
    import datetime as _dt
    done = []
    month = _dt.date.today().strftime("%Y-%m")
    spec = layout["project_scaffold"]["handoff"]
    base_rel = ans.get("handoff_dir") or "handoff"
    base = os.path.join(repo, base_rel)
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
    adr_state = "已存在，只补空目录占位" if os.path.isdir(adr_dir) and os.listdir(adr_dir) else "新建空目录 + 占位"
    print("== 将生成 ==")
    print(" ", os.path.relpath(out, repo))
    print(f"  handoff {len(spec['handoff']['slots'])} 槽（{spec['handoff']['board_slot']} 用子目录；其余按月）")
    print(f"  {adr_rel}/（{adr_state}）+ {spec['glossary']['to']}（已存在则不覆盖）")
    print("\n== 关键取值 ==")
    for k in ("project", "ship_mode"):
        print(f"  {k} = {cfg.get(k)}")
    for k, v in (cfg.get("paths") or {}).items():
        if not k.startswith("_note"):
            print(f"  paths.{k} = {v}")
    print(f"  registry.adrs.dir = {(cfg.get('registry') or {}).get('adrs', {}).get('dir')}")
    print(f"  gates.captain_preflight = {cfg.get('gates', {}).get('captain_preflight')}")
    for k, v in ((cfg.get("models") or {}).get("agents") or {}).items():
        print(f"  models.agents.{k}.model = {(v or {}).get('model')}")

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
