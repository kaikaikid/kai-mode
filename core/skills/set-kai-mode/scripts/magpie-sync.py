#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能回写中央库（#1819）
========================
本仓技能目录是正本，Magpie 中央库才是各家宿主真正读到的那份：库里每条是一个目录，
`~/.<agent>/skills/<名>` 是指向库目录的符号链接。正本与库是**拷贝**关系 ⇒ 「改了正本」≠「家家生效」。
本脚本把这一步变成一条命令，并让漂移可复查。
正本根认两种布局：项目仓落点读项目配置实例 `<root>/.ai/kai-mode.project.json` 的
`registry.skills.project_skills_dir`／`loop_dir`（无实例回落内置缺省）；框架仓 `skills/<名>`。
装机清单的单一事实源＝仓根 `registry.json`：只有 `install:auto` 的条目被拷贝、链到各家宿主、写进注册档；
没有 registry.json 的老根目录回落内置默认清单（照旧工作，不报错退出）。

用法：
    python magpie-sync.py check              # 只读：漂移表；有漂移 exit 1
    python magpie-sync.py apply              # 回写：正本 → 库 → 落点链接 → 注册档
    python magpie-sync.py apply --dry-run    # 只报将写哪些字节，盘上不动
    python magpie-sync.py --selftest         # 临时假库假落点跑一遍（不动真库）

三面判据（全部现算，不靠印象）：
  · 内容面 正本目录逐文件 SHA-256 == 库副本逐文件（缺件/多件都算漂移）
  · 落点面 凡已把 anchor（`kai-mode`）链到本库的宿主家目录，必须同样有该条且解引用回库
  · 注册面 `library.json` 的 `skills[]` 有条目，且每个铺了 anchor 的 `applied[*].skills` 含该名；
    条目另带 `source`（`kind`／`repo`／`path`）——Magpie 资源库页按它分组，缺了就落「本机」（只报 warn 不判红）

安全：只新增、只覆盖同路径文件，**绝不删除**库里多出来的东西；`library.json` 走临时档 + `os.replace`
原子替换，且写前自证「本次改动只允许末尾追加条目、或给缺 `source` 的既有条目补 `source`」，自证不过就中止不写。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

try:  # Windows 控制台下中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ANCHOR = "kai-mode"  # 库位与落点面都沿这条既有条目反查，不写死机器路径
LIBRARY_ENV = "KAI_MAGPIE_LIBRARY"
# 项目技能落点缺省（registry.skills 的模板缺省值）：只在项目配置实例
# 不在／没写 registry.skills 时回落用；实例给了就以实例为准（一个语义一个家）。
PROJECT_CONFIG = os.path.join(".ai", "kai-mode.project.json")
REGISTRY_SKILLS_DEFAULT = {
    "project_skills_dir": os.path.join(".ai", "skills", "project-skills"),
    "loop_dir": os.path.join(".ai", "skills", "loop"),
}
# 老根目录回落清单（无 registry.json 时用；值＝上面缺省布局的逐名展开）。
FAMILIES = {
    "kai-mode": os.path.join(".ai", "skills", "project-skills", "kai-mode"),
    "set-kai-mode": os.path.join(".ai", "skills", "project-skills", "set-kai-mode"),
    "loop": os.path.join(".ai", "skills", "loop"),
    "地勤": os.path.join(".ai", "skills", "project-skills", "地勤"),
    "塔台": os.path.join(".ai", "skills", "project-skills", "塔台"),
    "机长": os.path.join(".ai", "skills", "project-skills", "机长"),
    "副机长": os.path.join(".ai", "skills", "project-skills", "副机长"),
    "二副": os.path.join(".ai", "skills", "project-skills", "二副"),
    "航班信息": os.path.join(".ai", "skills", "project-skills", "航班信息"),
}
# 正本根认两种布局：项目仓落点（实例 registry.skills，缺省同上）与框架仓 `skills/<名>`。
ANCHOR_MARKERS = (
    os.path.join(REGISTRY_SKILLS_DEFAULT["project_skills_dir"], ANCHOR, "SKILL.md"),
    os.path.join("skills", ANCHOR, "SKILL.md"),
    os.path.join("core", "skills", ANCHOR, "SKILL.md"),
    os.path.join(".claude-plugin", "marketplace.json"),
)
ROOT_WALK_LIMIT = 8  # 上溯层级上限（脚本最深在仓根下 5 层，留余量）
# 装机清单的单一事实源＝仓根 registry.json；FAMILIES 只是「没有 registry.json 的老根目录」的回落清单。
REGISTRY_NAME = "registry.json"
REGISTRY_SCHEMA = "kai-mode-registry/1"
VALID_KINDS = ("framework", "personal")
VALID_SCOPES = ("global", "owner")
VALID_INSTALL = ("auto", "manual", "none")
REQUIRED_ENTRY_FIELDS = ("name", "path", "kind", "scope", "install", "summary")
# 装机来源标记：中央库记住「自己是从哪个仓装来的」——谁跑装机器都回那个仓，不被 cwd 里的项目仓顶掉。
SOURCE_MARKER_NAME = ".kai-mode-source.json"
SOURCE_SCHEMA = "kai-mode-source/1"
# 注册档每条的 `source.kind` 取值：Magpie 资源库页按 `source.repo`＋`source.path` 的父目录分组，
# 没有 `source` 的条目一律落「本机」。只认 GitHub 一种，别的远端不猜。
LIBRARY_SOURCE_KIND = "github"
PROFILES_REL = os.path.join("manifests", "install-profiles.json")
PROFILES_SCHEMA = "kai-mode-install-profiles/1"
BACKUP_DIR = ".backups"
BACKUP_KEEP = 5
RETIRED_DIR = ".retired"
# 角色改名的一次性迁移：旧中文目录 → 新英文目录。只在显式 --retire-legacy 时移动/摘链。
LEGACY_ALIASES = {
    "塔台": "tower",
    "机长": "pilot",
    "副机长": "copilot",
    "二副": "second-officer",
    "第二副机长": "second-officer",
    "地勤": "ground-crew",
    "航班信息": "flight-info",
    "set-航班信息": "flight-info",
}


def library_root(library: str) -> str:
    """中央库根＝library skills 目录的上一级（装机来源标记放这儿）。"""
    return os.path.dirname(os.path.abspath(library))


def source_marker_path(library: str) -> str:
    """装机来源标记文件：`<库根>/.kai-mode-source.json`。"""
    return os.path.join(library_root(library), SOURCE_MARKER_NAME)


def write_source_marker(library: str, root: str, skills: int, profile: str | None = None,
                        skill_names=None, hashes=None, source_commit: str | None = None) -> str:
    """apply 真跑完 ⇒ 记下来源、档位、技能清单与哈希：原子写（临时档 + os.replace）。
    旧字段 `skills` 仍是计数（向后兼容）；新增字段是安装回执。"""
    path = source_marker_path(library)
    data = {
        "schema": SOURCE_SCHEMA,
        "root": os.path.abspath(root),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "skills": skills,
        "profile": profile,
        "skill_names": list(skill_names or []),
        "hashes": dict(hashes or {}),
        "source_commit": source_commit,
    }
    fd, tmp = tempfile.mkstemp(prefix=".kai-mode-source.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SystemExit(f"装机来源标记写入失败：{exc}")
    return path


def read_source_marker(library: str) -> dict | None:
    """读库根安装回执；缺失/损坏/schema 不认识 ⇒ None。"""
    path = source_marker_path(library)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SOURCE_SCHEMA:
        return None
    return data


def marked_profile(library: str) -> str | None:
    data = read_source_marker(library) or {}
    profile = data.get("profile")
    return profile if isinstance(profile, str) and profile else None


def read_profiles(root: str) -> dict | None:
    """读 `manifests/install-profiles.json`；缺失 ⇒ None（旧根照旧全装）。"""
    path = os.path.join(root, PROFILES_REL)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"安装档位读不出：{path}（{exc}）")
    if not isinstance(data, dict) or data.get("schema") != PROFILES_SCHEMA:
        raise SystemExit(f"安装档位 schema 不认识：{path}")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SystemExit(f"安装档位为空：{path}")
    return profiles


def profile_skill_names(root: str, profile: str) -> list:
    profiles = read_profiles(root)
    if profiles is None:
        raise SystemExit(f"指定了 --profile {profile}，但 {PROFILES_REL} 不存在")
    item = profiles.get(profile)
    if not isinstance(item, dict):
        raise SystemExit(f"未知安装档位：{profile}（可选：{'、'.join(sorted(profiles))}）")
    names = item.get("skills")
    if not isinstance(names, list) or not names or not all(isinstance(x, str) and x for x in names):
        raise SystemExit(f"安装档位 {profile} 的 skills 必须是非空字符串数组")
    return names


