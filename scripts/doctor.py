#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kai-mode 框架仓 doctor（单一校验入口）
=====================================
用法：
    python scripts/doctor.py                # 逐项检查（25 项）
    python scripts/doctor.py --with-tests   # 追加跑各技能自己的 pytest
    python scripts/doctor.py --json         # 机器可读：{"ok":bool,"checks":[{id,status,detail}]}

仓根默认＝脚本上溯一级（`<仓根>/scripts/doctor.py` → `<仓根>`），`--root` 可指到别的根（假仓自测用）。
只读：除 pytest 自己的缓存外不写盘；只用标准库，不装任何东西。
注册表口径只有一份：本仓 `core/skills/set-kai-mode/scripts/magpie-sync.py` 里的注册表读写与装机集派生，
这里 import 那个模块来比，不复制第二份逻辑。
第 13 项 `install-sync` 依赖宿主状态（中央库在不在、装没装）：库定位不到 ⇒ 跳过，不是红。
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
import shutil
import tempfile

try:  # Windows 控制台下中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# import magpie-sync 时别在技能目录里落 __pycache__（那会被装机尺当成正本差异带进中央库）
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
OWN_ROOT = os.path.abspath(os.path.join(HERE, ".."))
MAGPIE_SYNC = os.path.join(OWN_ROOT, "core", "skills", "set-kai-mode", "scripts", "magpie-sync.py")

FRONTMATTER_ORDER = ("name", "status", "approved_by", "approved", "sources", "description", "version", "updated")
TEXT_EXT = (".md", ".py", ".bat", ".cmd", ".ps1", ".json", ".yml", ".yaml", ".txt", ".cfg", ".ini", ".sh")
# 机器绝对路径：盘符路径、\Users\ 家目录、/home/、%USERPROFILE%
MACHINE_RE = (
    (re.compile(r"[A-Za-z]:\\"), "drive"),
    (re.compile(r"\\Users\\"), "other"),
    (re.compile(r"/home/"), "other"),
    (re.compile(r"%USERPROFILE%"), "other"),
)
EXAMPLE_RE = re.compile(r"例|示例|example", re.IGNORECASE)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
ALLOW_MARK = "# doctor:allow-machine-path"

# ── 14 解耦门（ADR-0004「代价与迁移」）：项目硬路径不许回流进框架正本 ──────────
DECOUPLE_DIRS = ("airport", "core", "board", "intake", "ops", "templates")
DECOUPLE_EXT = (".md", ".py", ".json", ".bat", ".tsv")
# 模式按 ADR 判据的 grep 口径（大小写敏感）；命中行报「文件:行号:模式」。
DECOUPLE_PATTERNS = ("kai-vass", ".ai/router", ".ai/tasks", "docs/artifacts/adrs", ".ai/scope", "kai-vass-v2")
# 配置模板本体是项目差异层的载体：audit_dir 等字段采样值就是硬路径的合法新家（ADR-0004 D2 把
# .ai/scope/audit 收编进 paths.audit_dir），所以模板只对 .ai/scope 豁免；退役面（.ai/router）与
# 项目专名（kai-vass）在模板里同样不许出现，照扫。
CONFIG_TEMPLATE_REL = "templates/kai-mode.project.json"
CONFIG_TEMPLATE_EXEMPT = (".ai/scope",)
# 模型 slug 黑名单：框架仓与配置模板都不许写死具体模型（ADR-0008 D3：模型是用户的决定）。
SLUG_MARKS = ("group/", "-xhigh", "claude", "grok", "gpt", "gemini", "deepseek", "qwen",
              "kimi", "glm-", "minimax", "anthropic")
DECOUPLE_FIX = ("修法：硬路径改读项目配置实例字段（<项目仓根>/.ai/kai-mode.project.json，schema 4），"
                "字段映射见 docs/adr/0004-project-config-schema.md D2；读不到实例就 rc≠0 报缺件清单，别猜路径；"
                "模型只按人格配（models.agents.<人格>.model，null=宿主默认），见 docs/adr/0008")


def load_magpie_sync():
    """import 本仓的 magpie-sync（注册表口径只有它一份）。"""
    if not os.path.isfile(MAGPIE_SYNC):
        return None
    spec = importlib.util.spec_from_file_location("kai_mode_magpie_sync", MAGPIE_SYNC)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def registry(root, ms):
    """注册表读不出来就返回 (None, 说明)，不抛。"""
    if ms is None:
        return None, "magpie-sync 读不出来"
    data, err = ms.read_skill_registry(root)
    if err:
        return None, err
    if data is None:
        return None, "注册表不存在"
    return data, None


def parse_frontmatter(path: str):
    """返回 (顶层键顺序, name 值, 错误)：只认顶层 `key:`，缩进块（sources/description）不算键。"""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None, "没有 frontmatter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, None, "frontmatter 没闭合"
    keys, name = [], None
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        keys.append(key)
        if key == "name":
            name = val.strip().strip('"').strip("'")
    return keys, name, None


def chk_registry_file(root, ms):
    """01 registry.json 或 .claude-plugin/marketplace.json 存在、schema 认识、version 是整数。"""
    registry_path = os.path.join(root, "registry.json")
    marketplace_path = os.path.join(root, ".claude-plugin", "marketplace.json")

    # Check legacy registry.json first
    if os.path.isfile(registry_path):
        data, err = registry(root, ms)
        if data is None:
            return "fail", err
        ver = data.get("version")
        if not isinstance(ver, int) or isinstance(ver, bool):
            return "fail", f"version 不是整数：{ver!r}"
        return "ok", f"registry.json schema={data.get('schema')}，version={ver}，条目 {len(data.get('skills') or [])} 条"

    # Check marketplace.json
    if os.path.isfile(marketplace_path):
        try:
            with open(marketplace_path, encoding="utf-8") as f:
                marketplace = json.load(f)
        except (OSError, ValueError) as exc:
            return "fail", f"市场清单 JSON 解析失败：{exc}"

        if not isinstance(marketplace, dict) or "plugins" not in marketplace:
            return "fail", "市场清单格式错误：缺少 'plugins' 键"

        plugins = marketplace.get("plugins", [])
        if not isinstance(plugins, list) or not plugins:
            return "fail", "市场清单 plugins 为空"

        # Validate each plugin
        for plugin in plugins:
            if not isinstance(plugin, dict):
                return "fail", f"插件不是对象：{plugin}"

            if "name" not in plugin or "source" not in plugin or "description" not in plugin:
                return "fail", f"插件缺少必要字段：{plugin}"

            plugin_name = plugin.get("name")
            plugin_source = plugin.get("source")

            if not isinstance(plugin_name, str) or not isinstance(plugin_source, str):
                return "fail", f"插件 name/source 不是字符串：{plugin}"

            # Check local plugin directory
            plugin_dir = os.path.normpath(os.path.join(root, plugin_source))
            if not os.path.isdir(plugin_dir):
                return "fail", f"插件目录不存在：{plugin_dir}"

            # Check plugin manifest
            manifest_path = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
            if not os.path.isfile(manifest_path):
                return "fail", f"插件清单不存在：{manifest_path}"

            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
            except (OSError, ValueError) as exc:
                return "fail", f"插件清单 JSON 解析失败：{manifest_path} ({exc})"

            if not isinstance(manifest, dict) or manifest.get("name") != plugin_name:
                return "fail", f"插件清单 name 不匹配：{manifest_path}"

            version = manifest.get("version")
            if not isinstance(version, str) or not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9-]+)?$", version):
                return "fail", f"插件版本格式错误：{version}"

        return "ok", f"marketplace.json plugins={len(plugins)} 个，插件清单与版本格式正确"

    return "fail", f"注册表不存在：{registry_path} 且市场清单不存在：{marketplace_path}"


def chk_registry_fields(root, ms):
    """02 每条：字段齐全、kind/scope/install 取值合法、summary 非空。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    problems = ms.registry_entry_problems(data)
    if problems:
        head = "；".join(problems[:6])
        more = f"（共 {len(problems)} 处）" if len(problems) > 6 else ""
        return "fail", head + more
    return "ok", f"{len(data.get('skills') or [])} 条字段齐全、kind/scope/install 合法、summary 非空"


def chk_frontmatter(root, ms):
    """03 每条：SKILL.md frontmatter 八字段齐全且顺序固定；name 与目录名、与注册表名三处一致。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    problems = []
    for entry in data.get("skills") or []:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "")
        if not rel:
            continue
        md = os.path.join(root, *rel.split("/"), "SKILL.md")
        if not os.path.isfile(md):
            continue  # 路径缺失归 05 报
        keys, name, ferr = parse_frontmatter(md)
        if ferr:
            problems.append(f"{rel}/SKILL.md：{ferr}")
            continue
        ks = tuple(keys or [])
        # 八字段必须齐全且相对顺序不变；Agent Skills 1.2 的扩展字段
        # （dependencies/allowed-tools/license/compatibility/metadata）允许补充，不判红
        core = tuple(k for k in ks if k in FRONTMATTER_ORDER)
        if core != FRONTMATTER_ORDER:
            missing = [k for k in FRONTMATTER_ORDER if k not in ks]
            problems.append(f"{rel}/SKILL.md：frontmatter 八字段/顺序不对（缺 {missing} 实到 {ks}）")
            continue
        dirname = os.path.basename(rel.replace("\\", "/").rstrip("/"))
        if name != dirname or name != entry.get("name"):
            problems.append(f"{rel}/SKILL.md：name 三处不一致"
                            f"（frontmatter={name!r} 目录={dirname!r} 注册表={entry.get('name')!r}）")
    if problems:
        head = "；".join(problems[:6])
        more = f"（共 {len(problems)} 处）" if len(problems) > 6 else ""
        return "fail", head + more
    return "ok", f"{len(data.get('skills') or [])} 条 frontmatter 八字段齐全、顺序一致、name 三处一致"


