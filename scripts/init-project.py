#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kai-mode 装到别的项目：QA 初始化
==================================
一串问答 → 生成 `<目标仓>/.ai/kai-mode.project.json`（schema 5 实例）＋ 铺组件
（`handoff/` 交接与角色沟通面、`docs/` 长期正本面；人格层角色件不在这里渲染，只调
`render-roles.py bootstrap` 那条唯一渲染口，本脚本不写第二份渲染逻辑）。

用法：
  python scripts/init-project.py --repo <目标仓>              # 逐题问（每題有默认，回车即默认）
  python scripts/init-project.py --repo <目标仓> --yes        # 全默认，不提问
  python scripts/init-project.py --repo <目标仓> --answers a.json   # 机器填（CI/批处理）
  python scripts/init-project.py --repo <目标仓> --dry-run     # 只打印结果不写盘

十二问 ＋ 双仓五题（顺序固定，缺一不可）：
  1 项目名 2 票源 3 仓库 slug 4 交接目录 5 想法目录 6 ADR 目录
  7 规则目录 8 宿主 9 收尾门命令 10 想法池汇总票号 11 推送边界 12 皮肤
  其后 Q1–Q5 双仓五题 ＋ 发布库 slug（回车一律落「待定」，不替用户选默认值）
  第 12 问留「待定」⇒ 不装人格层角色件，只点名缺件：皮肤没拍板就不替你选一套冒充拍板。
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