def marked_root(lib_root: str) -> str | None:
    """读库根上的装机来源标记：指向一个**存在的目录** ⇒ 那是正本根；
    标记缺失／损坏／schema 不认识／目录没了 ⇒ None（不硬失败，走老路）。"""
    path = os.path.join(lib_root, SOURCE_MARKER_NAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SOURCE_SCHEMA:
        return None
    root = data.get("root")
    if not root or not os.path.isdir(root):
        return None
    return os.path.abspath(root)


def has_anchor(root: str) -> bool:
    """这个根下有没有 anchor 正本（两种布局任一）。"""
    return any(os.path.isfile(os.path.join(root, m)) for m in ANCHOR_MARKERS)


def read_project_config(root: str) -> tuple:
    """读项目配置实例 `<root>/.ai/kai-mode.project.json`。
    没有 ⇒ (None, None)；有但读不出/不是对象 ⇒ (None, 错误说明)。"""
    path = os.path.join(root, PROJECT_CONFIG)
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return None, f"项目配置实例读不出：{path}（{exc}）"
    if not isinstance(data, dict):
        return None, f"项目配置实例不是对象：{path}"
    return data, None


def skills_dirs(root: str | None) -> dict:
    """项目技能落点（registry.skills）：实例给了用实例的；
    无实例/字段缺 ⇒ 回落 REGISTRY_SKILLS_DEFAULT（模板缺省，仅此一处）。"""
    cfg, _err = read_project_config(root) if root else (None, None)
    skills = ((cfg or {}).get("registry") or {}).get("skills") or {}
    out = dict(REGISTRY_SKILLS_DEFAULT)
    for key in out:
        value = str(skills.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def default_source(name: str, root: str | None = None) -> str:
    """装机源缺省值：项目技能落点读配置实例 `registry.skills.*`；
    无实例回落 REGISTRY_SKILLS_DEFAULT。loop 用 loop_dir，其余住 project_skills_dir。"""
    dirs = skills_dirs(root)
    if name == "loop":
        return dirs["loop_dir"]
    return os.path.join(dirs["project_skills_dir"], name)


def read_skill_registry(root: str) -> tuple:
    """读 `<root>/registry.json`（仓内技能注册表）：没有 ⇒ (None, None)（回落内置清单）；
    有但读不出或 schema 不认识 ⇒ (None, 错误)（调用方退出非 0，不猜）。
    （中央库的注册档是另一个东西，见下面那个 `read_registry`。）"""
    path = os.path.join(root, REGISTRY_NAME)
    if not os.path.isfile(path):
        # Try marketplace layout if registry.json doesn't exist
        marketplace_path = os.path.join(root, ".claude-plugin", "marketplace.json")
        if os.path.isfile(marketplace_path):
            try:
                return synthesize_registry_from_marketplace(root, marketplace_path), None
            except SystemExit as exc:
                return None, str(exc)
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return None, f"注册档读不出：{path}（{exc}）"
    if not isinstance(data, dict):
        return None, f"注册档不是对象：{path}"
    if data.get("schema") != REGISTRY_SCHEMA:
        return None, f"注册档 schema 不认识：{path}（期望 {REGISTRY_SCHEMA}，读到 {data.get('schema')!r}）"
    return data, None


def _frontmatter_description(text: str) -> str:
    """取 frontmatter 里 description 的第一行正文（inline 或块式都认），取不到返回空串。"""
    m = re.search(r"^---\s*\n(.*?)\n---\s*$", text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    lines = m.group(1).splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("description:"):
            continue
        val = stripped[len("description:"):].strip()
        if val and val not in (">", "|", ">-", "|-", ">+", "|+"):
            return val
        for nxt in lines[i + 1:]:
            s = nxt.strip()
            if not s:
                continue
            if not nxt[:1].isspace():
                break  # 到了下一个顶层键
            return s
    return ""


def synthesize_registry_from_marketplace(root: str, marketplace_path: str) -> dict:
    """从 .claude-plugin/marketplace.json 合成注册表数据，保持向后兼容的内存形状。"""
    try:
        with open(marketplace_path, encoding="utf-8") as f:
            marketplace = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"市场清单读不出：{marketplace_path}（{exc}）")

    if not isinstance(marketplace, dict) or "plugins" not in marketplace:
        raise SystemExit(f"市场清单格式错误：{marketplace_path}（期望包含 'plugins' 键）")

    plugins = marketplace.get("plugins", [])
    if not isinstance(plugins, list) or not plugins:
        raise SystemExit(f"市场清单 plugins 为空：{marketplace_path}")

    skills = []

    for plugin in plugins:
        if not isinstance(plugin, dict):
            continue

        plugin_name = plugin.get("name")
        plugin_source = plugin.get("source")

        # Skip plugins with non-string/remote source
        if not isinstance(plugin_name, str) or not isinstance(plugin_source, str):
            continue

        # Skip remote sources (only local directory sources)
        if plugin_source.startswith(("http://", "https://", "git@", "github.com", "gitlab.com")):
            continue

        # Read plugin manifest
        plugin_dir = os.path.normpath(os.path.join(root, plugin_source))
        plugin_manifest_path = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")

        if not os.path.isfile(plugin_manifest_path):
            continue

        try:
            with open(plugin_manifest_path, encoding="utf-8") as f:
                plugin_manifest = json.load(f)
        except (OSError, ValueError):
            continue

        # Validate plugin manifest
        if not isinstance(plugin_manifest, dict) or plugin_manifest.get("name") != plugin_name:
            continue

        plugin_version = plugin_manifest.get("version", "0.0.0")

        # Find skills in this plugin
        skills_dir = os.path.join(plugin_dir, "skills")
        if os.path.isdir(skills_dir):
            for skill_name in os.listdir(skills_dir):
                skill_dir = os.path.join(skills_dir, skill_name)
                skill_md_path = os.path.join(skill_dir, "SKILL.md")

                if os.path.isdir(skill_dir) and os.path.isfile(skill_md_path):
                    # summary = frontmatter description 的第一行（取不到回落技能名）
                    summary = skill_name
                    try:
                        with open(skill_md_path, encoding="utf-8") as f:
                            summary = _frontmatter_description(f.read()) or skill_name
                    except (OSError, ValueError):
                        pass

                    # Add skill entry
                    install_type = "auto" if skill_name != "harness-audit" else "manual"
                    skills.append({
                        "name": skill_name,
                        "path": f"{plugin_name}/skills/{skill_name}",
                        "kind": "framework",
                        "scope": "global",
                        "install": install_type,
                        "summary": summary or skill_name,
                        "plugin": plugin_name,
                        "version": plugin_version,
                        "since": plugin_version
                    })

    return {
        "schema": "kai-mode-registry/1",
        "version": 1,
        "skills": skills
    }


def registry_entry_problems(data: dict) -> list:
    """注册档逐条字段校验：返回问题清单（空＝过）。装机尺与 doctor 共用这一份口径。"""
    problems = []
    for i, entry in enumerate(data.get("skills") or []):
        if not isinstance(entry, dict):
            problems.append(f"skills[{i}] 不是对象")
            continue
        for field in REQUIRED_ENTRY_FIELDS:
            if not str(entry.get(field) or "").strip():
                problems.append(f"skills[{i}].{field} 缺")
        if entry.get("kind") not in VALID_KINDS:
            problems.append(f"skills[{i}].kind 取值非法：{entry.get('kind')!r}")
        if entry.get("scope") not in VALID_SCOPES:
            problems.append(f"skills[{i}].scope 取值非法：{entry.get('scope')!r}")
        if entry.get("install") not in VALID_INSTALL:
            problems.append(f"skills[{i}].install 取值非法：{entry.get('install')!r}")
        if "tags" in entry and not isinstance(entry["tags"], list):
            problems.append(f"skills[{i}].tags 不是数组")
    return problems


def install_plan(root: str, profile: str | None = None) -> dict:
    """装机清单（name -> {"source", "path"}）：取注册表 `install == "auto"` 的条目；
    没有 registry.json（老根目录）⇒ 回落内置 FAMILIES，照旧工作，不报错退出。
    profile 给了就按 `manifests/install-profiles.json` 过滤；档位只能引用 auto 条目。"""
    data, err = read_skill_registry(root)
    if err:
        raise SystemExit(err)
    if data is None:
        plan = {name: {"source": default_source(name, root),
                       "path": os.path.join("skills", name)}
                for name in FAMILIES}
    else:
        plan = {}
        for entry in data.get("skills") or []:
            if not isinstance(entry, dict) or entry.get("install") != "auto":
                continue
            name = entry.get("name")
            if not name:
                continue
            plan[name] = {
                "source": entry.get("source") or default_source(name, root),
                "path": entry.get("path") or os.path.join("skills", name),
            }
    if not profile:
        return plan
    names = profile_skill_names(root, profile)
    unknown = sorted(set(names) - set(plan))
    if unknown:
        raise SystemExit(f"安装档位 {profile} 引用了非 install:auto 条目：{'、'.join(unknown)}")
    return {name: plan[name] for name in plan if name in set(names)}


def family_candidates(name: str, plan: dict | None = None, root: str | None = None) -> list:
    """某技能的候选源目录（相对正本根）：① 装机源（注册表 source，缺省读配置实例
    registry.skills）② 注册表 path（框架仓布局，如 `skills/flight-info`）③ `skills/<名>`；
    去重保序（去重按归一化后的路径算：`skills/x` 与 `skills\\x` 是同一个目录）。"""
    info = (plan or {}).get(name) or {}
    out, seen = [], set()
    for rel in (info.get("source") or default_source(name, root),
                info.get("path") or os.path.join("skills", name),
                os.path.join("skills", name)):
        if not rel:
            continue
        key = os.path.normpath(rel)
        if key in seen:
            continue
        seen.add(key)
        out.append(rel)
    return out


def family_src(root: str, name: str, plan: dict | None = None) -> str:
    """候选里第一个真实存在的源目录；都不在就退回首选（报错文案用）。"""
    plan = plan if plan is not None else install_plan(root)
    for rel in family_candidates(name, plan, root):
        p = os.path.join(root, rel)
        if os.path.isdir(p):
            return p
    return os.path.join(root, default_source(name, root))


def _ancestors(base: str, limit: int = ROOT_WALK_LIMIT) -> list:
    """从 base 自身起逐级上溯，最多 limit 层（含 base 本身）。"""
    out, cur = [], os.path.abspath(base)
    for _ in range(limit):
        out.append(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return out


def _root_candidates(script_dir: str | None = None) -> list:
    """候选正本根：脚本位置的上溯链在前，cwd 的上溯链在后（去重保序）。"""
    here = script_dir or os.path.dirname(os.path.abspath(__file__))
    out, seen = [], set()
    for base in (here, os.path.abspath(os.getcwd())):
        for anc in _ancestors(base):
            key = os.path.normcase(anc)
            if key in seen:
                continue
            seen.add(key)
            out.append(anc)
    return out


def _is_library_root(cand: str, lib: str | None) -> bool:
    """候选根本身是中央库根：要么是 `find_library()` 认出来的那个库的上一级，
    要么它自带装机来源标记（标记在 ⇒ 库根自证是库根，不靠外部发现）。"""
    if os.path.isfile(os.path.join(cand, SOURCE_MARKER_NAME)):
        return True
    if not lib:
        return False
    return os.path.realpath(os.path.join(cand, "skills")) == os.path.realpath(lib)


def default_root() -> str:
    """脚本位置反查的仓库根：项目仓布局下脚本住 `<repo>/<registry.skills>/set-kai-mode/scripts/`
    （缺省布局＝REGISTRY_SKILLS_DEFAULT，实例可改落点）⇒ 上溯五级是仓库根；
    框架仓布局下脚本住 `<repo>/skills/set-kai-mode/scripts/` ⇒ 上溯三级是仓库根。
    两种布局都试，谁有 anchor 正本谁算数；都没有就退回五级的老读数。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for up in (3, 4, 5):
        cand = os.path.abspath(os.path.join(here, *[".."] * up))
        if has_anchor(cand):
            return cand
    return os.path.abspath(os.path.join(here, *[".."] * 5))


def resolve_root(script_dir: str | None = None) -> str | None:
    """正本根：**中央库记住自己是从哪个仓装来的**（`<库根>/.kai-mode-source.json`）——
    候选里出现库根时先读那个标记：标记指向的仓就是正本根（谁跑都回本仓，不会被 cwd 里的项目仓顶掉）；
    标记缺失／坏／目录没了 ⇒ 维持老路（跳过库根，继续走脚本链 → cwd 链）。"""
    lib = find_library()
    cands = _root_candidates(script_dir)
    for cand in cands:
        if not _is_library_root(cand, lib):
            continue
        marked = marked_root(cand)
        if marked:
            return marked
    for cand in cands:
        if _is_library_root(cand, lib):
            continue
        if has_anchor(cand):
            return cand
    return None


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


CACHE_DIRS = ("__pycache__", ".pytest_cache")
PAYLOAD_LAYOUT_REL = os.path.join("manifests", "package-layout.json")
PAYLOAD_DEFAULT = {
    "exclude_dirs": CACHE_DIRS + ("tests",),
    "exclude_suffixes": (".pyc", ".pyo"),
}


def payload_rules(root: str) -> dict:
    """安装面排除规则＝manifests/package-layout.json 的 host_payload 段；老仓没有清单就回落缺省。"""
    path = os.path.join(root, PAYLOAD_LAYOUT_REL)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            hp = (data or {}).get("host_payload") or {}
            dirs = hp.get("exclude_dirs")
            sufs = hp.get("exclude_suffixes")
            if isinstance(dirs, list) and isinstance(sufs, list):
                return {"exclude_dirs": tuple(str(x) for x in dirs),
                        "exclude_suffixes": tuple(str(x) for x in sufs)}
        except (OSError, ValueError):
            pass
    return dict(PAYLOAD_DEFAULT)


def payload_files(root: str, rules: dict | None = None) -> dict:
    """安装面文件清单：跳过 tests/ 与缓存产物。
    技能自带的 pytest 是本仓开发件，装进中央库会被链到各家宿主，分不清哪份是正本。"""
    rules = rules or PAYLOAD_DEFAULT
    dirs_ex = set(rules.get("exclude_dirs") or ())
    suf_ex = tuple(rules.get("exclude_suffixes") or ())
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in dirs_ex]
        for name in files:
            if name.endswith(suf_ex):
                continue
            p = os.path.join(base, name)
            if not os.path.islink(p):
                out[os.path.relpath(p, root).replace(os.sep, "/")] = p
    return out


def prune_payload_excluded(library: str, name: str, rules: dict) -> list:
    """把技能目录里的开发件从中央库清掉；返回清掉的相对路径。只在 apply 非 dry 时调用。"""
    base_dir = os.path.join(library, name)
    if not os.path.isdir(base_dir):
        return []
    dirs_ex = set(rules.get("exclude_dirs") or ())
    suf_ex = tuple(rules.get("exclude_suffixes") or ())
    removed = []
    for base, dirs, files in os.walk(base_dir):
        for d in list(dirs):
            if d in dirs_ex:
                p = os.path.join(base, d)
                shutil.rmtree(p, ignore_errors=True)
                removed.append(os.path.relpath(p, base_dir).replace(os.sep, "/"))
                dirs.remove(d)
        for f in files:
            if f.endswith(suf_ex):
                p = os.path.join(base, f)
                os.remove(p)
                removed.append(os.path.relpath(p, base_dir).replace(os.sep, "/"))
    return removed


def tree_digest(root: str, rules: dict | None = None) -> str:
    """整棵技能安装面的稳定摘要：相对路径 + 每文件 SHA-256，用于回执比对。"""
    h = hashlib.sha256()
    for rel, p in sorted(payload_files(root, rules).items()):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(bytes.fromhex(sha256(p)))
        h.update(b"\0")
    return h.hexdigest()


def source_commit(root: str) -> str | None:
    """正本仓当前 HEAD；读不出（非 git／权限）⇒ None，不阻断安装。"""
    try:
        p = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


_REPO_INFO_CACHE: dict = {}


def github_repo_info(root: str) -> tuple:
    """读 remote origin 得 `(owner/repo, 仓顶层目录)`；不是 GitHub 仓 ⇒ `(None, None)`：
    宁可不贴来源标签，也不猜一个出处（贴错＝界面上把它归到别人的组里）。
    顶层目录单独取是有原因的——正本根按运行位置可能是仓根本身，也可能是仓里的某个插件目录
    （`resolve_root` 两条路），标签里的 `path` 必须对**仓**成立，不然同一个仓会分出自两种组名。
    按 root 缓存，一次 apply 只问一次 git。"""
    key = os.path.normcase(os.path.abspath(root))
    if key in _REPO_INFO_CACHE:
        return _REPO_INFO_CACHE[key]
    info = (None, None)
    try:
        top = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10)
        url = subprocess.run(["git", "-C", root, "config", "--get", "remote.origin.url"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10)
        m = re.search(r"github\.com[:/]?([\w.-]+)/([\w.-]+?)(?:\.git)?/?$",
                      (url.stdout or "").strip() if url.returncode == 0 else "")
        toplevel = (top.stdout or "").strip() if top.returncode == 0 else ""
        if m and toplevel:
            info = (f"{m.group(1)}/{m.group(2)}", os.path.normpath(toplevel))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        info = (None, None)
    _REPO_INFO_CACHE[key] = info
    return info


def skill_source(root: str, name: str, plan: dict | None = None) -> dict | None:
    """某条技能该贴的来源标签；仓没有 GitHub remote、或正本目录找不到 ⇒ None（不贴，别编）。
    `path` 取 `family_src` 真正解析到的那个正本目录，**相对仓顶层**、正斜杠：框架仓布局就是
    `<插件>/skills/<名>`，资源库页第二级分组（`core/skills` 那一档）即由此而来。"""
    repo, toplevel = github_repo_info(root)
    if not repo:
        return None
    src = family_src(root, name, plan)
    if not os.path.isdir(src):
        return None
    return {"kind": LIBRARY_SOURCE_KIND, "repo": repo,
            "path": os.path.relpath(src, toplevel).replace(os.sep, "/")}


def _backup_root(library: str) -> str:
    return os.path.join(library_root(library), BACKUP_DIR)


def backup_library(library: str) -> str | None:
    """写库前整包快照：技能副本 ＋ library.json ＋ 来源标记 ＋ 哈希基线。
    返回备份目录；库不存在则返回 None。"""
    if not os.path.isdir(library):
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup = os.path.join(_backup_root(library), stamp)
    os.makedirs(backup, exist_ok=True)
    shutil.copytree(library, os.path.join(backup, "skills"),
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    reg = registry_path(library)
    if os.path.isfile(reg):
        shutil.copy2(reg, os.path.join(backup, "library.json"))
    marker = source_marker_path(library)
    if os.path.isfile(marker):
        shutil.copy2(marker, os.path.join(backup, SOURCE_MARKER_NAME))
    baseline = {"created_at": datetime.now(timezone.utc).isoformat(),
                "library": os.path.abspath(library),
                "skills": {name: tree_digest(os.path.join(library, name))
                           for name in sorted(os.listdir(library))
                           if os.path.isdir(os.path.join(library, name))}}
    with open(os.path.join(backup, "backup.json"), "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    _prune_backups(library)
    return backup


def _prune_backups(library: str) -> None:
    root = _backup_root(library)
    if not os.path.isdir(root):
        return
    items = sorted(x for x in os.listdir(root) if os.path.isdir(os.path.join(root, x)))
    for old in items[:-BACKUP_KEEP]:
        shutil.rmtree(os.path.join(root, old), ignore_errors=True)


def restore_library(library: str, backup: str | None) -> bool:
    """从 backup_library 的快照还原技能、注册档与来源标记。"""
    if not backup or not os.path.isdir(backup):
        return False
    src = os.path.join(backup, "skills")
    if os.path.isdir(src):
        if os.path.isdir(library):
            shutil.rmtree(library)
        shutil.copytree(src, library)
    reg = os.path.join(backup, "library.json")
    if os.path.isfile(reg):
        shutil.copy2(reg, registry_path(library))
    marker = os.path.join(backup, SOURCE_MARKER_NAME)
    if os.path.isfile(marker):
        shutil.copy2(marker, source_marker_path(library))
    elif os.path.isfile(source_marker_path(library)):
        os.remove(source_marker_path(library))
    return True


def retire_registry_entries(library: str, names, dry: bool = False) -> list:
    """从中央库注册档删掉指定旧技能：只动 `skills[]` 与 `applied[*].skills`，
    其余任何字段变化都中止（宁可不动也不猜）。返回被删的条目名。"""
    path = registry_path(library)
    before, err = read_registry(library)
    if err:
        raise SystemExit(err)
    names = set(names)
    removed = sorted(s.get("name") for s in before.get("skills", [])
                     if isinstance(s, dict) and s.get("name") in names)
    if not removed:
        return []
    after = json.loads(json.dumps(before))
    after["skills"] = [s for s in after.get("skills", [])
                       if not (isinstance(s, dict) and s.get("name") in names)]
    for val in (after.get("applied") or {}).values():
        if isinstance(val, dict) and isinstance(val.get("skills"), list):
            val["skills"] = [x for x in val["skills"] if x not in names]
    # 自证只做了这两类删除：其余顶层字段与各 applied 的非 skills 字段必须原样
    for key in before:
        if key not in ("skills", "applied") and before[key] != after.get(key):
            raise SystemExit(f"退役注册档超出白名单：顶层 {key} 被改动，已中止")
    for plat, old in (before.get("applied") or {}).items():
        new = (after.get("applied") or {}).get(plat)
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise SystemExit(f"退役注册档超出白名单：applied.{plat} 形状变了，已中止")
        if set(old) != set(new):
            raise SystemExit(f"退役注册档超出白名单：applied.{plat} 键集合变了，已中止")
        for key in old:
            if key != "skills" and old[key] != new[key]:
                raise SystemExit(f"退役注册档超出白名单：applied.{plat}.{key} 被改动，已中止")
    if dry:
        return removed
    fd, tmp = tempfile.mkstemp(prefix="library.json.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(after, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SystemExit(f"退役注册档写入失败：{exc}")
    return removed


def retire_legacy(library: str, home: str | None = None, dry: bool = False) -> tuple:
    """显式迁移：把旧中文技能目录移到 `<库根>/.retired/<时间>/`，并摘掉各宿主指向旧目录的链接。
    只处理符号链接；遇到实体目录只报告、不动。返回 (moved, unlinked, skipped)。"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    retired_root = os.path.join(library_root(library), RETIRED_DIR, stamp)
    moved, unlinked, skipped = [], [], []
    faces = find_faces(library, home)
    for old, new in LEGACY_ALIASES.items():
        old_dir = os.path.join(library, old)
        old_real = os.path.realpath(old_dir)
        if os.path.isdir(old_dir):
            dest = os.path.join(retired_root, old)
            if dry:
                moved.append(f"{old} → {dest}")
            else:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(old_dir, dest)
                moved.append(f"{old} → {dest}")
        for face in faces:
            link = os.path.join(face, old)
            if not os.path.lexists(link):
                continue
            if os.path.islink(link) and os.path.realpath(link) == old_real:
                if dry:
                    unlinked.append(link)
                else:
                    os.remove(link)
                    unlinked.append(link)
            elif os.path.isdir(link) and not os.path.islink(link):
                skipped.append(f"{link}（实体目录，不删）")
    if not dry and (moved or unlinked or skipped):
        os.makedirs(retired_root, exist_ok=True)
        with open(os.path.join(retired_root, "retired.json"), "w", encoding="utf-8") as f:
            json.dump({"at": datetime.now(timezone.utc).isoformat(), "aliases": LEGACY_ALIASES,
                       "moved": moved, "unlinked": unlinked, "skipped": skipped},
                      f, ensure_ascii=False, indent=2)
            f.write("\n")
    return moved, unlinked, skipped


def retire_names(library: str, names, home: str | None = None, dry: bool = False) -> tuple:
    """显式退役指定技能：目录移到 `<库根>/.retired/<时间>/`，并摘掉各宿主指向它的链接。
    只处理符号链接；实体目录只报告、不动。返回 (moved, unlinked, skipped)。"""
    names = {str(n).strip() for n in (names or []) if str(n).strip()}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    retired_root = os.path.join(library_root(library), RETIRED_DIR, stamp)
    moved, unlinked, skipped = [], [], []
    faces = find_faces(library, home)
    for name in sorted(names):
        src = os.path.join(library, name)
        if not os.path.isdir(src):
            continue
        src_real = os.path.realpath(src)
        dest = os.path.join(retired_root, name)
        if dry:
            moved.append(f"{name} → {dest}")
        else:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)
            moved.append(f"{name} → {dest}")
        for face in faces:
            link = os.path.join(face, name)
            if not os.path.lexists(link):
                continue
            if os.path.islink(link) and os.path.realpath(link) == src_real:
                if dry:
                    unlinked.append(link)
                else:
                    os.remove(link)
                    unlinked.append(link)
            elif os.path.isdir(link) and not os.path.islink(link):
                skipped.append(f"{link}（实体目录，不删）")
    if not dry and (moved or unlinked or skipped):
        os.makedirs(retired_root, exist_ok=True)
        with open(os.path.join(retired_root, "retired.json"), "w", encoding="utf-8") as f:
            json.dump({"at": datetime.now(timezone.utc).isoformat(), "names": sorted(names),
                       "moved": moved, "unlinked": unlinked, "skipped": skipped},
                      f, ensure_ascii=False, indent=2)
            f.write("\n")
    return moved, unlinked, skipped


def find_library(home: str | None = None) -> str | None:
    home = home or os.path.expanduser("~")
    env = os.environ.get(LIBRARY_ENV)
    if env:
        return os.path.abspath(os.path.expanduser(env))
    for entry in sorted(os.listdir(home)):
        link = os.path.join(home, entry, "skills", ANCHOR)
        if os.path.isdir(link) and os.path.islink(link):
            real = os.path.realpath(link)
            if os.path.isfile(os.path.join(real, "SKILL.md")):
                return os.path.dirname(real)
    return None


def find_faces(library: str, home: str | None = None) -> list:
    """落点面＝凡把 anchor 链到本库的那些 `<家>/skills` 目录。"""
    home = home or os.path.expanduser("~")
    if not os.path.isdir(home):
        return []
    lib_anchor = os.path.realpath(os.path.join(library, ANCHOR))
    faces = []
    for entry in sorted(os.listdir(home)):
        sdir = os.path.join(home, entry, "skills")
        link = os.path.join(sdir, ANCHOR)
        if os.path.isdir(sdir) and os.path.islink(link) and os.path.realpath(link) == lib_anchor:
            faces.append(sdir)
    return faces


def registry_path(library: str) -> str:
    return os.path.join(os.path.dirname(os.path.dirname(library)), "library.json")


def read_registry(library: str):
    path = registry_path(library)
    if not os.path.isfile(path):
        return None, f"注册档不存在：{path}"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, ValueError) as exc:
        return None, f"注册档读不出：{path}（{exc}）"


def check(root: str, library: str, home: str | None = None, plan: dict | None = None) -> tuple:
    rows, drifted = [], False
    faces = find_faces(library, home)
    data, reg_err = read_registry(library)
    plan = plan if plan is not None else install_plan(root)
    rules = payload_rules(root)
    for name in plan:
        src, dst = family_src(root, name, plan), os.path.join(library, name)
        if not os.path.isdir(src):
            tried = "、".join(os.path.join(root, r) for r in family_candidates(name, plan, root))
            rows.append((name, "正本缺失", f"试过：{tried}", src, "red"))
            drifted = True
            continue
        a = payload_files(src, rules)
        b = payload_files(dst, rules) if os.path.isdir(dst) else {}
        missing = sorted(set(a) - set(b))
        extra = sorted(set(b) - set(a))
        diff = sorted(p for p in set(a) & set(b) if sha256(a[p]) != sha256(b[p]))
        if not os.path.isdir(dst):
            status, detail, kind = "库内无此条", f"正本 {len(a)} 件", "red"
        elif diff or missing:
            status, detail, kind = "漂移", f"正本 {len(a)}／库 {len(b)}：内容不符 {len(diff)} 缺 {len(missing)}", "red"
        elif extra:
            status, detail, kind = "库内多件", f"多出 {extra}", "warn"
        else:
            status, detail, kind = "一致", f"{len(a)} 件逐字相同", "ok"
        if kind == "red":
            drifted = True
        rows.append((name, status, detail, "", kind))
        for p in diff:
            rows.append((f"    · {p}", "内容不符", sha256(a[p])[:12] + " ↔ " + sha256(b[p])[:12], "", "red"))
    for name in plan:
        absent = [f for f in faces if not os.path.lexists(os.path.join(f, name))]
        if absent:
            drifted = True
            rows.append((name, "落点缺失", f"{len(faces) - len(absent)}/{len(faces)} 家", ";".join(absent), "red"))
    if reg_err:
        drifted = True
        rows.append(("注册档", "读不出", reg_err, "", "red"))
    else:
        names = {s.get("name") for s in data.get("skills", []) if isinstance(s, dict)}
        reg = {s.get("name"): s for s in data.get("skills", []) if isinstance(s, dict)}
        for name in plan:
            if name not in names:
                drifted = True
                rows.append((name, "注册缺条目", registry_path(library), "", "red"))
            elif not (reg.get(name) or {}).get("source"):
                # 只报不判红：仓本来没有 GitHub remote 时就该没有标签，判红会让 apply 把整包回滚
                rows.append((name, "缺来源标签", "资源库页把它落在「本机」；跑 apply 会自动补", "", "warn"))
    return rows, drifted, len(faces)


def conflict_rows(rows: list, plan: dict) -> list:
    """同名不同内容（库/宿主已有副本与正本不符）＝需要用户抉择去留的那几条。"""
    return [{"name": r[0], "status": r[1], "detail": r[2]}
            for r in rows if r[0] in plan and r[1] == "漂移"]


def copy_family(root: str, library: str, name: str, dry: bool, plan: dict | None = None) -> list:
    src = family_src(root, name, plan)
    written = []
    if not os.path.isdir(src):
        return written
    for rel, p in sorted(payload_files(src, payload_rules(root)).items()):
        dst = os.path.join(library, name, *rel.split("/"))
        if os.path.isfile(dst) and sha256(dst) == sha256(p):
            continue
        if not dry:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)
        written.append(f"{name}/{rel}")
    return written