def chk_unregistered(root, ms):
    """04 盘上有技能目录但没登记 ⇒ 红；插件目录没进市场清单也红。"""
    data, _ = registry(root, ms)
    inventory = set()
    for entry in (data or {}).get("skills") or []:
        if isinstance(entry, dict) and entry.get("path"):
            inventory.add(str(entry["path"]).replace("\\", "/").strip("/"))

    # 旧布局：仓根 skills/<名>/SKILL.md 必须登记
    legacy = os.path.join(root, "skills")
    legacy_on_disk = {f"skills/{n}" for n in sorted(os.listdir(legacy))
                      if os.path.isfile(os.path.join(legacy, n, "SKILL.md"))} if os.path.isdir(legacy) else set()
    if legacy_on_disk:
        on_disk = legacy_on_disk
        extra = sorted(on_disk - inventory)
        if extra:
            return "fail", f"盘上有技能目录没登记：{'、'.join(extra)}（补市场清单/插件目录）"
        return "ok", f"skills/ 上 {len(on_disk)} 个技能目录都登记了"

    # 插件布局：市场清单里的每个插件 skills/* 必须在清单里；有 plugin.json 却没进市场的目录也红
    market = os.path.join(root, ".claude-plugin", "marketplace.json")
    if not os.path.isfile(market):
        return "skip", "没有 skills/ 也没有市场清单"
    try:
        with open(market, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return "skip", "市场清单 JSON 解析失败"
    plugins = [x for x in (m.get("plugins") or []) if isinstance(x, dict)]
    names = {x.get("name") for x in plugins if isinstance(x.get("name"), str)}
    on_disk = set()
    for plugin in plugins:
        name, src = plugin.get("name"), plugin.get("source")
        if not isinstance(name, str) or not isinstance(src, str):
            continue
        if src.startswith(("http://", "https://", "git@", "github.com", "gitlab.com")):
            continue
        sd = os.path.join(root, *src.replace("\\", "/").split("/"), "skills")
        if os.path.isdir(sd):
            for sk in os.listdir(sd):
                if os.path.isfile(os.path.join(sd, sk, "SKILL.md")):
                    on_disk.add(f"{name}/skills/{sk}")
    extra = sorted(on_disk - inventory)
    if extra:
        return "fail", f"盘上有技能目录没登记：{'、'.join(extra)}（补市场清单/插件目录）"
    # 有 plugin.json 却没进市场清单的顶层目录
    orphans = []
    for d in sorted(os.listdir(root)):
        pd = os.path.join(root, d)
        if d.startswith(".") or not os.path.isdir(pd):
            continue
        if os.path.isfile(os.path.join(pd, ".claude-plugin", "plugin.json")) and d not in names:
            orphans.append(d)
    if orphans:
        return "fail", f"插件目录没进市场清单：{'、'.join(orphans)}（补 .claude-plugin/marketplace.json）"
    return "ok", f"市场布局中 {len(on_disk)} 个技能都登记了；市场插件 {len(names)} 个"


def chk_missing_path(root, ms):
    """05 注册条目的路径不存在 ⇒ 红。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    missing = []
    for entry in data.get("skills") or []:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "")
        if not rel:
            continue
        d = os.path.join(root, *rel.split("/"))
        if not os.path.isdir(d):
            missing.append(f"{rel}（目录不在）")
        elif not os.path.isfile(os.path.join(d, "SKILL.md")):
            missing.append(f"{rel}（没有 SKILL.md）")
    if missing:
        return "fail", "；".join(missing[:6]) + (f"（共 {len(missing)} 处）" if len(missing) > 6 else "")
    return "ok", f"{len(data.get('skills') or [])} 条路径与 SKILL.md 都在"


def chk_machine_path(root, ms):
    """06 技能正文/脚本里的机器绝对路径 ⇒ 红。
    豁免三种（都不放行真实机器路径以外的误伤）：
      · 该行有 `# doctor:allow-machine-path` 标记
      · 该文件在仓根 `doctor.allowlist.json` 里（没有这个文件就不建）
      · 该行是用法例句（例/示例/example）或转义字面量（`"D:\\\\"` 这种，不是路径）"""
    allow_path = os.path.join(root, "doctor.allowlist.json")
    allow_files = set()
    if os.path.isfile(allow_path):
        try:
            with open(allow_path, encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("files") if isinstance(data, dict) else data
            allow_files = {str(x).replace("\\", "/") for x in (raw or [])}
        except (OSError, ValueError):
            allow_files = set()
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return "skip", "没有 skills/ 目录"
    hits, exempt = [], []
    for base, dirs, files in os.walk(skills_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if not fn.lower().endswith(TEXT_EXT):
                continue
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if rel in allow_files:
                exempt.append(f"{rel}（allowlist）")
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, 1):
                if ALLOW_MARK in line:
                    continue
                real, escaped = [], False
                for rx, kind in MACHINE_RE:
                    for m in rx.finditer(line):
                        if kind == "drive" and m.end() < len(line) and line[m.end()] == "\\":
                            escaped = True  # 转义字面量，不是路径
                            continue
                        real.append(m)
                if real:
                    if EXAMPLE_RE.search(line):
                        exempt.append(f"{rel}:{i}（用法例句）")
                    else:
                        hits.append(f"{rel}:{i}：{line.strip()[:80]}")
                elif escaped:
                    exempt.append(f"{rel}:{i}（转义字面量）")
    if hits:
        return "fail", "；".join(hits[:6]) + (f"（共 {len(hits)} 处）" if len(hits) > 6 else "")
    tail = f"，豁免 {len(exempt)} 处" if exempt else ""
    return "ok", f"没有机器绝对路径{tail}"


RESOURCE_RE = re.compile(r'^\s*-\s*resource:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.M)
BRACE_RE = re.compile(r"\{([^{}]+)\}")


def _expand_braces(value: str) -> list:
    m = BRACE_RE.search(value)
    if not m:
        return [value]
    out = []
    for alt in m.group(1).split(","):
        out.extend(_expand_braces(value[:m.start()] + alt.strip() + value[m.end():]))
    return out


def _dead_sources(root: str, rel: str, skill_dir: str, text: str) -> tuple:
    """sources[].resource 里的路径必须指向随装件（本技能自己的文件或 skills/<名>/…）。
    不含 "/" 或含空白的条目是自然语言引用（项目配置字段、票源、上游出处），不判路径。
    只校 install:auto 的技能：manual 件本来就不随装，它的 sources 指向框架仓文档是设计内。"""
    bad, checked = [], 0
    for m in RESOURCE_RE.finditer(text):
        res = m.group(1).strip()
        if "/" not in res or any(ch.isspace() for ch in res):
            continue  # 自然语言引用（项目配置字段、票源、上游出处）不判路径；路径项不含空白
        for variant in _expand_braces(res.split("#", 1)[0]):
            checked += 1
            if variant.startswith("skills/"):
                p = os.path.join(root, *variant.split("/"))
            else:
                p = os.path.join(skill_dir, *variant.split("/"))
            if not os.path.exists(p):
                bad.append(f"{rel}/SKILL.md sources → {variant}")
    return bad, checked


def chk_broken_link(root, ms):
    """07 SKILL.md 里的相对 markdown 链接 + sources 随装件路径，指向的东西不存在 ⇒ 红。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    broken, scanned, res_checked = [], 0, 0
    for entry in data.get("skills") or []:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path") or "")
        if not rel:
            continue
        md = os.path.join(root, *rel.split("/"), "SKILL.md")
        if not os.path.isfile(md):
            continue
        scanned += 1
        with open(md, encoding="utf-8") as f:
            text = f.read()
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:", "/")):
                continue
            if re.match(r"^[A-Za-z]:[\\/]", target):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(md), *target.split("/")))
            if not os.path.exists(resolved):
                broken.append(f"{rel}/SKILL.md → {target}")
        if str(entry.get("install") or "") == "auto":
            dead, n = _dead_sources(root, rel, os.path.join(root, *rel.split("/")), text)
            broken.extend(dead)
            res_checked += n
    if broken:
        return "fail", "；".join(broken[:6]) + (f"（共 {len(broken)} 处）" if len(broken) > 6 else "")
    return "ok", f"{scanned} 份 SKILL.md 的相对链接都在；sources 随装件路径 {res_checked} 条都在"


TRACKED_DATA_SUFFIXES = (".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".db-journal",
                         ".sqlite", ".sqlite3", ".log", ".tmp", ".pid", ".jsonl")
TRACKED_DATA_DIRS = ("__pycache__", ".pytest_cache", ".workbuddy")
TRACKED_DATA_ROOT_DIRS = ("agent-data", ".agent-data", "verify", "logs", ".cache")
HANDOFF_MONTH_SEGMENT_RE = re.compile(r"^\d{4}-\d{2}$")


def _is_tracked_handoff_flow(path):
    """本仓 handoff/ 里被跟踪的文件，哪些算开发流水（GitHub 上不该看见）。"""
    if not path.startswith("handoff/"):
        return False
    parts = path.split("/")
    if any(HANDOFF_MONTH_SEGMENT_RE.match(seg) for seg in parts[1:-1]):
        return True                              # 住在日期目录里的，连 .gitkeep 一起
    if SCAFFOLD_HANDOFF_SOURCE_RE.match(path):
        return False                             # 四件规范／模板＝init-project 的骨架源
    if parts[-1] == ".gitkeep":
        return len(parts) > 4                    # 槽位与看板状态目录之外的占位
    return True                                  # 其余（看板工单等）


def _tracked_dev_records(root, paths):
    """返回 git 跟踪文件里属于「开发期间数据」的那些：缓存／运行产物 + 本仓 handoff 流水。"""
    roots = tuple(d + "/" for d in TRACKED_DATA_ROOT_DIRS)
    has_layout = os.path.isfile(os.path.join(root, *LAYOUT_REL.split("/")))
    out = []
    for x in paths:
        path = x.replace("\\", "/")
        if (path.endswith(TRACKED_DATA_SUFFIXES)
                or any(seg in TRACKED_DATA_DIRS for seg in path.split("/"))
                or path.startswith(roots)):
            out.append(x)
        elif has_layout and _is_tracked_handoff_flow(path):
            out.append(x)
    return out


def chk_tracked_cache(root, ms):
    """08 git 跟踪的文件里出现缓存、运行数据或本仓开发流水 ⇒ 红。"""
    if not os.path.isdir(os.path.join(root, ".git")):
        return "skip", "不是 git 仓（不适用）"
    try:
        p = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        return "skip", f"git 不可用：{exc}"
    if p.returncode != 0:
        return "skip", "git ls-files 失败（不适用）"
    bad = _tracked_dev_records(root, p.stdout.splitlines())
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", "git 跟踪的文件里没有缓存/运行数据/开发流水"


def chk_gitattributes(root, ms):
    """09 .gitattributes 里要有 `*.bat text eol=crlf`（.bat 落回 LF 会让 cmd 直接崩）。"""
    path = os.path.join(root, ".gitattributes")
    if not os.path.isfile(path):
        return "fail", f"没有 .gitattributes：{path}"
    with open(path, encoding="utf-8") as f:
        lines = [l.strip() for l in f.read().splitlines()]
    want = "*.bat text eol=crlf"
    if want in lines:
        return "ok", f".gitattributes 有 `{want}`"
    near = [l for l in lines if l.startswith("*.bat")]
    return "fail", f".gitattributes 缺 `{want}`（现有：{near or '无 *.bat 行'}）"


def chk_install_set(root, ms):
    """10 magpie-sync 派生的装机集合 == 注册表里 install:auto 的集合（import 那个模块比，不复制逻辑）。"""
    if ms is None:
        return "fail", "magpie-sync 读不出来"
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    auto = [e.get("name") for e in data.get("skills") or []
            if isinstance(e, dict) and e.get("install") == "auto"]
    auto_set = set(auto)
    try:
        plan = ms.install_plan(root)
    except SystemExit as exc:
        return "fail", f"magpie-sync 拒绝这份注册表：{exc}"
    derived = set(plan)
    if derived != auto_set:
        return "fail", (f"不一致：注册表 auto={sorted(x for x in auto_set if x)}，"
                        f"magpie-sync 派生={sorted(derived)}")
    return "ok", f"一致：{len(auto_set)} 条（{'、'.join(sorted(x for x in auto_set if x))}）"


def chk_version_readme(root, ms):
    """11 VERSION 的版本串要出现在 README.md 里（两处版本口径必须一致）。"""
    vf, rf = os.path.join(root, "VERSION"), os.path.join(root, "README.md")
    if not os.path.isfile(vf):
        return "fail", f"没有 VERSION 文件：{vf}"
    with open(vf, encoding="utf-8") as f:
        ver = f.read().strip()
    if not os.path.isfile(rf):
        return "fail", f"没有 README.md：{rf}"
    with open(rf, encoding="utf-8") as f:
        text = f.read()
    if ver in text:
        return "ok", f"VERSION={ver} 出现在 README.md"
    return "fail", f"VERSION={ver} 没出现在 README.md（两处版本口径不一致）"