def write_atomic(path: str, text: str) -> None:
    """同目录临时文件＋os.replace：中途断掉不留半截 JSON（体检 M18）。
    实例是门禁的输入，半截文件会被下游读成「配置坏了」而不是「没写完」。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


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


TBD = "待定"  # 用户未拍板的双仓参数：一律落这个，不许替用户选默认值


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
    for key in ("handoff_dir", "ideas_dir", "adr_dir", "rules_dir"):
        if ans.get(key):
            ans[key] = safe_rel(ans[key], key)
    return ans


def build_answers(repo: str, a, yes: bool) -> dict:
    if a.answers:
        with open(a.answers, encoding="utf-8") as f:
            return json.load(f)
    auto_slug = guess_slug(repo)
    return {
        "project": ask("1/12 项目名", os.path.basename(os.path.abspath(repo)), yes),
        "ticket_source": ask("2/12 票源（github / none）", "github", yes),
        "repo_slug": ask("3/12 仓库 slug（owner/name，none 可留空）", auto_slug, yes),
        "handoff_dir": ask("4/12 交接目录", "handoff", yes),
        "ideas_dir": ask("5/12 想法目录", "ideas", yes),
        "adr_dir": ask("6/12 ADR 目录", "docs/adr", yes),
        "rules_dir": ask("7/12 规则目录", ".ai/rules", yes),
        "host": ask("8/12 宿主（qoder / codex / opencode / claude / copilot / cursor）— 脚本不探测本机宿主，请填你实际在用的那一个；留空＝不写该键，人格层角色件本次不装", "", yes),
        "finish_gate": ask("9/12 收尾门命令（本项目没有就回车留 null，别抄别仓的门名）",
                           "", yes),
        "boom_summary_ticket": ask("10/12 想法池汇总票号（可留空）", "", yes),
        "push_policy": ask("11/12 推送边界（默认：工作区留本地；发布/项目仓才推送，且由用户推）",
                           "workspace-local", yes),
        # 第 12 问＝人格层皮肤。回车一律「待定」＝不装：皮肤是团长的取舍，没拍板就不替她选，
        # 选错了会让每个新会话都带着错的脾气说话。答案不进配置实例，记录的家是角色件头部。
        # 推荐只写在提示里（guild 在前，理由：酒馆具名脸，默认入口康娜的正装），不作默认值。
        "persona_skin": ask("12/12 主 AI 人格皮肤（推荐 guild 酒馆康娜；generic 通用调度）回车＝待定＝本次不装角色件",
                             TBD, yes),
        # 双仓库开发规范的五题。规范明写「用户没拍板的一律记待定，不许替用户选默认值」，
        # 所以回车一律落「待定」，推荐值只写在提示里给用户参考。
        "q1_topology": ask("Q1/5 双仓还是单仓（推荐双仓；纯内部工具可单仓）回车＝待定",
                           TBD, yes),
        "q2_visibility": ask("Q2/5 发布库公开还是私有（public / private）回车＝待定", TBD, yes),
        "q3_dev_push": ask("Q3/5 开发仓推送权（user-only / ai-allowed；推荐 user-only）回车＝待定",
                           TBD, yes),
        "q4_release_issues": ask("Q4/5 发布库 issue 入口（closed / redirect；私有期推荐 closed）回车＝待定",
                                 TBD, yes),
        "q5_release_history": ask("Q5/5 发布历史（immutable-tags / rewritable；对外推荐不可变 tag）回车＝待定",
                                  TBD, yes),
        "release_repo": ask("发布库 slug（owner/name；没有就回车留待定）", TBD, yes),
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
    ("runtime.deps.check_dir_rel", "repo"),
    ("runtime.backend_python.fallback.rel", "main_tree"),
    ("runtime.node.rel", "main_tree"),
)
ON_DEMAND_PATHS = (  # 问答答案或框架自有命名空间：现在没有是正常的，按需生成，不抹成 null
    "paths.handoff_dir", "paths.ideas_dir", "paths.state_dir",
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
    reg = cfg.setdefault("registry", {})
    reg.setdefault("adrs", {})["dir"] = ans.get("adr_dir") or "docs/adr"
    reg.setdefault("rules", {})["dir"] = ans.get("rules_dir") or ".ai/rules"
    paths = cfg.setdefault("paths", {})
    paths["handoff_dir"] = ans.get("handoff_dir") or "handoff"
    paths["ideas_dir"] = ans.get("ideas_dir") or "ideas"
    gates = cfg.setdefault("gates", {})
    gate = (ans.get("finish_gate") or "").strip()
    gates["finish_cmd"] = gate or None
    issue = cfg.setdefault("issue", {})
    issue["platform"] = "none" if ans.get("ticket_source") == "none" else "github"
    if ans.get("repo_slug"):
        issue["repo"] = ans["repo_slug"]
    ticket = str(ans.get("boom_summary_ticket") or ans.get("ideas_pool_issue") or "").strip()
    issue["boom_summary_ticket"] = ticket or None
    if ans.get("host"):
        cfg.setdefault("host", {})["adapter"] = ans["host"]
    # release 段以模板为准：模板没这一段就不凭空造（ADR-0014：不发明值）。
    rel_cfg = cfg.get("release")
    if isinstance(rel_cfg, dict):
        for key, value in release_values(ans).items():
            rel_cfg[key] = value
    return cfg


TBD = "待定"  # 用户未拍板的双仓参数：一律落这个，不许替用户选默认值

# 双仓库开发规范的五题：把用户原话归一到规范取值；认不出的一律待定，不猜。
RELEASE_ENUMS = {
    "topology": {"dual": "dual", "双仓": "dual", "single": "single", "单仓": "single"},
    "visibility": {"public": "public", "公开": "public", "private": "private", "私有": "private"},
    "dev_push": {"user-only": "user-only", "只有用户推": "user-only",
                 "ai-allowed": "ai-allowed", "ai 可推": "ai-allowed", "ai可推": "ai-allowed"},
    "issues": {"closed": "closed", "关闭": "closed", "redirect": "redirect", "重定向": "redirect"},
    "history": {"immutable-tags": "immutable-tags", "不可变": "immutable-tags",
                "immutable": "immutable-tags", "rewritable": "rewritable",
                "可重推": "rewritable", "允许清空重推": "rewritable"},
}
RELEASE_LABELS = {
    "dual": "双仓（dual）", "single": "单仓（single）",
    "public": "公开（public）", "private": "私有（private）",
    "user-only": "只有用户推（user-only）", "ai-allowed": "AI 可推（ai-allowed）",
    "closed": "关闭（closed）", "redirect": "开着但重定向回开发仓（redirect）",
    "immutable-tags": "不可变 tag（immutable-tags）", "rewritable": "允许清空重推（rewritable）",
}
RELEASE_KEYS = ("topology", "visibility", "dev_push", "issues", "history")


def _pick_enum(field: str, value) -> str:
    raw = str(value or "").strip()
    if not raw or raw == TBD:
        return TBD
    table = RELEASE_ENUMS[field]
    return table.get(raw, table.get(raw.lower(), TBD))


def release_values(ans: dict) -> dict:
    """五题归一化结果（canonical 值或 TBD）。单一入口，apply 与渲染都读它。"""
    got = {
        "topology": _pick_enum("topology", ans.get("q1_topology")),
        "visibility": _pick_enum("visibility", ans.get("q2_visibility")),
        "dev_push": _pick_enum("dev_push", ans.get("q3_dev_push")),
        "issues": _pick_enum("issues", ans.get("q4_release_issues")),
        "history": _pick_enum("history", ans.get("q5_release_history")),
    }
    slug = str(ans.get("release_repo") or "").strip()
    got["repo"] = slug if (slug and slug != TBD) else TBD
    return got


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


def gen_push_policy(repo: str, ans: dict, layout: dict) -> list:
    """铺「推送边界」规则：默认只写一份；用户另行说明时按那句话改，不覆盖现值。"""
    spec = layout["project_scaffold"].get("push_policy") or {}
    src_rel, dst_rel = spec.get("from"), spec.get("to")
    if not src_rel or not dst_rel:
        return []
    src = os.path.join(ROOT, *src_rel.split("/"))
    dst = os.path.join(repo, *dst_rel.split("/"))
    if os.path.exists(dst):
        return []
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return [dst_rel]


def gen_dual_repo(repo: str, ans: dict, layout: dict) -> list:
    """铺「双仓库开发规范」：把 QA 五题结论渲染进模板，落 .ai/dual-repo.md。

    与 push-policy 一样「已有不覆盖」——用户改过的结论不许被重跑抹掉。
    """
    spec = layout["project_scaffold"].get("dual_repo") or {}
    src_rel, dst_rel = spec.get("from"), spec.get("to")
    if not src_rel or not dst_rel:
        return []
    src = os.path.join(ROOT, *src_rel.split("/"))
    dst = os.path.join(repo, *dst_rel.split("/"))
    if os.path.exists(dst):
        return []
    with open(src, encoding="utf-8") as f:
        text = f.read()
    vals = release_values(ans)
    dev = str(ans.get("repo_slug") or "").strip() or TBD
    mapping = {
        "{{Q1}}": RELEASE_LABELS.get(vals["topology"], vals["topology"]),
        "{{Q2}}": RELEASE_LABELS.get(vals["visibility"], vals["visibility"]),
        "{{Q3}}": RELEASE_LABELS.get(vals["dev_push"], vals["dev_push"]),
        "{{Q4}}": RELEASE_LABELS.get(vals["issues"], vals["issues"]),
        "{{Q5}}": RELEASE_LABELS.get(vals["history"], vals["history"]),
        "{{DEV_REPO}}": dev,
        "{{RELEASE_REPO}}": vals["repo"],
    }
    for token, value in mapping.items():
        text = text.replace(token, value)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    write_atomic(dst, text)
    return [dst_rel]


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


def gen_roles(repo: str, ans: dict, dry_run: bool = False) -> list:
    """装人格层腿一：调 `render-roles.py bootstrap` 产出角色件＋宿主映射表＋说明卡。

    渲染与枚举的正本一律住在 render-roles.py：这里**不复制一份合法值表**（那是第二个家，
    扩档必漂），只负责两件事——没拍板就不装并点名，拍了板就把渲染器自己的读数原样透传。
    皮肤不进配置实例：它的记录家是角色件头部那行 `skin=…`（doctor 的 config-instance
    只认模板那 32 个叶子键，加键即红）。
    """
    verb = "将跳过" if dry_run else "未装"
    skin = str(ans.get("persona_skin") or "").strip()
    host = str(ans.get("host") or "").strip()
    if skin in ("", TBD):
        print(f"人格层腿一{verb}：皮肤未拍板（本次＝空或「待定」）。"
              "不替你选一套冒充拍板——拍板后重跑本步即可产出角色件。")
        return []
    if host in ("", TBD):
        print(f"人格层腿一{verb}：宿主未记牢（第 8 问留空＝「本机当前宿主」，"
              "这句话脚本读不出来，不猜）。补法：填实际宿主后重跑本步。")
        return []
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "render-roles.py"),
           "bootstrap", "--project", repo, "--host", host, "--skin", skin]
    if dry_run:
        cmd.append("--dry-run")
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "").strip()
    if p.returncode != 0:
        # 合法取值由 argparse 自己报，这里不另写一份清单
        print(f"人格层腿一{verb}：bootstrap rc={p.returncode}；"
              f"{(p.stderr.strip() or out or '无输出')[:240]}")
        return []
    if out:
        print(out)  # 件数与落点只由渲染器的 stdout 生成，手抄一份就会漂
    return [f"人格层角色件（{host}／{skin}）"]


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
    if str(ans.get("push_policy") or "").strip() not in ("workspace-local", ""):
        print("推送边界只认两档：workspace-local（默认，工作区留本地）或另行说明；本次未写明，先按缺件处理")
        return 2
    policy_spec = spec.get("push_policy") or {}
    dual_spec = spec.get("dual_repo") or {}
    scaffold_sources = [
        cfg_src_rel,
        spec["glossary"]["from"],
        policy_spec.get("from") or "",
        dual_spec.get("from") or "",
        *spec["handoff"]["files"],
    ]
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
    for k in ("project",):
        print(f"  {k} = {cfg.get(k)}")
    for k, v in (cfg.get("paths") or {}).items():
        if not k.startswith("_note"):
            print(f"  paths.{k} = {v}")
    print(f"  registry.adrs.dir = {(cfg.get('registry') or {}).get('adrs', {}).get('dir')}")
    print(f"  gates.finish_cmd = {cfg.get('gates', {}).get('finish_cmd')}")
    pp = policy_spec.get("to")
    if pp:
        exists = os.path.isfile(os.path.join(repo, *pp.split("/")))
        print(f"  push_policy = {pp}（{'已有，不覆盖' if exists else '已铺骨架'}）")

    if a.dry_run:
        gen_roles(repo, ans, dry_run=True)  # 预演走渲染器自己的 --dry-run，零写盘
        print("\n（dry-run，未写盘）")
        return 0

    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_atomic(out, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    files = (
        gen_push_policy(repo, ans, layout)
        + gen_dual_repo(repo, ans, layout)
        + gen_handoff(repo, ans, layout)
        + gen_docs(repo, ans, layout)
        + gen_roles(repo, ans)
    )

    print(f"\n已写 {os.path.relpath(out, repo)}（{len(files)} 个组件文件）")
    print("\n== 下一棒 ==")
    print("  1) 补收尾门：gates.finish_cmd 按本仓实情填，没有就留 null（V2 发货时跳过并注明）")
    print("     值可带子命令（读取端按 `python <值>` 直接插值），例：scripts/scope-check.py close-gate")
    print("  2) 补记录面：paths.audit_dir / module_cards / dashboard 填本仓实有落点，没有的留 null（读取端如实报缺件，不猜路径）")
    print("  3) 跑 python <kai-mode 仓>/scripts/doctor.py 确认本仓绿；在目标仓跑一次康娜自证")
    print("  4) 在项目 CLAUDE.md / AGENTS.md 写上「默认入口＝康娜」，见 set-kai-mode 第 3 步")
    print("  5) 人格层：上面若打过「皮肤未拍板」或「宿主未记牢」，腿一就没装。拍板后可单独补跑")
    print("     python <kai-mode 仓>/scripts/render-roles.py bootstrap --project <项目根> --host <宿主> --skin <皮肤>")
    print("     两条腿都取不到时新会话按普通会话处理并登记 persona-source-unreachable（不报错、不编人格）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