def _only_additions(before: dict, after: dict, names) -> str | None:
    """注册档允许的改动＝末尾追加条目，＋给原来没有 `source` 的既有条目补 `source`；
    越界就报原因（宁可中止也不猜）。"""
    if set(before) != set(after):
        return "顶层键集合变了"
    for key in before:
        b, a = before[key], after[key]
        if key == "skills" and isinstance(b, list) and isinstance(a, list):
            if len(a) < len(b):
                return "skills[] 条目变少"
            for i, old in enumerate(b):
                new = a[i]
                if old == new:
                    continue
                ok = (isinstance(old, dict) and isinstance(new, dict)
                      and "source" not in old and isinstance(new.get("source"), dict)
                      and set(new) - set(old) == {"source"}
                      and all(new.get(k) == old[k] for k in old))
                if not ok:
                    who = old.get("name") if isinstance(old, dict) else f"#{i}"
                    return f"skills[] 既有条目 {who} 只许补 source，别的字段与顺序都不许动"
            known = {x.get("name") for x in b if isinstance(x, dict)}
            for extra in a[len(b):]:
                if not isinstance(extra, dict) or extra.get("name") not in names or extra["name"] in known:
                    return "skills[] 追加项不在本次名单"
        elif key == "applied" and isinstance(b, dict) and isinstance(a, dict):
            for plat, val in b.items():
                new = a.get(plat)
                if not isinstance(new, dict) or set(val) != set(new):
                    return f"applied.{plat} 键集合变了"
                for field, old_list in val.items():
                    if field != "skills":
                        if new[field] != old_list:
                            return f"applied.{plat}.{field} 被改写"
                    elif new[field][: len(old_list)] != old_list:
                        return f"applied.{plat}.skills 既有条目被改写或换序"
        elif b != a and key not in ("skills", "applied"):
            return f"{key} 被改写"
    return None