def chk_skill_tests(root, ms):
    """12 --with-tests：跑各技能自带测试 + 仓级 `scripts/tests`。
    有 pytest 用 pytest；技能测试在没有 pytest 时退化到标准库 unittest；
    仓级测试是 doctor 自己的回归网，pytest 不可用即如实报红，不静默跳过。"""
    skills_dir = os.path.join(root, "skills")
    targets = []
    seen = set()
    # 新布局：按清单里每个技能的路径找自带测试；老布局：skills/<名> 平铺
    data, _ = registry(root, ms)
    skill_dirs = []
    for entry in (data or {}).get("skills") or []:
        rel = str((entry or {}).get("path") or "")
        if rel:
            skill_dirs.append((str(entry.get("name") or rel), os.path.join(root, *rel.split("/"))))
    if os.path.isdir(skills_dir):
        for name in sorted(os.listdir(skills_dir)):
            skill_dirs.append((name, os.path.join(skills_dir, name)))
    for name, skill_dir in skill_dirs:
        for sub in ("scripts/tests", "tests"):
            d = os.path.join(skill_dir, *sub.split("/"))
            if os.path.isdir(d) and d not in seen:
                seen.add(d)
                targets.append((name, d))
    repo_tests = os.path.join(root, "scripts", "tests")
    has_repo_tests = os.path.isdir(repo_tests)
    if not targets and not has_repo_tests:
        return "skip", "没有技能自带的测试目录，也没有 scripts/tests"

    def _run(args):
        return subprocess.run([sys.executable] + args, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=root)

    bad, mode = [], ""
    for name, d in targets:
        p = _run(["-m", "pytest", d, "-q", "-p", "no:cacheprovider"])
        if p.returncode != 0 and "No module named pytest" in (p.stderr or ""):
            mode = "unittest"
            p = _run(["-m", "unittest", "discover", "-s", d])
        elif p.returncode == 0:
            mode = mode or "pytest"
        if p.returncode != 0:
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-1:] or [""]
            bad.append(f"{name}：{tail[0][:120]}")
    if has_repo_tests:
        p = _run(["-m", "pytest", repo_tests, "-q", "-p", "no:cacheprovider"])
        if p.returncode != 0 and "No module named pytest" in (p.stderr or ""):
            bad.append("仓级 scripts/tests：pytest 不可用，未跑")
        elif p.returncode != 0:
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-1:] or [""]
            bad.append(f"仓级 scripts/tests：{tail[0][:120]}")
        else:
            mode = mode or "pytest"
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    label = f"{len(targets)} 个技能测试目录" if targets else "无技能测试目录"
    return "ok", f"{label} ＋ 仓级 scripts/tests 全绿（跑法 {mode or 'pytest'}）"


def chk_install_sync(root, ms):
    """13 装机同步：中央库里的技能副本还等于本仓吗？库记住的装机来源是不是本仓？（只读，不写盘）
    这是「本仓为准」从口头约定变成可发现的关键闸：项目仓那份旧脚本若被再跑会把库刷回旧版，
    这项检查当场点名并给修法。库定位不到 ⇒ 跳过（本仓可以脱离宿主单跑）。"""
    if ms is None:
        return "fail", "magpie-sync 读不出来"
    lib = ms.find_library()
    if not lib or not os.path.isdir(lib):
        return "skip", f"中央库定位不到（{getattr(ms, 'LIBRARY_ENV', 'KAI_MAGPIE_LIBRARY')} 未设，~/*/skills/kai-mode 没有指向库的链接）"
    fix = (f"python core/skills/set-kai-mode/scripts/magpie-sync.py apply --root {root} --library {lib}")
    try:
        plan = ms.install_plan(root)
    except SystemExit as exc:
        return "fail", f"magpie-sync 拒绝这份注册表：{exc}"
    profile = ms.marked_profile(lib)
    if profile:
        try:
            plan = ms.install_plan(root, profile)
        except SystemExit as exc:
            return "fail", f"回执档位 {profile} 读不出：{exc}"
    problems = []
    blocked = []
    rules = ms.payload_rules(root)
    # ① 库副本 vs 本仓正本：逐文件 SHA-256（payload_files 跳过 tests/ 与缓存产物，
    #    技能自带测试是本仓开发件，不进安装面，也不该出现在库里）
    for name in plan:
        src = ms.family_src(root, name, plan)
        dst = os.path.join(lib, name)
        if not os.path.isdir(src):
            problems.append(f"{name}：注册表指向的正本目录不存在（{src}）")
            continue
        try:
            a = ms.payload_files(src, rules)
        except PermissionError:
            # 环境（安全层/占用）拦读源件：这一条核对不了，如实记账，不判红也不假装通过
            blocked.append(name)
            continue
        if not a:
            # tree_files 用 os.walk，被安全层拦时会静默返回空树 —— 当拦读处理，不当「库内缺件」
            blocked.append(name)
            continue
        if not os.path.isdir(dst):
            # 库里没有这一条。先确认源件**内容**真的读得出来：读不出说明是环境拦读，
            # 这不是「内容不符」，不能当成缺陷让人去修。
            try:
                ms.sha256(next(iter(a.values())))
            except (PermissionError, OSError):
                blocked.append(name)
                continue
            problems.append(f"{name}：库内没有这一条")
            continue
        try:
            b = ms.payload_files(dst, rules)
        except PermissionError:
            blocked.append(name)
            continue
        for p in sorted(x for x in set(a) & set(b) if ms.sha256(a[x]) != ms.sha256(b[x])):
            problems.append(f"{name}/{p}：内容不符")
        for p in sorted(set(a) - set(b)):
            problems.append(f"{name}/{p}：库内缺件")
        for p in sorted(set(b) - set(a)):
            problems.append(f"{name}/{p}：库内多出")
    # ② 装机来源标记：库得记得自己是从本仓装的（判据用 magpie-sync 的 marked_root，这里只补人话原因）
    lib_root = ms.library_root(lib)
    marker_path = ms.source_marker_path(lib)
    marked = ms.marked_root(lib_root)
    if marked is None:
        if not os.path.isfile(marker_path):
            problems.append(f"装机来源没钉死：库根没有 {marker_path}（谁在别的仓目录下跑装机器就会刷回旧版）")
        else:
            problems.append(f"装机来源没钉死：标记读不出用不了（{marker_path} 损坏／schema 不认识／指向的仓不在了）")
    elif os.path.normcase(marked) != os.path.normcase(os.path.abspath(root)):
        problems.append(f"这个库是从 {marked} 装的，不是本仓")
    # ③ 库内不得残留开发件（tests/、缓存）：apply 会清，这里量盘上现状
    for name in plan:
        d = os.path.join(lib, name)
        if not os.path.isdir(d):
            continue
        for base, dnames, fnames in os.walk(d):
            for x in list(dnames):
                if x in rules.get("exclude_dirs", ()):
                    rel = os.path.relpath(os.path.join(base, x), d).replace(os.sep, "/")
                    problems.append(f"{name}/{rel}：库内残留开发件")
                    dnames.remove(x)
            for f in fnames:
                if f.endswith(tuple(rules.get("exclude_suffixes") or ())):
                    rel = os.path.relpath(os.path.join(base, f), d).replace(os.sep, "/")
                    problems.append(f"{name}/{rel}：库内残留开发件")
    if problems:
        head = "；".join(problems[:6])
        more = f"（共 {len(problems)} 处）" if len(problems) > 6 else ""
        return "fail", f"{head}{more}。修法：{fix}"
    if blocked:
        tail = f"其余 {len(plan) - len(blocked)} 个逐字相同"
        return "skip", (f"{len(blocked)} 个技能源件被环境拦读、核对不了（{'、'.join(blocked)}）；{tail}。"
                        f"安全层放行后复跑本项")
    return "ok", (f"{len(plan)} 个技能副本与本仓逐字相同；档位={profile or 'full'}；"
                  f"装机来源＝本仓（{root}）")


PROFILES_REL = "manifests/install-profiles.json"
PROFILES_SCHEMA = "kai-mode-install-profiles/1"


def chk_install_profiles(root: str, ms):
    """安装档位清单：schema 合法、core/full 存在、只引用 install:auto、core ⊆ full。"""
    path = os.path.join(root, *PROFILES_REL.split("/"))
    if not os.path.isfile(path):
        return "skip", f"没有 {PROFILES_REL}（旧仓不适用）"
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        return "fail", f"{PROFILES_REL} 读不出：{exc}"
    if not isinstance(cfg, dict) or cfg.get("schema") != PROFILES_SCHEMA:
        return "fail", f"{PROFILES_REL} schema 不是 {PROFILES_SCHEMA}"
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        return "fail", f"{PROFILES_REL} 没有 profiles"
    auto = {e.get("name") for e in data.get("skills") or []
            if isinstance(e, dict) and e.get("install") == "auto"}
    problems = []
    for name in ("core", "full"):
        if name not in profiles:
            problems.append(f"缺档位 {name}")
    expanded = {}
    for name, item in sorted(profiles.items()):
        if not isinstance(item, dict):
            problems.append(f"{name} 不是对象")
            continue
        skills = item.get("skills")
        if not isinstance(skills, list) or not skills:
            problems.append(f"{name}.skills 必须是非空数组")
            continue
        dup = sorted({x for x in skills if skills.count(x) > 1})
        if dup:
            problems.append(f"{name}.skills 重复：{', '.join(dup)}")
        unknown = sorted(set(skills) - auto)
        if unknown:
            problems.append(f"{name} 引用了非 install:auto 条目：{', '.join(unknown)}")
        expanded[name] = set(skills)
    if "core" in expanded and "full" in expanded:
        extra = sorted(expanded["core"] - expanded["full"])
        if extra:
            problems.append(f"core 不是 full 的子集：{', '.join(extra)}")
    if problems:
        return "fail", "；".join(problems[:6]) + (f"（共 {len(problems)} 处）" if len(problems) > 6 else "")
    return "ok", f"{len(profiles)} 个档位；core {len(expanded.get('core', []))} 条 ⊆ full {len(expanded.get('full', []))} 条"


def chk_install_receipt(root: str, ms):
    """安装回执：库根来源标记里的 profile／skill_names／hashes 与库现状一致。
    旧回执没有 skill_names ⇒ skip（不把旧装机判红）。"""
    if ms is None:
        return "fail", "magpie-sync 读不出来"
    lib = ms.find_library()
    if not lib or not os.path.isdir(lib):
        return "skip", "中央库定位不到（安装回执不适用）"
    marker = ms.read_source_marker(lib)
    if marker is None:
        return "skip", "库根没有新格式安装回执（旧装机／未装）"
    names = marker.get("skill_names")
    if not isinstance(names, list) or not names:
        return "skip", "旧回执没有 skill_names（不判红）"
    hashes = marker.get("hashes")
    if not isinstance(hashes, dict):
        return "fail", "回执缺 hashes；修法：重跑 magpie-sync apply --root <本仓>"
    bad = []
    for name in names:
        d = os.path.join(lib, name)
        if not os.path.isdir(d):
            bad.append(f"{name}：库内缺件")
            continue
        want = hashes.get(name)
        if not want:
            bad.append(f"{name}：回执无哈希")
        elif ms.tree_digest(d, ms.payload_rules(root)) != want:
            bad.append(f"{name}：哈希不符")
    profile = marker.get("profile")
    if profile:
        try:
            ms.install_plan(root, profile)
        except SystemExit as exc:
            bad.append(f"profile={profile}：{exc}")
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"回执 {len(names)} 条技能、档位={profile or 'full'}；哈希与库一致"


LAYOUT_REL = "manifests/package-layout.json"
LAYOUT_SCHEMA = "kai-mode-package-layout/1"
SCAFFOLD_HANDOFF_SOURCE_RE = re.compile(
    r"^handoff/(?:README\.md|60-board/README\.md|templates/[^/]+\.md)$")


def _safe_rel(value) -> bool:
    """落点必须留在目标仓内：非空、相对、不含 ..。"""
    if not isinstance(value, str) or not value.strip():
        return False
    norm = value.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        return False
    return ".." not in norm.split("/")


def chk_package_layout(root: str, ms):
    """24 三层打包边界（ADR-0011）：本仓开发件不进宿主库，也不进项目骨架。
    静态查清单与安装面；有 scripts/init-project.py 就实跑一次，生成文件集合必须与清单逐件相等。"""
    path = os.path.join(root, *LAYOUT_REL.split("/"))
    if not os.path.isfile(path):
        return "skip", f"没有 {LAYOUT_REL}（旧仓不适用）"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return "fail", f"{LAYOUT_REL} 读不出：{exc}"
    if not isinstance(data, dict) or data.get("schema") != LAYOUT_SCHEMA:
        return "fail", f"{LAYOUT_REL} schema 不是 {LAYOUT_SCHEMA}"
    problems = []
    repo_only = data.get("repo_only")
    if (not isinstance(repo_only, list) or not repo_only
            or not all(isinstance(x, str) and x for x in repo_only)):
        problems.append("repo_only 必须是非空字符串数组")
    hp = data.get("host_payload") if isinstance(data.get("host_payload"), dict) else {}
    if hp.get("source") != ".claude-plugin/marketplace.json#plugin-skills":
        problems.append("host_payload.source 必须指向 .claude-plugin/marketplace.json#plugin-skills（名单不另抄一份）")
    dirs = hp.get("exclude_dirs")
    sufs = hp.get("exclude_suffixes")
    need_dirs = {"tests", "__pycache__", ".pytest_cache"}
    if not isinstance(dirs, list) or not need_dirs <= set(dirs):
        problems.append("host_payload.exclude_dirs 必须含 " + "／".join(sorted(need_dirs)))
    if not isinstance(sufs, list) or ".pyc" not in sufs:
        problems.append("host_payload.exclude_suffixes 必须含 .pyc")
    spec = data.get("project_scaffold") if isinstance(data.get("project_scaffold"), dict) else {}
    if not spec:
        problems.append("缺 project_scaffold")
    # 安装面实量：payload 不得含被排除的开发件（防安装器与清单脱钩）
    reg, reg_err = registry(root, ms) if ms is not None else (None, "magpie-sync 读不出来")
    if reg is None:
        problems.append(f"注册表不可用：{reg_err}")
    else:
        rules = ms.payload_rules(root)
        dirs_ex = set(rules.get("exclude_dirs") or ())
        suf_ex = tuple(rules.get("exclude_suffixes") or ())
        for entry in reg.get("skills") or []:
            if not isinstance(entry, dict) or entry.get("install") != "auto":
                continue
            rel = str(entry.get("path") or "")
            src = os.path.join(root, *rel.split("/")) if rel else ""
            if not src or not os.path.isdir(src):
                continue
            leaked = sorted(
                p for p in ms.payload_files(src, rules)
                if any(seg in dirs_ex for seg in p.split("/")[:-1]) or p.endswith(suf_ex)
            )
            if leaked:
                problems.append(
                    f"{entry.get('name')} 安装面混入开发件（清单排除没生效）：{'、'.join(leaked[:4])}")
    # 骨架源与落点
    cfg = spec.get("config") if isinstance(spec.get("config"), dict) else {}
    gloss = spec.get("glossary") if isinstance(spec.get("glossary"), dict) else {}
    hand = spec.get("handoff") if isinstance(spec.get("handoff"), dict) else {}
    sources = []
    for label, item in (("config", cfg), ("glossary", gloss)):
        frm, to = item.get("from"), item.get("to")
        if not isinstance(frm, str) or not frm or not _safe_rel(to):
            problems.append(f"project_scaffold.{label} 的 from/to 不合法")
            continue
        sources.append(frm)
        if not os.path.isfile(os.path.join(root, *frm.split("/"))):
            problems.append(f"{label} 源件不存在：{frm}")
    hand_files = hand.get("files") if isinstance(hand.get("files"), dict) else {}
    if not hand_files:
        problems.append("project_scaffold.handoff.files 必须是非空映射")
    for frm, to in hand_files.items():
        sources.append(frm)
        if not SCAFFOLD_HANDOFF_SOURCE_RE.match(frm):
            problems.append(f"交接骨架源越界（只许 README／看板 README／templates 模板）：{frm}")
        if not isinstance(to, str) or not to.startswith("handoff/") or not _safe_rel(to):
            problems.append(f"交接骨架落点必须留在 handoff/：{to!r}")
        if not os.path.isfile(os.path.join(root, *frm.split("/"))):
            problems.append(f"交接骨架源件不存在：{frm}")
    for frm in sources:
        if frm == "docs" or frm.startswith("docs/"):
            problems.append(f"骨架源件来自 docs/（本仓正本，不许复制）：{frm}")
    if not _safe_rel(spec.get("adr_dir")):
        problems.append("project_scaffold.adr_dir 必须是仓内相对路径")
    placeholder = spec.get("placeholder")
    if not isinstance(placeholder, str) or not placeholder:
        problems.append("project_scaffold.placeholder 必须是非空文件名")
    slots = hand.get("slots") if isinstance(hand.get("slots"), list) else []
    monthly = hand.get("monthly_slots") if isinstance(hand.get("monthly_slots"), list) else []
    board_slot = hand.get("board_slot")
    board_children = hand.get("board_children") if isinstance(hand.get("board_children"), list) else []
    if not slots:
        problems.append("handoff.slots 必须是非空数组")
    if board_slot not in slots:
        problems.append("handoff.board_slot 必须在 slots 里")
    if not board_children:
        problems.append("handoff.board_children 必须是非空数组")
    if set(monthly) | {board_slot} != set(slots):
        problems.append("handoff.monthly_slots ＋ board_slot 必须正好覆盖 slots")
    if problems:
        return "fail", "；".join(problems[:6]) + (f"（共 {len(problems)} 处）" if len(problems) > 6 else "")
    # 实跑对账：生成面必须与清单逐件相等
    init = os.path.join(root, "scripts", "init-project.py")
    if not os.path.isfile(init):
        return "ok", "清单与安装面通过（没有 scripts/init-project.py，未实跑骨架）"
    with tempfile.TemporaryDirectory(prefix="kai-layout-") as tmp:
        target = os.path.join(tmp, "proj")
        os.makedirs(target)
        answers = {
            "project": "layout-probe", "ticket_source": "github", "repo_slug": "probe/probe",
            "day_tables_dir": ".ai/tasks", "handoff_dir": "handoff", "ideas_dir": "ideas",
            "adr_dir": spec["adr_dir"], "host": "qoder",
            "preflight_gate": "scripts/captain-preflight.py",
            "boom_summary_ticket": "", "agent_models": None,
        }
        apath = os.path.join(tmp, "answers.json")
        with open(apath, "w", encoding="utf-8") as f:
            json.dump(answers, f, ensure_ascii=False)
        p = subprocess.run([sys.executable, init, "--repo", target, "--answers", apath],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=root)
        if p.returncode != 0:
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-2:]
            return "fail", f"init-project 实跑失败 rc={p.returncode}：{' '.join(tail)[:240]}"
        actual = set()
        for base, _d, files in os.walk(target):
            for fn in files:
                actual.add(os.path.relpath(os.path.join(base, fn), target).replace(os.sep, "/"))
        adr_src = os.path.join(root, "docs", "adr")
        adr_names = sorted(fn for fn in os.listdir(adr_src)
                           if fn.endswith(".md")) if os.path.isdir(adr_src) else []
        leaked = []
        if adr_names:
            for rel in sorted(actual):
                try:
                    with open(os.path.join(target, *rel.split("/")), encoding="utf-8",
                              errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                hit = [n for n in adr_names if n in text]
                if hit:
                    leaked.append(f"{rel} ← {'、'.join(hit[:2])}")
        if leaked:
            return "fail", "骨架夹带本仓 ADR 文件名（开发记录混入）：" + "；".join(leaked[:4])
        month = dt.date.today().strftime("%Y-%m")
        expected = {cfg["to"], gloss["to"], f"{spec['adr_dir']}/{placeholder}"}
        expected |= set(hand_files.values())
        for slot in slots:
            subs = board_children if slot == board_slot else [month]
            for sub in subs:
                expected.add(f"handoff/{slot}/{sub}/{placeholder}")
        missing, extra = sorted(expected - actual), sorted(actual - expected)
        if missing or extra:
            bits = []
            if missing:
                bits.append("缺：" + "、".join(missing[:6]))
            if extra:
                bits.append("多：" + "、".join(extra[:6]))
            return "fail", "骨架实跑与清单不一致（" + "；".join(bits) + "）"
    n_auto = sum(1 for e in (reg.get("skills") or [])
                 if isinstance(e, dict) and e.get("install") == "auto")
    return "ok", (f"三层边界通过：安装面 {n_auto} 条无开发件；骨架 {len(slots)} 槽／"
                  f"{len(expected)} 件与清单逐件一致")


CFG_ASKED_GATES = ("captain_preflight",)
MACHINE_PATH_RE = re.compile(r"^([A-Za-z]:[\\/]|[\\\\]{2})")


def _cfg_leaves(node, prefix=""):
    out = set()
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_") or k == "schema":
                continue
            p = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict) and v:
                out |= _cfg_leaves(v, p)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                out |= {f"{p}.{kk}" for kk in v[0] if not str(kk).startswith("_")}
            else:
                out.add(p)
    return out


def _cfg_values(node, prefix=""):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_"):
                continue
            p = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                out.extend(_cfg_values(v, p))
            else:
                out.append((p, v))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            p = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                out.extend(_cfg_values(v, p))
            else:
                out.append((p, v))
    return out