def patch_registry(library: str, names, dry: bool = False, sources: dict | None = None) -> list:
    """注册面写入：新条目末尾追加（带来源标签），既有条目只补缺失的 `source`，别的字段一律不动。
    `sources`＝{技能名: {"kind","repo","path"}}；给 None 或没这个键 ⇒ 该条不贴标签（照旧工作）。"""
    path = registry_path(library)
    before, err = read_registry(library)
    if err:
        raise SystemExit(err)
    after = json.loads(json.dumps(before))
    anchor_entry = next((s for s in before.get("skills", []) if s.get("name") == ANCHOR), {})
    agents = list(anchor_entry.get("agents") or [])
    added = []
    sources = sources or {}
    by_name = {s.get("name"): s for s in after.get("skills", []) if isinstance(s, dict)}
    for name in names:
        src = sources.get(name)
        entry = by_name.get(name)
        if entry is None:
            new = {"name": name}
            if src:
                new["source"] = dict(src)
            if agents:
                new["agents"] = list(agents)
            after.setdefault("skills", []).append(new)
            added.append(f"skills[] += {name}" + ("（带来源）" if src else ""))
            continue
        if src and "source" not in entry:
            entry["source"] = dict(src)
            added.append(f"skills[] ~ {name} 补来源 → {src['repo']} 的 {src['path']}")
    for plat, val in (after.get("applied") or {}).items():
        if not isinstance(val, dict) or ANCHOR not in (val.get("skills") or []):
            continue
        for name in names:
            if name not in val["skills"]:
                val["skills"].append(name)
                added.append(f"applied.{plat}.skills += {name}")
    if not added:
        return added
    reason = _only_additions(before, after, names)
    if reason:
        raise SystemExit(f"注册档改动面超出「仅新增」，已中止（真库未写）：{reason}")
    if dry:
        return added
    fd, tmp = tempfile.mkstemp(prefix="library.json.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(after, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SystemExit(f"注册档写入失败（多半是宿主正持着这个文件）：{exc}")
    return added


def link_faces(library: str, names, home: str | None = None, dry: bool = False):
    faces = find_faces(library, home)
    made, failed = [], []
    for name in names:
        target = os.path.join(library, name)
        for f in faces:
            link = os.path.join(f, name)
            if os.path.islink(link):
                continue
            if os.path.lexists(link):
                failed.append(f"{link}（已存在实体目录，不覆盖）")
                continue
            if dry:
                made.append(link)
                continue
            try:
                os.symlink(target, link, target_is_directory=True)
            except OSError as exc:
                failed.append(f"{link}（{exc.strerror}）")
                continue
            made.append(link)
    return made, failed


def apply(root: str, library: str, dry: bool, home: str | None = None,
          plan: dict | None = None, profile: str | None = None, retire: bool = False,
          skip: set | None = None, retire_names_list: set | None = None) -> int:
    plan = plan if plan is not None else install_plan(root, profile)
    skip_names = {str(n).strip() for n in (skip or []) if str(n).strip()}
    unknown = sorted(skip_names - set(plan))
    if unknown:
        print(f"  跳过名单里有不在安装面的名字（忽略）：{'、'.join(unknown)}")
    targets = [n for n in plan if n not in skip_names]
    rows, drifted, nfaces = check(root, library, home, plan)
    print(f"正本根={root}  库={library}  档位={profile or 'full'}  落点面={nfaces} 家  "
          f"写前漂移={'有' if drifted else '无'}")
    for name in sorted(skip_names & set(plan)):
        print(f"  保留现有 {name}（--skip：用户选择不去覆盖）")
    had_library = os.path.isdir(library)
    backup = None if dry else backup_library(library)
    if backup:
        print(f"  写前备份 {backup}")
    written, added, made, failed, marker = [], [], [], [], None
    rules = payload_rules(root)
    pruned = []
    try:
        for name in targets:
            written += copy_family(root, library, name, dry, plan)
            if not dry:
                pruned += [f"{name}/{rel}" for rel in prune_payload_excluded(library, name, rules)]
        sources = {n: s for n, s in ((n, skill_source(root, n, plan)) for n in targets) if s}
        if dry:
            try:
                added = patch_registry(library, list(targets), dry=True, sources=sources)
            except SystemExit as exc:
                print(f"  注册档预演被自证挡下：{exc}")
        else:
            added = patch_registry(library, list(targets), sources=sources)
        made, failed = link_faces(library, list(targets), home, dry)
        if not dry:
            hashes = {name: tree_digest(family_src(root, name, plan), rules) for name in targets}
            marker = write_source_marker(
                library, root, len(targets), profile=profile or marked_profile(library),
                skill_names=list(targets), hashes=hashes, source_commit=source_commit(root))
    except BaseException as exc:
        if backup and restore_library(library, backup):
            print(f"  apply 失败，已从备份还原：{backup}")
        elif not dry and not had_library and os.path.isdir(library):
            shutil.rmtree(library, ignore_errors=True)
        raise SystemExit(f"apply 失败：{exc}")
    for p in written:
        print(f"  {'将写' if dry else '写入'} {p}")
    for p in pruned:
        print(f"  清开发件 {p}")
    for a in added:
        print(f"  注册 {a}")
    for l in made:
        print(f"  链接 {'将建' if dry else '建好'} {l}")
    for f in failed:
        print(f"  落点失败 {f}")
    if marker:
        print(f"  安装回执 {marker}（来源根／档位／技能哈希）")
    if dry:
        if retire_names_list:
            removed = retire_registry_entries(library, retire_names_list, dry=True)
            moved, unlinked, skipped = retire_names(library, retire_names_list, home, dry=True)
            for x in removed:
                print(f"  将退役注册条目 {x}")
            for x in moved:
                print(f"  将退役目录 {x}")
            for x in unlinked:
                print(f"  将摘链 {x}")
            for x in skipped:
                print(f"  退役跳过 {x}")
        if retire:
            removed = retire_registry_entries(library, LEGACY_ALIASES, dry=True)
            moved, unlinked, skipped = retire_legacy(library, home, dry=True)
            for x in removed:
                print(f"  将退役注册条目 {x}")
            for x in moved:
                print(f"  将退役目录 {x}")
            for x in unlinked:
                print(f"  将摘链 {x}")
            for x in skipped:
                print(f"  退役跳过 {x}")
        print("（dry-run：盘上未改动）")
        return 0
    _rows, drifted2, _n = check(root, library, home, {n: plan[n] for n in targets})
    if drifted2:
        if backup and restore_library(library, backup):
            print(f"回写后复量仍有漂移，已从备份还原：{backup}")
        else:
            print("回写后复量仍有漂移（无备份可还原）")
        return 1
    print("回写后复量：三面全绿")
    if retire_names_list:
        try:
            removed = retire_registry_entries(library, retire_names_list)
            moved, unlinked, skipped = retire_names(library, retire_names_list, home, dry=False)
        except (OSError, SystemExit) as exc:
            print(f"  退役失败：{exc}")
            return 1
        for x in removed:
            print(f"  退役注册条目 {x}")
        for x in moved:
            print(f"  退役目录 {x}")
        for x in unlinked:
            print(f"  摘旧链 {x}")
        for x in skipped:
            print(f"  退役跳过 {x}")
    if retire:
        try:
            removed = retire_registry_entries(library, LEGACY_ALIASES)
            moved, unlinked, skipped = retire_legacy(library, home, dry=False)
        except (OSError, SystemExit) as exc:
            print(f"  旧角色退役失败：{exc}")
            return 1
        for x in removed:
            print(f"  退役注册条目 {x}")
        for x in moved:
            print(f"  退役目录 {x}")
        for x in unlinked:
            print(f"  摘旧链 {x}")
        for x in skipped:
            print(f"  退役跳过 {x}")
    return 0


def selftest() -> int:
    """假库＋假落点面：先证明这把尺会响，再证明 apply 能把它按成绿（可达绿路）。"""
    fails = []
    picked = resolve_root()
    if picked is None:
        fails.append(f"正本根读不出（脚本上溯={default_root()} · cwd={os.path.abspath(os.getcwd())} 两处都没有 anchor 正本）")
    else:
        print(f"  正本根自证：{picked}")
    tmp = tempfile.mkdtemp(prefix="magpie-sync-selftest-")
    home = os.path.join(tmp, "home")
    try:
        root = os.path.join(tmp, "repo")
        library = os.path.join(tmp, "data", "library", "skills")
        os.makedirs(home)
        for rel in FAMILIES.values():
            os.makedirs(os.path.join(root, rel), exist_ok=True)
            with open(os.path.join(root, rel, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: t\n---\n# 正本\n")
        # 项目仓布局优先：同名框架仓布局也在时，family_src 仍先认 `.ai/skills/...`
        for name in FAMILIES:
            alt = os.path.join(root, "skills", name)
            os.makedirs(alt, exist_ok=True)
            with open(os.path.join(alt, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: alt\n---\n# 框架仓布局同名件\n")
        for name in FAMILIES:
            got = family_src(root, name)
            if got != os.path.join(root, FAMILIES[name]):
                fails.append(f"{name} 项目仓布局没被优先认（读到 {got}）")
        # 框架仓布局：skills/<名>/SKILL.md 要能被 family_src 认出来
        fw_root = os.path.join(tmp, "fwrepo")
        for name in FAMILIES:
            d = os.path.join(fw_root, "skills", name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: t\n---\n# 框架仓正本\n")
        for name in FAMILIES:
            got = family_src(fw_root, name)
            if got != os.path.join(fw_root, "skills", name):
                fails.append(f"{name} 框架仓布局没被 family_src 认出（读到 {got}）")
        # 项目配置实例 registry.skills 自定义落点：装机源缺省要认实例
        cfg_root = os.path.join(tmp, "cfgrepo")
        custom_dir = os.path.join(".ai", "skills", "custom")
        custom_loop = os.path.join(".ai", "skills", "custom-loop")
        os.makedirs(os.path.join(cfg_root, custom_dir, ANCHOR), exist_ok=True)
        os.makedirs(os.path.join(cfg_root, custom_loop), exist_ok=True)
        with open(os.path.join(cfg_root, PROJECT_CONFIG), "w", encoding="utf-8") as f:
            json.dump({"schema": 4, "registry": {"skills": {
                "project_skills_dir": custom_dir, "loop_dir": custom_loop}}},
                f, ensure_ascii=False)
        got = family_src(cfg_root, ANCHOR, install_plan(cfg_root))
        if os.path.normcase(got) != os.path.normcase(
                os.path.join(cfg_root, custom_dir, ANCHOR)):
            fails.append(f"实例 registry.skills 自定义落点没被认（读到 {got}）")
        if default_source("loop", cfg_root) != custom_loop:
            fails.append(f"loop 没按实例 registry.skills.loop_dir 读（读到 {default_source('loop', cfg_root)}）")
        # 无实例的根照旧回落模板缺省布局
        if default_source("loop", None) != REGISTRY_SKILLS_DEFAULT["loop_dir"]:
            fails.append("无实例时 loop 缺省回落不对")
        # 没有 registry.json 的根 ⇒ 回落内置清单（老根目录照旧工作）
        fallback = install_plan(root)
        if len(fallback) != len(FAMILIES):
            fails.append(f"无 registry.json 的根应回落内置 {len(FAMILIES)} 条，读到 {len(fallback)}")
        # 有 skills/kai-mode/SKILL.md 的仓，正本根必须读得出（不再报「正本根读不出」）
        fw_script = os.path.join(fw_root, "skills", "set-kai-mode", "scripts")
        os.makedirs(fw_script, exist_ok=True)
        picked_fw = resolve_root(script_dir=fw_script)
        if picked_fw is None:
            fails.append("框架仓布局仍读不出正本根")
        elif os.path.normcase(picked_fw) != os.path.normcase(os.path.abspath(fw_root)):
            fails.append(f"框架仓布局正本根认错：{picked_fw}")
        # 装机来源标记：库记住自己是从哪个仓装来的 ⇒ 谁跑都回那个仓，不被 cwd 里的项目仓顶掉
        marked_repo = os.path.join(tmp, "markedrepo")
        os.makedirs(os.path.join(marked_repo, "skills", ANCHOR), exist_ok=True)
        with open(os.path.join(marked_repo, "skills", ANCHOR, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: t\n---\n# 正本\n")
        fake_lib_root = os.path.join(tmp, "fakelib")
        fake_lib = os.path.join(fake_lib_root, "skills")
        fake_script = os.path.join(fake_lib, "set-kai-mode", "scripts")
        os.makedirs(fake_script, exist_ok=True)
        # 像项目仓的 cwd：它也有 .ai/skills/project-skills/kai-mode/SKILL.md
        fake_proj = os.path.join(tmp, "fakeproj")
        os.makedirs(os.path.join(fake_proj, ".ai", "skills", "project-skills", ANCHOR), exist_ok=True)
        with open(os.path.join(fake_proj, ".ai", "skills", "project-skills", ANCHOR, "SKILL.md"),
                  "w", encoding="utf-8") as f:
            f.write("---\nname: t\n---\n# 项目仓旧版\n")
        old_cwd = os.getcwd()
        os.chdir(fake_proj)
        try:
            picked_nomark = resolve_root(script_dir=fake_script)
        finally:
            os.chdir(old_cwd)
        if os.path.normcase(picked_nomark or "") != os.path.normcase(os.path.abspath(fake_proj)):
            fails.append(f"无标记时应维持老路（走 cwd 链拿到项目仓根），读到 {picked_nomark}")
        with open(os.path.join(fake_lib_root, SOURCE_MARKER_NAME), "w", encoding="utf-8") as f:
            json.dump({"schema": SOURCE_SCHEMA, "root": os.path.abspath(marked_repo),
                       "applied_at": "2026-10-22T00:00:00+00:00", "skills": 1}, f, ensure_ascii=False)
        os.chdir(fake_proj)
        try:
            picked_mark = resolve_root(script_dir=fake_script)
        finally:
            os.chdir(old_cwd)
        if os.path.normcase(picked_mark or "") != os.path.normcase(os.path.abspath(marked_repo)):
            fails.append(f"有标记时正本根应是标记里那个仓（不是 cwd 里的项目仓），读到 {picked_mark}")
        os.makedirs(os.path.join(library, ANCHOR))
        with open(os.path.join(library, ANCHOR, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: t\n---\n# 库内旧版\n")
        face = os.path.join(home, ".fakeagent", "skills")
        os.makedirs(face)
        os.symlink(os.path.join(library, ANCHOR), os.path.join(face, ANCHOR), target_is_directory=True)
        with open(registry_path(library), "w", encoding="utf-8") as f:
            json.dump(
                {"skills": [{"name": ANCHOR, "agents": ["fake"]}], "icons": {"x": 1},
                 "applied": {"fake": {"skills": [ANCHOR]}, "other": {"skills": ["zzz"], "mcp": ["keep"]}}},
                f,
                ensure_ascii=False,
            )
        rows, drifted, nfaces = check(root, library, home)
        if not drifted:
            fails.append("预置漂移没被抓到（尺不响）")
        if nfaces != 1:
            fails.append(f"假落点面读到 {nfaces} 家，应为 1")
        for want in ("漂移", "落点缺失", "注册缺条目"):
            if not any(r[1] == want for r in rows):
                fails.append(f"三面里没报「{want}」")
        rc = apply(root, library, dry=False, home=home)
        if rc != 0:
            fails.append(f"apply 后仍有漂移 rc={rc}")
        for name in FAMILIES:
            a = os.path.join(root, FAMILIES[name], "SKILL.md")
            b = os.path.join(library, name, "SKILL.md")
            if sha256(a) != sha256(b):
                fails.append(f"{name} 正本/库副本哈希不等")
            if os.path.realpath(os.path.join(face, name)) != os.path.realpath(os.path.join(library, name)):
                fails.append(f"{name} 落点链接没指回库")
        with open(registry_path(library), encoding="utf-8") as f:
            after = json.load(f)
        if len(after["skills"]) != len(FAMILIES):  # 假库起手只有 anchor，本次补齐其余全部
            fails.append(f"注册档条目数应为 {len(FAMILIES)}，读到 {len(after['skills'])}")
        if after.get("icons") != {"x": 1} or after["applied"]["other"] != {"skills": ["zzz"], "mcp": ["keep"]}:
            fails.append("注册档动了无关条目")
        # 真 apply ⇒ 库根出现装机来源标记，内容里的 root 就是本次正本根
        marker_path = source_marker_path(library)
        if not os.path.isfile(marker_path):
            fails.append(f"apply 后库根没有装机来源标记：{marker_path}")
        else:
            with open(marker_path, encoding="utf-8") as f:
                marker = json.load(f)
            if marker.get("schema") != SOURCE_SCHEMA:
                fails.append(f"装机来源标记 schema 不对：{marker.get('schema')}")
            if os.path.normcase(str(marker.get("root") or "")) != os.path.normcase(os.path.abspath(root)):
                fails.append(f"装机来源标记的 root 不是本次正本根：{marker.get('root')}")
            if marker.get("skills") != len(FAMILIES):
                fails.append(f"装机来源标记的 skills 应为 {len(FAMILIES)}，读到 {marker.get('skills')}")
        # 幂等：再跑一次不该写出任何字节
        again = []
        for name in FAMILIES:
            again += copy_family(root, library, name, dry=False)
        if again:
            fails.append(f"二次 apply 仍在写字节（不幂等）：{again}")
        # 带 registry.json 的假根：install:auto 的装，manual/none 的不装（不进库、不建链接、不进注册档）
        reg_root = os.path.join(tmp, "regrepo")
        reg_library = os.path.join(tmp, "regdata", "library", "skills")
        reg_face = os.path.join(home, ".regagent", "skills")
        os.makedirs(reg_root)
        reg_entries = [
            {"name": ANCHOR, "path": f"skills/{ANCHOR}", "kind": "framework", "scope": "global",
             "install": "auto", "summary": "入口"},
            {"name": "auto-x", "path": "skills/auto-x", "kind": "personal", "scope": "owner",
             "install": "auto", "summary": "该装"},
            {"name": "manual-x", "path": "skills/manual-x", "kind": "personal", "scope": "owner",
             "install": "manual", "summary": "手工装"},
            {"name": "none-x", "path": "skills/none-x", "kind": "personal", "scope": "owner",
             "install": "none", "summary": "不装"},
        ]
        for e in reg_entries:
            d = os.path.join(reg_root, *e["path"].split("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(f"---\nname: {e['name']}\n---\n# 正本\n")
        with open(os.path.join(reg_root, REGISTRY_NAME), "w", encoding="utf-8") as f:
            json.dump({"schema": REGISTRY_SCHEMA, "version": 1, "skills": reg_entries}, f, ensure_ascii=False)
        os.makedirs(os.path.join(reg_library, ANCHOR))
        with open(os.path.join(reg_library, ANCHOR, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: t\n---\n# 库内旧版\n")
        os.makedirs(reg_face)
        os.symlink(os.path.join(reg_library, ANCHOR), os.path.join(reg_face, ANCHOR), target_is_directory=True)
        with open(registry_path(reg_library), "w", encoding="utf-8") as f:
            json.dump({"skills": [{"name": ANCHOR, "agents": ["fake"]}], "icons": {"x": 1}, "applied": {}},
                      f, ensure_ascii=False)
        # dry-run ⇒ 绝不写装机来源标记
        apply(reg_root, reg_library, dry=True, home=home)
        if os.path.exists(source_marker_path(reg_library)):
            fails.append("dry-run 竟写了装机来源标记")
        rc_reg = apply(reg_root, reg_library, dry=False, home=home)
        if rc_reg != 0:
            fails.append(f"注册表驱动的 apply 没收敛 rc={rc_reg}")
        reg_marker = source_marker_path(reg_library)
        if not os.path.isfile(reg_marker):
            fails.append(f"apply 后库根没有装机来源标记：{reg_marker}")
        else:
            with open(reg_marker, encoding="utf-8") as f:
                reg_marker_data = json.load(f)
            if os.path.normcase(str(reg_marker_data.get("root") or "")) != os.path.normcase(os.path.abspath(reg_root)):
                fails.append(f"装机来源标记的 root 不是本次正本根：{reg_marker_data.get('root')}")
        if not os.path.isdir(os.path.join(reg_library, "auto-x")):
            fails.append("auto-x 是 install:auto 却没装进库")
        if os.path.realpath(os.path.join(reg_face, "auto-x")) != os.path.realpath(os.path.join(reg_library, "auto-x")):
            fails.append("auto-x 落点链接没指回库")
        for name in ("manual-x", "none-x"):
            if os.path.isdir(os.path.join(reg_library, name)):
                fails.append(f"{name} 不是 install:auto 却进了库")
            if os.path.lexists(os.path.join(reg_face, name)):
                fails.append(f"{name} 不是 install:auto 却建了落点链接")
        with open(registry_path(reg_library), encoding="utf-8") as f:
            reg_after = json.load(f)
        reg_names = {s.get("name") for s in reg_after["skills"]}
        if "auto-x" not in reg_names:
            fails.append("注册档少了 auto-x")
        for name in ("manual-x", "none-x"):
            if name in reg_names:
                fails.append(f"注册档多了非 auto 条目 {name}")
        # 来源标签：Magpie 资源库页按 `source.repo`＋`source.path` 的父目录分组，没有它就落「本机」。
        # 有 GitHub remote ⇒ 新条目带标签、既有缺标签的条目要被补上；没有 remote ⇒ 一律不贴（不猜出处）。
        if any(s.get("source") for s in reg_after["skills"]):
            fails.append("仓没有 GitHub remote 时竟贴了来源标签（该保持不贴）")
        gt_root = os.path.join(tmp, "gtrepo")
        gt_library = os.path.join(tmp, "gtdata", "library", "skills")
        gt_face = os.path.join(home, ".gtagent", "skills")
        gt_names = (ANCHOR, "tagged-x")
        for n in gt_names:
            d = os.path.join(gt_root, "skills", n)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(f"---\nname: {n}\n---\n# 正本\n")
        with open(os.path.join(gt_root, REGISTRY_NAME), "w", encoding="utf-8") as f:
            json.dump({"schema": REGISTRY_SCHEMA, "version": 1, "skills": [
                {"name": n, "path": f"skills/{n}", "kind": "framework", "scope": "global",
                 "install": "auto", "summary": n} for n in gt_names]}, f, ensure_ascii=False)
        gi = subprocess.run(["git", "-C", gt_root, "init", "-q"], capture_output=True, text=True)
        gr = subprocess.run(["git", "-C", gt_root, "remote", "add", "origin",
                             "https://github.com/acme/widget.git"],
                            capture_output=True, text=True) if gi.returncode == 0 else None
        if gi.returncode != 0 or gr is None or gr.returncode != 0:
            print("  （跳过来源标签用例：本机 git 起不来）")
        else:
            os.makedirs(os.path.join(gt_library, ANCHOR))
            with open(os.path.join(gt_library, ANCHOR, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: t\n---\n# 库内旧版\n")
            os.makedirs(gt_face)
            os.symlink(os.path.join(gt_library, ANCHOR), os.path.join(gt_face, ANCHOR),
                       target_is_directory=True)
            with open(registry_path(gt_library), "w", encoding="utf-8") as f:
                json.dump({"skills": [{"name": ANCHOR, "agents": ["fake"]}],
                           "icons": {"x": 1}, "applied": {}}, f, ensure_ascii=False)
            rows_gt, _drift_gt, _n_gt = check(gt_root, gt_library, home)
            if not any(r[1] == "缺来源标签" for r in rows_gt):
                fails.append("既有条目缺 source 时 check 没报「缺来源标签」")
            rc_gt = apply(gt_root, gt_library, dry=False, home=home)
            if rc_gt != 0:
                fails.append(f"有 remote 的 apply 没收敛 rc={rc_gt}")
            with open(registry_path(gt_library), encoding="utf-8") as f:
                gt_after = {s["name"]: s for s in json.load(f)["skills"]}
            if gt_after[ANCHOR].get("source") != {"kind": LIBRARY_SOURCE_KIND, "repo": "acme/widget",
                                                  "path": f"skills/{ANCHOR}"}:
                fails.append(f"既有条目的 source 没按仓补上：{gt_after[ANCHOR].get('source')}")
            if (gt_after.get("tagged-x") or {}).get("source", {}).get("repo") != "acme/widget":
                fails.append(f"新条目没带 source：{gt_after.get('tagged-x')}")
            # 标签的 path 要对「仓」成立：正本根换成仓里的子目录（插件目录），分组名不能跟着变
            sub = os.path.join(gt_root, "inner")
            sub_skill = os.path.join(sub, "skills", "tagged-x")
            os.makedirs(sub_skill, exist_ok=True)
            with open(os.path.join(sub_skill, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: tagged-x\n---\n# 子目录里的正本\n")
            got_sub = skill_source(sub, "tagged-x", install_plan(sub))
            if (got_sub or {}).get("path") != "inner/skills/tagged-x" or (got_sub or {}).get("repo") != "acme/widget":
                fails.append(f"从仓内子目录跑，标签没按仓顶层算：{got_sub}")
            # 尺会响：除「给缺 source 的条目补 source」以外，注册面任何改动都要被自证挡下
            b1 = {"skills": [{"name": "s1", "agents": ["a"]}]}
            b2 = {"skills": [{"name": "s1", "agents": ["a"], "source": {"kind": "github"}}]}
            if _only_additions(b1, {"skills": [{"name": "s1", "agents": ["a"],
                                                "source": {"kind": "github"}}]}, ["s1"]):
                fails.append("给缺 source 的条目补 source 被自证误挡")
            if _only_additions(b2, {"skills": [dict(x) for x in b2["skills"]]}, ["s1"]):
                fails.append("注册档逐字不动却被自证误挡")
            for label, bad in (
                ("改 agents", {"skills": [{"name": "s1", "agents": ["a", "b"], "source": {"kind": "github"}}]}),
                ("改 name", {"skills": [{"name": "s2", "agents": ["a"], "source": {"kind": "github"}}]}),
                ("删字段", {"skills": [{"name": "s1", "source": {"kind": "github"}}]}),
                ("改写已有 source", {"skills": [{"name": "s1", "agents": ["a"], "source": {"kind": "folder"}}]}),
                ("补 source 外再加键", {"skills": [{"name": "s1", "agents": ["a"],
                                                    "source": {"kind": "github"}, "hash": "x"}]}),
                ("条目变少", {"skills": []}),
                ("追加不在名单", {"skills": [{"name": "s1", "agents": ["a"], "source": {"kind": "github"}},
                                             {"name": "zzz"}]}),
            ):
                if not _only_additions(b2, bad, ["s1"]):
                    fails.append(f"自证对「{label}」没响（应中止不写）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELFTEST", "ok" if not fails else "FAIL")
    for f in fails:
        print("  -", f)
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="技能回写 Magpie 中央库（#1819）")
    ap.add_argument("mode", nargs="?", default="check", choices=["check", "apply"])
    ap.add_argument("--root", default=None, help="仓库根（默认按脚本位置或 cwd 反查）")
    ap.add_argument("--library", default=None, help=f"中央库 skills 目录（默认沿 {ANCHOR} 链接反查）")
    ap.add_argument("--profile", default=None, help="安装档位（core/full；缺省读回执，无回执=full）")
    ap.add_argument("--retire-legacy", action="store_true",
                    help="一次性迁移：旧中文角色目录移到 .retired 并摘掉宿主旧链")
    ap.add_argument("--retire", default="",
                    help="显式退役技能名，逗号分隔（目录移到 .retired 并摘掉宿主旧链）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true", help="check 输出机器可读的漂移/冲突表")
    ap.add_argument("--skip", default=None,
                    help="apply 时跳过的技能名（逗号分隔）：初始化时用户选「保留现有」的那几个")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    root = a.root or resolve_root()
    if root is None:
        print(f"ROOT=读不出：脚本上溯 {default_root()} 与 cwd {os.path.abspath(os.getcwd())} 两处都没有 "
              f"{' 或 '.join(ANCHOR_MARKERS)}——在仓库根运行，或用 --root 指到仓库根")
        return 2
    library = a.library or find_library()
    if not library or not os.path.isdir(library):
        print(f"LIBRARY=读不出（env {LIBRARY_ENV} 未设，且 ~/*/skills/{ANCHOR} 没有指向库的链接）")
        return 2
    profile = a.profile or marked_profile(library)
    try:
        plan = install_plan(root, profile)
    except SystemExit as exc:
        print(f"PROFILE={exc}")
        return 2
    if a.mode == "check":
        rows, drifted, nfaces = check(root, library, plan=plan)
        if a.json:
            conflicts = conflict_rows(rows, plan)
            print(json.dumps({
                "root": root, "library": library, "profile": profile or "full",
                "faces": nfaces, "drifted": drifted,
                "conflicts": conflicts,
                "rows": [{"name": r[0], "status": r[1], "detail": r[2], "kind": r[4]}
                         for r in rows],
            }, ensure_ascii=False, indent=2))
            return 1 if drifted else 0
        print(f"正本根={root}  库={library}  档位={profile or 'full'}  落点面={nfaces} 家")
        for r in rows:
            print("  ", " | ".join(str(c) for c in r).rstrip(" |"))
        print("CHECK", "漂移" if drifted else "全绿")
        return 1 if drifted else 0
    skip = {s.strip() for s in (a.skip or "").split(",") if s.strip()}
    return apply(root, library, a.dry_run, plan=plan, profile=profile,
                 retire=a.retire_legacy, skip=skip,
                 retire_names_list={x.strip() for x in (a.retire or "").split(",") if x.strip()})


if __name__ == "__main__":
    raise SystemExit(main())