def chk_config_instance(root: str, ms):
    """26 配置实例零虚构值：实跑一次 init-project，生成的实例必须
    ①键集与模板一致 ②值里不留 <占位>（没问出来就 null）③不留机器绝对路径
    ④gates 里非 null 的键只能是问答过的门。模板没问的字段预置本仓的值 ⇒ 红。"""
    tpl_rel = os.path.join(root, *LAYOUT_REL.split("/"))
    if not os.path.isfile(tpl_rel):
        return "skip", f"没有 {LAYOUT_REL}（不适用）"
    try:
        with open(tpl_rel, encoding="utf-8") as f:
            layout = json.load(f)
        spec = layout["project_scaffold"]
        cfg_from = os.path.join(root, *spec["config"]["from"].split("/"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return "fail", f"{LAYOUT_REL} 读不出配置模板落点：{exc}"
    init_py = os.path.join(root, "scripts", "init-project.py")
    if not (os.path.isfile(cfg_from) and os.path.isfile(init_py)):
        return "skip", "没有配置模板或初始化器（不适用）"
    tmp = tempfile.mkdtemp(prefix="kai-doctor-cfg-")
    try:
        if subprocess.run(["git", "-C", tmp, "init", "-q"], capture_output=True).returncode != 0:
            return "skip", "git 不可用（不适用）"
        answers = {
            "project": "doctor-probe", "ticket_source": "github", "repo_slug": "probe/proj",
            "day_tables_dir": ".ai/tasks", "handoff_dir": "handoff", "ideas_dir": "ideas",
            "adr_dir": "docs/adr", "host": "qoder", "preflight_gate": "",
            "boom_summary_ticket": "", "agent_models": None,
        }
        ans_file = os.path.join(tmp, "answers.json")
        with open(ans_file, "w", encoding="utf-8") as f:
            json.dump(answers, f, ensure_ascii=False)
        p = subprocess.run([sys.executable, init_py, "--repo", tmp, "--answers", ans_file],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        inst = os.path.join(tmp, *spec["config"]["to"].split("/"))
        if p.returncode != 0 or not os.path.isfile(inst):
            return "fail", "实跑 init-project 没生成实例（rc=%s）：%s" % (
                p.returncode, (p.stdout or p.stderr or "").strip()[:160])
        with open(cfg_from, encoding="utf-8") as f:
            tpl = json.load(f)
        with open(inst, encoding="utf-8") as f:
            got = json.load(f)
        problems = []
        tkeys, gkeys = _cfg_leaves(tpl), _cfg_leaves(got)
        if tkeys != gkeys:
            miss = sorted(tkeys - gkeys)
            extra = sorted(gkeys - tkeys)
            problems.append("键集不一致（模板缺 %s／实例多 %s）" % (miss[:4] or "无", extra[:4] or "无"))
        for k, v in _cfg_values(got):
            if isinstance(v, str) and "<" in v and ">" in v:
                problems.append(f"占位没答就落盘：{k}")
            elif isinstance(v, str) and MACHINE_PATH_RE.match(v):
                problems.append(f"机器绝对路径进了实例：{k}")
        fake = sorted(k.split(".")[-1] for k, v in _cfg_values(got.get("gates") or {})
                      if v not in (None,) and k.split(".")[-1] not in CFG_ASKED_GATES)
        if fake:
            problems.append("模板预置了没被问答的门：" + "、".join(fake[:5]))
        if problems:
            return "fail", "；".join(problems[:5]) + (f"（共 {len(problems)} 处）"
                                                    if len(problems) > 5 else "")
        return "ok", ("实跑生成实例通过：%d 个叶子键与模板一致，零占位、零机器路径；"
                      "gates %d 键里只有问答过的非 null" % (len(gkeys), len(got.get("gates") or {}) - 1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


PAYLOAD_TEXT_SUFFIXES = (".md", ".py", ".json", ".ps1", ".sh", ".sql", ".yaml", ".yml", ".txt")
PAYLOAD_FORBIDDEN = (
    ("框架仓 URL", re.compile(r"github\.com/kaikaikid/kai-mode")),
    ("框架 ADR 文件名", re.compile(r"docs/adr/0\d{3}")),
    ("框架 ADR 编号", re.compile(r"ADR-?\s?0\d{3}")),
    ("维护者门禁命令", re.compile(r"(?<!env-)doctor\.py")),
    ("裸 ADR 编号", re.compile(r"(?<![\w/`.-])0\d{3}(?![\d.])")),
)


def chk_payload_refs(root: str, ms):
    """25 安装面零开发史（ADR-0013）：install:auto 的 payload 里不得出现框架仓 URL、
    ADR 编号／文件名、维护者门禁命令，Markdown 相对链接也不得指向装不走的本仓开发件。
    `install:manual` 是维护侧件，豁免。"""
    if ms is None:
        return "fail", "magpie-sync 读不出来"
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    rules = ms.payload_rules(root)
    active = []
    for entry in data.get("skills") or []:
        if not isinstance(entry, dict) or entry.get("install") != "auto":
            continue
        rel = str(entry.get("path") or "").strip("/")
        if rel:
            active.append((entry.get("name"), rel))
    allowed = [rel for _name, rel in active]
    scanned, bad = 0, []
    for name, rel in active:
        src = os.path.join(root, *rel.split("/"))
        if not os.path.isdir(src):
            continue
        for path in ms.payload_files(src, rules).values():
            if not path.endswith(PAYLOAD_TEXT_SUFFIXES):
                continue
            scanned += 1
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            where = f"{name}/{os.path.relpath(path, src)}"
            for label, rx in PAYLOAD_FORBIDDEN:
                for lineno, line in enumerate(lines, 1):
                    if rx.search(line):
                        bad.append(f"{where}:{lineno} → {label}「{line.strip()[:40]}」")
            if not path.endswith(".md"):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            fenced = False
            for lineno, line in enumerate(lines, 1):
                stripped = line.lstrip()
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    fenced = not fenced
                    continue
                if fenced:
                    continue
                for m in LINK_RE.finditer(line):
                    raw = m.group(1).strip()
                    if (not raw or raw.startswith(("#", "mailto:", "/"))
                            or re.match(r"^[A-Za-z]:[\\/]", raw)):
                        continue
                    where = f"{name}/{os.path.relpath(path, src)}:{lineno}"
                    if raw.startswith(("http://", "https://")):
                        continue
                    target = raw.split("#", 1)[0]
                    if not target:
                        continue
                    resolved = os.path.normpath(os.path.join(os.path.dirname(path), *target.split("/")))
                    relres = os.path.relpath(resolved, root).replace(os.sep, "/")
                    if relres == ".." or relres.startswith("../"):
                        bad.append(f"{where} → {m.group(1)}（越出本仓）")
                    elif not any(relres == d or relres.startswith(d + "/") for d in allowed):
                        bad.append(f"{where} → {m.group(1)}（指向 {relres}，不随技能安装）")
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"{scanned} 份安装面文本：框架仓 URL／ADR 编号与文件名／维护者门禁命令 0 处（manual 件豁免）"


def _decouple_whitelisted(rel: str) -> bool:
    """解耦门白名单（仓内相对路径、正斜杠）：docs/adr（出处注记区）、_superseded/ 归档、
    缓存产物、本门自己的测试 fixture（scripts/tests/；当前扫描面不含 scripts/，这条防扫描面日后扩大）。"""
    segs = rel.split("/")
    if rel.endswith(".pyc") or "__pycache__" in segs or ".pytest_cache" in segs:
        return True
    if "_superseded" in segs[:-1]:  # 归档目录（仓根或任意层级）不算正本
        return True
    if any(segs[i] == "docs" and segs[i + 1] == "adr" for i in range(len(segs) - 1)):
        return True
    return rel.startswith("scripts/tests/")


def _template_models_problems(tpl, personas=()) -> list:
    """schema 3/4 配置模板的 models 子检查（ADR-0008 D3）：只许 {_note, agents}；
    `agents.<人格>.model` 只许 null（框架不写死模型）；键集与盘上人格双向一致。
    models 段已被移除（schema 4+），只检查当它存在时。"""
    problems = []
    models = tpl.get("models")
    if not models:
        return []  # models 段已退役，不报错
    if not isinstance(models, dict):
        return ["models 段不是对象（模型配置必须有家）"]
    for k in ("tiers", "default", "roles"):
        if k in models:
            problems.append(f"models.{k} 已退役（六档词表已退役，ADR-0008 D3）——模型只按人格配")
    extra = sorted(k for k in models if k not in ("_note", "agents"))
    if extra:
        problems.append(f"models 多余键 {', '.join(extra)}（只许 _note/agents）")
    agents = models.get("agents")
    if not isinstance(agents, dict):
        problems.append("models.agents 缺失或不是对象")
        return problems
    for name, spec in sorted(agents.items()):
        if not isinstance(spec, dict):
            problems.append(f"models.agents.{name} 不是对象")
            continue
        junk = sorted(k for k in spec if k != "model")
        if junk:
            problems.append(f"models.agents.{name} 多余键 {', '.join(junk)}（只许 model）")
        if "model" not in spec:
            problems.append(f"models.agents.{name} 缺 model（写 null = 宿主默认）")
        elif spec["model"] is not None:
            problems.append(f"models.agents.{name}.model={spec['model']!r}（模板只许 null：框架不写死模型）")
    if personas:
        missing = sorted(set(personas) - set(agents))
        ghost = sorted(set(agents) - set(personas))
        if missing:
            problems.append(f"models.agents 缺人格：{', '.join(missing)}")
        if ghost:
            problems.append(f"models.agents 有盘上不存在的人格：{', '.join(ghost)}")
    return problems


def chk_decoupling(root, ms):
    """14 解耦门（ADR-0004「代价与迁移」）：skills/ loops/ templates/ 的文本文件里不许再有项目硬路径
    （kai-vass、.ai/router、.ai/tasks、docs/artifacts/adrs、.ai/scope、kai-vass-v2），命中即红并按
    「文件:行号:模式」点名。白名单：docs/adr（出处注记）、_superseded/、缓存产物、本门测试 fixture；
    配置模板本体只对 .ai/scope 豁免（字段采样值是硬路径的合法新家），其余模式照扫。
    子检查：配置模板 schema==3 时，models 段只许按人格配、值只许 null（ADR-0008 D3）。"""
    bases = [os.path.join(root, d) for d in DECOUPLE_DIRS if os.path.isdir(os.path.join(root, d))]
    if not bases:
        return "skip", "没有插件目录或 templates/（不适用）"
    hits, scanned = [], 0
    for base in bases:
        for b, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".pytest_cache")]
            for fn in sorted(files):
                if not fn.lower().endswith(DECOUPLE_EXT):
                    continue
                p = os.path.join(b, fn)
                rel = os.path.relpath(p, root).replace("\\", "/")
                if _decouple_whitelisted(rel):
                    continue
                scanned += 1
                pats = [x for x in DECOUPLE_PATTERNS
                        if rel != CONFIG_TEMPLATE_REL or x not in CONFIG_TEMPLATE_EXEMPT]
                try:
                    with open(p, encoding="utf-8") as f:
                        lines = f.read().splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                for i, line in enumerate(lines, 1):
                    matched = [x for x in pats if x in line]
                    # 长模式命中就不再报被它包含的短模式（kai-vass-v2 命中不重复报 kai-vass）
                    matched = [x for x in matched if not any(x != y and x in y for y in matched)]
                    hits.extend(f"{rel}:{i}:{x}" for x in matched)
    problems = []
    if hits:
        head = "；".join(hits[:6]) + (f"（共 {len(hits)} 处）" if len(hits) > 6 else "")
        problems.append(f"硬路径残留：{head}")
    tpl_note = ""
    tpl_path = os.path.join(root, *CONFIG_TEMPLATE_REL.split("/"))
    if os.path.isfile(tpl_path):
        try:
            with open(tpl_path, encoding="utf-8") as f:
                tpl = json.load(f)
        except (OSError, ValueError) as exc:
            problems.append(f"{CONFIG_TEMPLATE_REL} 不是合法 JSON：{exc}")
        else:
            if tpl.get("schema") in (3, 4):
                problems.extend(_template_models_problems(tpl, _agent_personas(root)))
            else:
                tpl_note = f"；配置模板 schema={tpl.get('schema')!r}，models 子检查只对 schema 3/4 生效"
    else:
        tpl_note = "；配置模板不在，models 子检查跳过"
    if problems:
        return "fail", "；".join(problems) + "。" + DECOUPLE_FIX
    return "ok", (f"skills/loops/templates 扫了 {scanned} 份文本文件，六种硬路径 0 命中；"
                  f"配置模板 models 只按人格配、无模型 slug{tpl_note}")


# ── 15 交接文档分类（handoff/）：两级路径 / 命名 / frontmatter / 类型词与槽位一致 ────
HANDOFF_SLOTS = ("00-inbox", "10-session", "20-plan", "30-research", "40-review",
                 "50-comms", "60-board", "90-archive")
# 60-board 按「工作流状态」分（角色与人格划分还在演进，目录不绑架未定概念）
HANDOFF_BOARD_STATES = ("open", "claimed", "done")
HANDOFF_ARCHIVE = "archive"  # 看板归档：60-board/archive/YYYY-MM/ + 月度索引 YYYY-MM.md
# 类型词 → 槽位（正本在 handoff/README.md §二 槽位判定表，两处必须一致）
HANDOFF_TYPE2SLOT = {
    "handoff": "10-session", "carry": "10-session",
    "plan": "20-plan", "fixplan": "20-plan", "design": "20-plan", "spec": "20-plan", "roadmap": "20-plan",
    "research": "30-research", "analysis": "30-research", "comparison": "30-research",
    "census": "30-research", "survey": "30-research",
    "review": "40-review", "audit": "40-review", "triage": "40-review",
    "postmortem": "40-review", "acceptance": "40-review",
    "msg": "50-comms", "ask": "50-comms", "answer": "50-comms", "notice": "50-comms",
    "task": "60-board", "dispatch": "60-board", "claim": "60-board", "blocked": "60-board",
    "hotfix": "60-board",
}
HANDOFF_NAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$")
HANDOFF_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
ROOT_MD_ALLOWED = ("README.md", "AGENTS.md", "CHANGELOG.md", "GLOSSARY.md")
INBOX_TTL_DAYS = 7


def _fm_fields(path):
    """读文件头 frontmatter 的 key→value（只取顶层 `key:`，剥掉行内 # 注释）。没有则 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not lines or lines[0].strip() != "---":
        return None
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = re.split(r"\s+#", m.group(2), maxsplit=1)[0].strip().strip('"').strip("'")
    return out


def _handoff_files(root):
    """handoff/ 下受检的 .md（规范本体 README.md 与 templates/ 不参与命名检查）。"""
    hd = os.path.join(root, "handoff")
    out = []
    for base, _dirs, files in os.walk(hd):
        rel_dir = os.path.relpath(base, root).replace("\\", "/")
        if rel_dir.split("/")[1:2] == ["templates"]:
            continue
        for fn in files:
            if not fn.endswith(".md"):
                continue
            rel = f"{rel_dir}/{fn}"
            if fn == "README.md":
                continue  # 规范本体与槽级协议（如 60-board/README.md）不参与命名检查
            out.append((rel, os.path.join(base, fn)))
    return sorted(out)


def chk_handoff(root, ms):
    """15 交接文档分类：八槽齐全 / 两级路径 / 命名 / frontmatter 一致 / 类型词对槽 / inbox 不滞留 / 仓根无散落。"""
    hd = os.path.join(root, "handoff")
    if not os.path.isdir(hd):
        return "fail", "没有 handoff/（交接文档唯一落点，规范见 handoff/README.md）"
    bad = []
    for slot in HANDOFF_SLOTS:
        if not os.path.isdir(os.path.join(hd, slot)):
            bad.append(f"缺槽位 handoff/{slot}/")
    for name in sorted(os.listdir(hd)):
        if os.path.isdir(os.path.join(hd, name)) and name not in HANDOFF_SLOTS and name != "templates":
            bad.append(f"handoff/ 下非法子目录 {name}/（只许八槽 + templates）")
    if not os.path.isfile(os.path.join(hd, "README.md")):
        bad.append("handoff/README.md 缺失（分类规范入口）")

    today = dt.date.today()
    files = _handoff_files(root)
    for rel, path in files:
        fn = os.path.basename(path)
        parts = rel.split("/")
        # 两级：handoff/<槽>/<YYYY-MM 或状态>/<文件>（看板归档多一层月份）
        slot, sub = (parts[1], parts[2]) if len(parts) >= 3 else ("", "")
        if slot == "60-board" and sub == HANDOFF_ARCHIVE:
            if len(parts) == 4:
                continue  # 月度生命周期索引（handoff-board.py archive 生成），豁免
            if len(parts) != 5 or not HANDOFF_MONTH_RE.match(parts[3]):
                bad.append(f"{rel}：看板归档应为 60-board/archive/YYYY-MM/")
        elif len(parts) != 4:
            bad.append(f"{rel}：必须落在两级目录（handoff/<槽>/<YYYY-MM|状态>/）")
            continue
        m = HANDOFF_NAME_RE.match(fn)
        if not m:
            bad.append(f"{rel}：命名不合 YYYY-MM-DD-<slug>-<类型>.md")
            continue
        try:
            filedate = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            bad.append(f"{rel}：文件名日期不合法")
            continue
        if slot == "60-board" and sub != HANDOFF_ARCHIVE:
            if sub not in HANDOFF_BOARD_STATES:
                bad.append(f"{rel}：看板子目录只许 {'/'.join(HANDOFF_BOARD_STATES)}")
        elif slot != "60-board":  # 看板不按月分，按状态分
            mm = HANDOFF_MONTH_RE.match(sub)
            if not mm:
                bad.append(f"{rel}：二级目录应是 YYYY-MM，实际 {sub}/")
            elif sub != f"{m.group(1)}-{m.group(2)}":
                bad.append(f"{rel}：文件名年月 {m.group(1)}-{m.group(2)} 与所在目录 {sub}/ 不符")
        if slot == "00-inbox" and (today - filedate).days > INBOX_TTL_DAYS:
            bad.append(f"{rel}：收件箱滞留 {(today - filedate).days} 天（>{INBOX_TTL_DAYS} 天必须归位）")

        # 归档区保留原件：类型词与 frontmatter 的 slot 都按原槽留痕，只校验命名与年月。
        if slot == "90-archive":
            continue

        tword = fn[:-3].rsplit("-", 1)[-1].lower()
        want = HANDOFF_TYPE2SLOT.get(tword)
        if want is None:
            bad.append(f"{rel}：类型词 {tword} 未在 handoff/README.md 登记")
        elif want != slot:
            bad.append(f"{rel}：类型词 {tword} 该落 {want}/，现在在 {slot}/")

        # frontmatter 是 AI 识别用途的机器正本：slot/type 必须与落位一致
        fm = _fm_fields(path)
        if fm is None:
            bad.append(f"{rel}：缺 frontmatter（slot/type 是机器认用途的正本，见 templates/）")
        else:
            if fm.get("slot") and fm["slot"] != slot:
                bad.append(f"{rel}：frontmatter slot={fm['slot']} 与实际槽 {slot}/ 不符")
            if fm.get("type") and fm["type"].lower() != tword:
                bad.append(f"{rel}：frontmatter type={fm['type']} 与文件名类型词 {tword} 不符")

        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        fence = False
        for i, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence or ALLOW_MARK in line or EXAMPLE_RE.search(line):
                continue
            for rx, kind in MACHINE_RE:
                hit = rx.search(line)
                if hit and not (kind == "drive" and hit.end() < len(line) and line[hit.end()] == "\\"):
                    bad.append(f"{rel}:{i}：机器绝对路径（应写相对仓根）")
                    break

    for fn in sorted(os.listdir(root)):
        if fn.endswith(".md") and fn not in ROOT_MD_ALLOWED:
            bad.append(f"仓根散落文档 {fn}（应进 handoff/ 对应槽）")

    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"handoff/ 八槽齐全，{len(files)} 份文档两级路径·命名·frontmatter 均合规"


# ── 16 技能格式对齐 Agent Skills 规范 1.2（Anthropic 开放标准，Claude/Codex/Cursor/Copilot 采纳）──
# 规范要点：name 与目录名一致（小写字母数字+连字符）、version 必填且 semver、
# description ≤1024 字符、SKILL.md < 500 行、未知顶层字段忽略（故本仓扩展字段不违规）。
SPEC_MAX_LINES = 500
SPEC_MAX_DESC = 1024
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def chk_skill_spec(root, ms):
    """16 技能格式对齐规范 1.2：version(semver) / description(≤1024) / SKILL.md(<500 行) / name 与目录名一致。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    bad, nonkebab, scanned = [], [], 0
    for e in data.get("skills") or []:
        if not isinstance(e, dict):
            continue
        d = os.path.join(root, e.get("path", ""))
        p = os.path.join(d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        nm = e.get("name", "?")
        lines = text.splitlines()
        if len(lines) > SPEC_MAX_LINES:
            bad.append(f"{nm}：SKILL.md {len(lines)} 行 > {SPEC_MAX_LINES}（细则应拆进 references/）")
        fm = {}
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip()
        if not fm:
            bad.append(f"{nm}：没有 frontmatter")
            continue
        ver = fm.get("version", "")
        if not SEMVER_RE.match(ver):
            bad.append(f"{nm}：version 不是 semver（{ver or '缺'}）")
        m = re.search(r"description: >?\n((?:  .*\n)+)", text)
        desc = " ".join(x.strip() for x in m.group(1).splitlines()) if m else fm.get("description", "")
        if not desc:
            bad.append(f"{nm}：description 为空")
        elif len(desc) > SPEC_MAX_DESC:
            bad.append(f"{nm}：description {len(desc)} 字符 > {SPEC_MAX_DESC}")
        if fm.get("name", "") != os.path.basename(d):
            bad.append(f"{nm}：frontmatter name 与目录名不一致")
        if not KEBAB_RE.match(fm.get("name", "")):
            nonkebab.append(fm.get("name", ""))
    tail = f"；非 kebab-case 名 {len(nonkebab)} 个（中文口令是有意偏离，不判红）" if nonkebab else ""
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"{scanned} 份 SKILL.md 对齐规范 1.2（version/description/行数/name）{tail}"


# ── 17 agents 层契约（ADR-0007 / ADR-0008）──────────────────────────────────
# 对齐 Agent Skills 开放标准：顶层只许标准字段（自有语义一律进 metadata）、name==文件名、
# description ≤1024、metadata 只许 access、正文 <500 行 / 零外链 / 零 slug。
AGENT_TOP_KEYS = ("name", "description", "version", "license", "compatibility", "metadata")
AGENT_META = {"access": ("readonly", "write")}
AGENT_MAX_LINES = 500
AGENT_DESC_MAX = 1024
AGENT_NON_PERSONA = ("README.md", "dispatch.md")


def _agent_frontmatter(text: str):
    """解析人格 frontmatter：返回 ((顶层键顺序, 顶层值, metadata 值, 正文行), None) 或 (None, 错误)。

    只认本层固定形状（顶层 key + metadata 缩进块 + description 折叠块），不引 yaml。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "没有 frontmatter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter 没闭合"
    order, top, meta, cur, buf = [], {}, {}, None, []

    def flush():
        nonlocal buf
        if cur is not None and buf:
            top[cur] = " ".join(x.strip() for x in buf if x.strip())
        buf = []

    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", raw)
        if m:
            flush()
            key, val = m.group(1), m.group(2).strip()
            order.append(key)
            cur = key
            if key == "metadata" or val in ("", ">", "|", ">-", "|-"):
                top[key] = ""
            else:
                top[key] = val.strip('"').strip("'")
            continue
        m2 = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
        if m2 and cur == "metadata":
            meta[m2.group(1)] = m2.group(2).strip().strip('"').strip("'")
            continue
        buf.append(raw)
    flush()
    return (order, top, meta, lines[end + 1:]), None


def _agent_personas(root: str) -> list:
    d = os.path.join(root, "agents")
    if not os.path.isdir(d):
        return []
    return sorted(fn[:-3] for fn in os.listdir(d)
                  if fn.endswith(".md") and fn not in AGENT_NON_PERSONA)


def chk_agents(root, ms):
    """17 agents 层契约：字段合规、零外链、README 表两向一致、handoff persona 有家。"""
    d = os.path.join(root, "agents")
    if not os.path.isdir(d):
        return "skip", "人格层已退役（无 agents/）"
    personas = _agent_personas(root)
    if not personas:
        return "fail", "agents/ 下没有 <人格>.md 文件"
    bad = []
    for stem in personas:
        fn = stem + ".md"
        p = os.path.join(d, fn)
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            bad.append(f"{fn}：读不出来 {exc!r}")
            continue
        parsed, err = _agent_frontmatter(text)
        if err:
            bad.append(f"{fn}：{err}")
            continue
        order, top, meta, body = parsed
        extra = [k for k in order if k not in AGENT_TOP_KEYS]
        if extra:
            bad.append(f"{fn}：非标准顶层字段 {', '.join(extra)}（自有语义进 metadata）")
        for k in ("name", "description", "version"):
            if not top.get(k):
                bad.append(f"{fn}：缺 {k}")
        if "metadata" not in order:
            bad.append(f"{fn}：缺 metadata")
        seq = [k for k in order if k in ("name", "description", "version", "metadata")]
        want = ["name", "description", "version", "metadata"]
        if seq != want:
            bad.append(f"{fn}：必填字段顺序应为 {' < '.join(want)}，实际 {' < '.join(seq) or '无'}")
        if top.get("name") and top["name"] != stem:
            bad.append(f"{fn}：name={top['name']!r} 与文件名不一致")
        if not KEBAB_RE.match(top.get("name") or ""):
            bad.append(f"{fn}：name 不是 kebab-case")
        if top.get("version") and not SEMVER_RE.match(top["version"]):
            bad.append(f"{fn}：version 不是 semver（{top['version']}）")
        if len(top.get("description") or "") > AGENT_DESC_MAX:
            bad.append(f"{fn}：description 超 {AGENT_DESC_MAX} 字符")
        junk = sorted(k for k in meta if k not in AGENT_META)
        if junk:
            bad.append(f"{fn}：metadata 多余键 {', '.join(junk)}（只许 access）")
        for k, allowed in AGENT_META.items():
            v = meta.get(k)
            if not v:
                bad.append(f"{fn}：metadata 缺 {k}")
            elif v not in allowed:
                bad.append(f"{fn}：metadata.{k}={v!r} 不在枚举 {'/'.join(allowed)}")
        body_text = "\n".join(body)
        nlines = len([x for x in body if x.strip()])
        if nlines > AGENT_MAX_LINES:
            bad.append(f"{fn}：正文 {nlines} 行 > {AGENT_MAX_LINES}")
        for target in LINK_RE.findall(body_text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if os.path.dirname(target) not in ("", "."):
                bad.append(f"{fn}：外链 {target}（人格只许指 agents/ 内同级文件）")
        low = body_text.lower()
        for mark in SLUG_MARKS:
            if mark in low:
                bad.append(f"{fn}：正文出现模型 slug 片段 {mark!r}")
        if any(rx.search(body_text) for rx, _ in MACHINE_RE):
            bad.append(f"{fn}：正文出现机器绝对路径")
    # README 人格表 ↔ 盘上文件 双向一致
    rp = os.path.join(d, "README.md")
    listed = set()
    if os.path.isfile(rp):
        with open(rp, encoding="utf-8") as f:
            for ln in f:
                m = re.match(r"^\|\s*\[([a-z0-9-]+)\]\(([a-z0-9-]+)\.md\)", ln)
                if m:
                    listed.add(m.group(1))
    else:
        bad.append("agents/README.md 不存在")
    missing = sorted(set(personas) - listed)
    ghost = sorted(listed - set(personas))
    if missing:
        bad.append(f"README 表缺：{', '.join(missing)}")
    if ghost:
        bad.append(f"README 表多出无文件条目：{', '.join(ghost)}")
    # handoff frontmatter 的 persona 取值必须有家
    ok_ids = set(personas) | {"-"}
    hd = os.path.join(root, "handoff")
    if os.path.isdir(hd):
        for dirpath, dirs, names in os.walk(hd):
            dirs[:] = [x for x in dirs if x not in ("__pycache__",)]
            for fn in sorted(names):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, encoding="utf-8") as f:
                        head = f.read(3000)
                except (OSError, UnicodeDecodeError):
                    continue
                m = re.search(r"^persona:\s*(\S+)\s*$", head, re.M)
                if m:
                    v = m.group(1).strip('"').strip("'")
                    if v.startswith("<") or v.startswith("{{"):
                        continue  # 模板占位符，不判
                    if v not in ok_ids:
                        bad.append(f"{os.path.relpath(fp, root).replace(chr(92), '/')}：persona={v} 不在人格集内")
    # 人格**计数**不许写死：加一格就会把别处的旧数留成假话（第七人格落地时实测三处残留）
    PERSONA_COUNT_RX = re.compile(r"[0-9]+\s*(?:个|种)\s*(?:子代理)?人格"
                                  r"|全部\s*(?:[0-9]+|[一二两三四五六七八九十])\s*个")
    count_files = [os.path.join(root, x) for x in ("README.md", "AGENTS.md")
                   if os.path.isfile(os.path.join(root, x))]
    for cd in ("skills", "loops", "templates", "agents", "adapters"):
        cbase = os.path.join(root, cd)
        if os.path.isdir(cbase):
            for dirpath, dirs, names in os.walk(cbase):
                dirs[:] = [x for x in dirs if x not in ("__pycache__", ".pytest_cache")]
                count_files += [os.path.join(dirpath, x) for x in names if x.endswith(TEXT_EXT)]
    for fp in count_files:
        try:
            with open(fp, encoding="utf-8") as f:
                ftext = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        for i, ln in enumerate(ftext.splitlines(), 1):
            cm = PERSONA_COUNT_RX.search(ln)
            if cm:
                bad.append("%s:%d 写死了人格计数「%s」（改指针，名单由 agents/ 实量派生）"
                           % (os.path.relpath(fp, root).replace("\\", "/"), i, cm.group(0).strip()))
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"{len(personas)} 个格：字段·零外链·零 slug·README 两向一致·persona 有家·计数未写死"


# ── 18 判据归属门（ADR-0007）：一条判据一个家，退役词与平行正本都要红 ──────────
CANON_REL = "docs/canon.json"


def chk_canon(root, ms):
    """18 判据归属：退役词黑名单 + 每个判据键只许住 home，不许出现在 forbidden 目录。"""
    path = os.path.join(root, CANON_REL)
    if not os.path.isfile(path):
        return "fail", f"缺件：{CANON_REL}（判据归属表正本）"
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return "fail", f"{CANON_REL} 读不出来：{exc!r}"
    retired = cfg.get("retired_terms") or []
    exempt = tuple(cfg.get("exempt") or ())
    keys = cfg.get("canon_keys") or []
    files = []
    for rel in cfg.get("scan_roots") or []:
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            files.append(p)
        elif os.path.isdir(p):
            for dirpath, dirs, names in os.walk(p):
                dirs[:] = [x for x in dirs if x not in ("__pycache__", ".pytest_cache")]
                for fn in names:
                    if fn.endswith(TEXT_EXT):
                        files.append(os.path.join(dirpath, fn))
    bad, scanned = [], 0
    for fp in files:
        relf = os.path.relpath(fp, root).replace("\\", "/")
        if any(relf.startswith(e) for e in exempt):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        for i, ln in enumerate(text.splitlines(), 1):
            if "canon:allow-retired" in ln:
                continue  # 显式声明某词已退役的那一行，豁免
            for term in retired:
                if term in ln:
                    bad.append(f"{relf}:{i} 退役词「{term}」")
            for ck in keys:
                if relf == ck.get("home"):
                    continue
                if not any(relf.startswith(x) for x in (ck.get("forbidden") or [])):
                    continue
                try:
                    if re.search(ck["pattern"], ln):
                        bad.append(f"{relf}:{i} 平行正本「{ck['key']}」（家={ck['home']}）")
                except re.error:
                    bad.append(f"{CANON_REL}：判据键 {ck.get('key')} 正则非法")
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"{scanned} 个文件：退役词 {len(retired)} 个零命中，判据键 {len(keys)} 条单点住家"


# ── 19 vendor 漂移（ADR-0008 D7）：vendor/ 必须进 git；有本机镜像时与源一致 ─────────
# ── 20 宿主中立（ADR-0008）：宿主专有 token 只许住 adapters/ ─────────────────
HOST_NEUTRAL_DIRS = ("airport", "core", "board", "intake", "ops", "skills")
HOST_TOKENS = (
    (re.compile(r"\$\{?CLAUDE_"), "CLAUDE_*"),
    (re.compile(r"\$\{?ARGUMENTS\}?"), "$ARGUMENTS"),
    (re.compile(r"\bqoder_cron\b"), "qoder_cron"),
    (re.compile(r"\bcreate_chat_session\b"), "create_chat_session"),
    (re.compile(r"~/\.claude/"), "~/.claude"),
    (re.compile(r"\.claude/"), ".claude/"),
    (re.compile(r"\.opencode/"), ".opencode/"),
    (re.compile(r"\.codex/"), ".codex/"),
    (re.compile(r"\bcodex exec\b"), "codex exec"),
    (re.compile(r"\bopencode run\b"), "opencode run"),
    (re.compile(r"\bmcp__[A-Za-z0-9_]+"), "mcp__*"),
)
# ── 21 frontmatter YAML 形状（skills / agents）：不引 PyYAML，只拦最常见的粘连 ──
YAML_RESERVED_START = ("@", "`")


def chk_host_neutral(root: str, ms):
    """宿主专有 token 不许进 skills/ loops/ agents/：那些细节归 adapters/<宿主>.md。
    需要保留的说明行写 `canon:allow-host`。"""
    hits, scanned = [], 0
    for d in HOST_NEUTRAL_DIRS:
        base = os.path.join(root, d)
        if not os.path.isdir(base):
            continue
        for b, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".pytest_cache", "commands")]
            for fn in sorted(files):
                if not fn.lower().endswith(TEXT_EXT):
                    continue
                p = os.path.join(b, fn)
                rel = os.path.relpath(p, root).replace("\\", "/")
                try:
                    with open(p, encoding="utf-8") as f:
                        lines = f.read().splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                scanned += 1
                for i, line in enumerate(lines, 1):
                    if "canon:allow-host" in line:
                        continue
                    for rx, label in HOST_TOKENS:
                        if rx.search(line):
                            hits.append(f"{rel}:{i}:{label}")
    if hits:
        return "fail", ("宿主专有 token 进正本： " + "；".join(hits[:6])
                        + ("（共 %d 处）" % len(hits) if len(hits) > 6 else "")
                        + "。修法：宿主细节移入 adapters/<宿主>.md，本处留指针")
    return "ok", f"插件目录（commands/ 是宿主面，豁免）扫了 {scanned} 份文本文件，宿主专有 token 0 命中"


def _frontmatter_yaml_problems(text: str) -> list:
    """frontmatter 的 YAML 形状：未加引号的 `: `、`@`/反引号开头的值。
    只做最常见、能从 markdown 行直接判的拦截；复杂 YAML 解析仍不引依赖。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ["没有 frontmatter"]
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return ["frontmatter 没闭合"]
    bad = []
    for i, line in enumerate(lines[1:end], 2):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if not val or val.startswith(("'", '"')):
            continue
        if ": " in val:
            bad.append(f"{key} 的未加引号值含 ': '（第 {i} 行）——加引号或把下一键分行")
        if val.startswith(YAML_RESERVED_START):
            bad.append(f"{key} 的未加引号值以 {val[0]!r} 开头（第 {i} 行）——YAML 保留字符，需加引号")
    return bad


def chk_frontmatter_yaml(root: str, ms):
    """skills/ 已登记 SKILL.md 与 agents/*.md 的 frontmatter YAML 形状。"""
    targets = []
    data, err = registry(root, ms)
    if data is not None:
        for entry in data.get("skills") or []:
            if isinstance(entry, dict) and entry.get("path"):
                p = os.path.join(root, *str(entry["path"]).split("/"), "SKILL.md")
                if os.path.isfile(p):
                    targets.append(p)
    ad = os.path.join(root, "agents")
    if os.path.isdir(ad):
        for fn in sorted(os.listdir(ad)):
            if fn.endswith(".md") and fn not in AGENT_NON_PERSONA:
                targets.append(os.path.join(ad, fn))
    bad, scanned = [], 0
    for p in targets:
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        rel = os.path.relpath(p, root).replace("\\", "/")
        for problem in _frontmatter_yaml_problems(text):
            bad.append(f"{rel}：{problem}")
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", f"{scanned} 份 frontmatter YAML 形状合规（无未加引号的 ': ' / 保留字符开头）"


VENDOR_REL = "vendor"
VENDOR_SYNC = "scripts/vendor-sync.py"
VENDOR_MIRROR = os.path.expanduser(os.path.join("~", ".workbuddy", "skills"))


# ── 28 命令面覆盖：技能正文 ```bash 块里声明要跑的命令，必须在它自己的 allowed-tools 里 ──
CMD_FENCE_RE = re.compile(r"^```[ \t]*(?:bash|sh|shell|console)[ \t]*\n(.*?)^```", re.S | re.M)
CMD_LEAD_RE = re.compile(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S+\s+)*([A-Za-z][A-Za-z0-9._-]{1,24})\b")
CMD_SKIP_WORDS = {"cd", "export", "set", "echo", "if", "then", "else", "elif", "for", "while",
                  "do", "done", "true", "false", "source", "exit", "test", "and", "or"}
CMD_PREFIX_WORDS = {"command", "sudo", "time", "env", "nohup", "npx"}


def _skill_allowed_tools(text: str) -> str:
    """取 SKILL.md frontmatter 里的 allowed-tools 值（折叠标量的续行也算，不限行数）。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    value, collecting = "", False
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        if collecting:
            if ln.startswith(("  ", "\t")):
                value += " " + ln.strip()
                continue
            break
        if ln.startswith("allowed-tools:"):
            value = ln.split(":", 1)[1].strip()
            collecting = True
    return value


def _bash_covers(allowed: str, biname: str) -> bool:
    """`Bash(<命令>:*)`、更细的 `Bash(<命令>:<子命令>:*)`、`Bash(*)` 与裸 `Bash` 都算覆盖。"""
    for tok in re.findall(r"Bash\(([^)]*)\)", allowed):
        head = tok.split(":")[0].strip().lower()
        if head == biname or head == "*":
            return True
    return re.search(r"(^|[\s,])Bash($|[\s,])", allowed) is not None


def _cmd_binaries(block: str) -> set:
    """一个 bash 块里每条命令的起始二进制名（小写归一）。
    先抹引号与 `$( )`／反引号里的文本（`--jq '{…}'` 的 `select(` 不是命令）、去行内注释、
    跳过 heredoc 正文；`&&`、`;`、带空格的管道分段；`sudo`/`time`/`env` 这类前缀词后移。"""
    found, heredoc = set(), None
    for raw in block.splitlines():
        line = raw.strip()
        if heredoc:
            if line == heredoc:
                heredoc = None
            continue
        if not line or line.startswith("#"):
            continue
        hd = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", line)
        if hd:
            heredoc = hd.group(1)
        line = line.lstrip("$").strip()
        line = re.sub(r"'[^']*'", "''", line)
        line = re.sub(r'"[^"]*"', '""', line)
        line = re.sub(r"\$\([^)]*\)", "()", line)
        line = re.sub(r"`[^`]*`", "()", line)
        line = re.sub(r"\s+#\s.*$", "", line)
        for seg in re.split(r"&&|;|\s\|\s", line):
            seg = seg.strip()
            while True:
                m = CMD_LEAD_RE.match(seg)
                if not m:
                    break
                word = m.group(1).lower()
                if word in CMD_PREFIX_WORDS:
                    seg = seg[m.end():].strip()
                    continue
                if word not in CMD_SKIP_WORDS:
                    found.add(word)
                break
    return found


def chk_command_surface(root: str, ms=None):
    """技能自己声明要跑的命令，工具面没登记 ⇒ 到会硬拦白名单的宿主上就是一步步弹审批、停下来问人。
    `Bash(*)`、`Bash(<命令>:*)`、`Bash(<命令>:<子>:*)` 与裸 `Bash` 都算覆盖；
    不认为该命令由本技能跑的，把它移出 ```bash 块。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"技能清单不可用（01 已报）：{err}"
    bad, scanned, cmds = [], 0, 0
    for entry in sorted((e for e in data.get("skills") or [] if isinstance(e, dict)),
                        key=lambda e: str(e.get("name"))):
        name = str(entry.get("name") or "?")
        md = os.path.join(root, *str(entry.get("path") or "").split("/"), "SKILL.md")
        if not os.path.isfile(md):
            continue
        try:
            with open(md, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as exc:
            bad.append(f"{name}：读不出来 {exc!r}")
            continue
        scanned += 1
        at = _skill_allowed_tools(text)
        fences = CMD_FENCE_RE.findall(text)
        if fences and not at:
            bad.append(f"{name}：有 ```bash 块却没登记 allowed-tools")
        for block in fences:
            for biname in sorted(_cmd_binaries(block)):
                cmds += 1
                if _bash_covers(at, biname):
                    continue
                bad.append(f"{name} 缺 Bash({biname}:*)")
    if bad:
        uniq = sorted(set(bad))
        return "fail", (f"{len(bad)} 条声明要跑的命令不在该技能 allowed-tools 里：" + "；".join(uniq[:8])
                        + (f"（共 {len(uniq)} 处）" if len(uniq) > 8 else "")
                        + "。修法：按上面点名的 Bash(<命令>:*) 补进那个技能的 allowed-tools；"
                          "不该它跑的移出 ```bash 块")
    return "ok", (f"command-surface 扫了 {scanned} 份 SKILL.md 的 ```bash 块，"
                  f"{cmds} 条命令全部在各自 allowed-tools 内（无 bash 块的技能不计）")


def chk_vendor(root, ms):
    """19 vendor/：未纳入 git ⇒ 红（克隆不可复原）；本机无镜像 ⇒ skip；有镜像则跑 --check 比漂移。"""
    if not os.path.isdir(os.path.join(root, VENDOR_REL)):
        return "skip", "没有 vendor/（不适用）"
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            p = subprocess.run(["git", "-C", root, "ls-files", "--", VENDOR_REL],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        except (OSError, ValueError) as exc:
            return "skip", f"git 不可用：{exc}"
        if p.returncode == 0 and not p.stdout.strip():
            return "fail", "vendor/ 未纳入 git 跟踪（克隆出来会缺件）：git add -- vendor"
    script = os.path.join(root, *VENDOR_SYNC.split("/"))
    if not os.path.isfile(script):
        return "fail", f"缺件：{VENDOR_SYNC}"
    if not os.path.isdir(VENDOR_MIRROR):
        return "skip", f"本机无技能镜像（{VENDOR_MIRROR} 不存在），跨机不判漂移"
    try:
        p = subprocess.run([sys.executable, script, "--check"], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        return "skip", f"跑不动 {VENDOR_SYNC}：{exc}"
    out = " ".join(x.strip() for x in ((p.stdout or "") + (p.stderr or "")).splitlines() if x.strip())
    if p.returncode != 0:
        return "fail", f"{VENDOR_SYNC} --check rc={p.returncode}：{out}"
    return "ok", out.split("。")[0][:200] if out else "vendor 与源一致"


BUDGETS = (  # 层 → (glob 列表, 上限字节)。与项目仓治理体量的上限同尺，项目可更严、不可更松
    ("AGENTS.md", ("AGENTS.md",), 12 * 1024),
    ("协议正本", ("airport/skills/loop/references/*.md", "loops/*.md"), 40 * 1024),
    ("适配说明", ("adapters/*.md",), 16 * 1024),
    ("安装面 SKILL.md", ("*/skills/*/SKILL.md", "skills/*/SKILL.md"), 40 * 1024),
    ("技能内其它 md", ("*/skills/**/*.md", "skills/**/*.md"), 64 * 1024),
)


def chk_payload_budget(root: str, ms=None):
    """反膨胀的尺：按层卡字节，绿也打印每层最大件与余量（半盲的 ✅ 不算尺）。"""
    import glob as _glob

    lines, over, total = [], [], 0
    for label, patterns, cap in BUDGETS:
        files = []
        for pat in patterns:
            files.extend(_glob.glob(os.path.join(root, pat), recursive=True))
        files = [f for f in files if "__pycache__" not in f.split(os.sep)]
        if label == "技能内其它 md":
            files = [f for f in files if os.path.basename(f) != "SKILL.md"]
        if not files:
            continue
        sizes = {f: os.path.getsize(f) for f in files}
        total += sum(sizes.values())
        top = max(sizes, key=sizes.get)
        size = sizes[top]
        rel = os.path.relpath(top, root).replace(os.sep, "/")
        lines.append(f"{label} ≤{cap // 1024}KB：最大 {rel} {size / 1024:.1f}KB（{size * 100 // cap}%）")
        if size > cap:
            over.append(f"{rel} {size / 1024:.1f}KB > {cap // 1024}KB")
    if not lines:
        return "fail", "五层一层都没量到——量具覆盖为空＝这把尺是瞎的"
    if over:
        return "fail", "；".join(over[:4]) + f"（共 {len(over)} 层超限；量了 {len(lines)} 层 / 合计 {total / 1024:.0f}KB）"
    return "ok", "；".join(lines) + f"（合计 {total / 1024:.0f}KB）"


def chk_plugin_manifest(root: str, ms=None):
    """29 插件清单与版本锁：调用 scripts/plugin-check.py，清单/版本/摘要/档位不一致即红。"""
    script = os.path.join(root, "scripts", "plugin-check.py")
    if not os.path.isfile(script):
        return "skip", "没有 scripts/plugin-check.py（旧仓不适用）"
    try:
        p = subprocess.run([sys.executable, script, "--root", root], cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        return "fail", f"跑不动 plugin-check：{exc}"
    out = " ".join(x.strip() for x in ((p.stdout or "") + (p.stderr or "")).splitlines() if x.strip())
    if p.returncode != 0:
        return "fail", f"plugin-check rc={p.returncode}：{out[:600]}"
    return "ok", out.split("总结：")[-1][:300] if "总结：" in out else out[:300]


CHECKS = (
    ("registry-file", "注册表文件", chk_registry_file),
    ("registry-fields", "注册表字段", chk_registry_fields),
    ("plugin-manifest", "插件清单与版本锁", chk_plugin_manifest),
    ("skill-frontmatter", "frontmatter 与 name 三处一致", chk_frontmatter),
    ("frontmatter-yaml", "frontmatter YAML 形状", chk_frontmatter_yaml),
    ("unregistered-skill", "盘上技能都登记了", chk_unregistered),
    ("missing-skill-path", "注册条目路径都在", chk_missing_path),
    ("machine-path", "没有机器绝对路径", chk_machine_path),
    ("broken-link", "SKILL.md 相对链接都在", chk_broken_link),
    ("tracked-cache", "git 跟踪文件无缓存/运行数据/开发流水", chk_tracked_cache),
    ("gitattributes-bat", ".gitattributes 钉住 .bat 行尾", chk_gitattributes),
    ("install-set-match", "装机集合与注册表一致", chk_install_set),
    ("version-in-readme", "VERSION 与 README 口径一致", chk_version_readme),
    ("skill-tests", "各技能 pytest 全绿", chk_skill_tests),
    ("install-sync", "装机同步（库副本与来源）", chk_install_sync),
    ("install-profiles", "安装档位清单（core/full）", chk_install_profiles),
    ("install-receipt", "安装回执（档位/技能/哈希）", chk_install_receipt),
    ("package-layout", "三层打包边界（开发件/安装件/骨架）", chk_package_layout),
    ("config-instance", "配置实例零虚构值（实跑 init-project）", chk_config_instance),
    ("payload-refs", "安装面零开发史引用", chk_payload_refs),
    ("decoupling-gate", "解耦门（项目硬路径零残留）", chk_decoupling),
    ("host-neutral", "宿主专有 token 不进正本", chk_host_neutral),
    ("handoff-slots", "交接文档分类（槽位/命名/归位）", chk_handoff),
    ("skill-spec", "技能格式对齐 Agent Skills 1.2", chk_skill_spec),
    ("command-surface", "技能声明的命令在自己工具面里", chk_command_surface),
        ("canon-dup", "判据一个家（退役词/平行正本）", chk_canon),
    ("vendor-sync", "辅助技能原样副本（跟踪/漂移）", chk_vendor),
    ("payload-budget", "安装面字节预算（分层反膨胀）", chk_payload_budget),
)


def run_checks(root: str, with_tests: bool = False) -> list:
    ms = load_magpie_sync()
    results = []
    for cid, _title, fn in CHECKS:
        if cid == "skill-tests" and not with_tests:
            results.append({"id": cid, "status": "skip", "detail": "未加 --with-tests，跳过"})
            continue
        try:
            status, detail = fn(root, ms)
        except PermissionError as exc:  # 权限/安全层拦读：记跳过，不记红（红要能修）
            status, detail = "skip", f"读不到被拦的文件，本项跳过：{(exc.filename or exc)!r}"
        except Exception as exc:  # 校验器自身出错 ⇒ 记红，不吞
            status, detail = "fail", f"检查器异常：{exc!r}"
        results.append({"id": cid, "status": status, "detail": detail})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="kai-mode 框架仓 doctor")
    ap.add_argument("--root", default=None, help="仓根（默认＝脚本上溯一级）")
    ap.add_argument("--with-tests", action="store_true", help="追加跑各技能自己的 pytest")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    a = ap.parse_args()
    root = os.path.abspath(a.root) if a.root else OWN_ROOT
    results = run_checks(root, a.with_tests)
    reds = [r for r in results if r["status"] == "fail"]
    ok = not reds
    if a.json:
        print(json.dumps({"ok": ok, "checks": results}, ensure_ascii=False, indent=2))
    else:
        titles = {cid: title for cid, title, _ in CHECKS}
        print(f"kai-mode doctor —— 根 {root}")
        for r in results:
            label = {"ok": "绿", "fail": "红", "skip": "跳过"}[r["status"]]
            print(f"[{label}] {r['id']:<19} {titles.get(r['id'], '')}：{r['detail']}")
        n_ok = sum(1 for r in results if r["status"] == "ok")
        n_skip = sum(1 for r in results if r["status"] == "skip")
        print(f"总结：{len(results)} 项 ｜ 绿 {n_ok} ｜ 红 {len(reds)} ｜ 跳过 {n_skip} ｜ "
              f"结论：{'绿' if ok else '红'}（rc={0 if ok else 1}）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
