#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能回写中央库（#1819）
========================
本仓技能目录是正本，Magpie 中央库才是各家宿主真正读到的那份：库里每条是一个目录，
`~/.<agent>/skills/<名>` 是指向库目录的符号链接。正本与库是**拷贝**关系 ⇒ 「改了正本」≠「家家生效」。
本脚本把这一步变成一条命令，并让漂移可复查。
正本根认两种布局：项目仓落点读项目配置实例 `<root>/.ai/kai-mode.project.json` 的
`registry.skills.project_skills_dir`／`loop_dir`（框架仓旧裁决，无实例回落内置缺省）；框架仓 `skills/<名>`。
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
  · 注册面 `library.json` 的 `skills[]` 有条目，且每个铺了 anchor 的 `applied[*].skills` 含该名

安全：只新增、只覆盖同路径文件，**绝不删除**库里多出来的东西；`library.json` 走临时档 + `os.replace`
原子替换，且写前自证「本次改动只允许新增条目」，自证不过就中止不写。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

try:  # Windows 控制台下中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ANCHOR = "kai-mode"  # 库位与落点面都沿这条既有条目反查，不写死机器路径
LIBRARY_ENV = "KAI_MAGPIE_LIBRARY"
# 项目技能落点缺省（框架仓旧裁决 registry.skills 的模板缺省值）：只在项目配置实例
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
    "航班信息": os.path.join(".ai", "skills", "project-skills", "航班信息"),
}
# 正本根认两种布局：项目仓落点（实例 registry.skills，缺省同上）与框架仓 `skills/<名>`。
ANCHOR_MARKERS = (
    os.path.join(REGISTRY_SKILLS_DEFAULT["project_skills_dir"], ANCHOR, "SKILL.md"),
    os.path.join("skills", ANCHOR, "SKILL.md"),
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


def library_root(library: str) -> str:
    """中央库根＝library skills 目录的上一级（装机来源标记放这儿）。"""
    return os.path.dirname(os.path.abspath(library))


def source_marker_path(library: str) -> str:
    """装机来源标记文件：`<库根>/.kai-mode-source.json`。"""
    return os.path.join(library_root(library), SOURCE_MARKER_NAME)


def write_source_marker(library: str, root: str, skills: int) -> str:
    """apply 真跑完 ⇒ 记下「这个库是从哪个仓装来的」：原子写（临时档 + os.replace，同 patch_registry 一路数）。"""
    path = source_marker_path(library)
    data = {
        "schema": SOURCE_SCHEMA,
        "root": os.path.abspath(root),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "skills": skills,
    }
    fd, tmp = tempfile.mkstemp(prefix=".kai-mode-source.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise SystemExit(f"装机来源标记写入失败：{exc}")
    return path


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
    """读项目配置实例 `<root>/.ai/kai-mode.project.json`（框架仓旧裁决/D4）。
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
    """项目技能落点（框架仓旧裁决 registry.skills）：实例给了用实例的；
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
    """装机源缺省值：项目技能落点读配置实例 `registry.skills.*`（框架仓旧裁决）；
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


def install_plan(root: str) -> dict:
    """装机清单（name -> {"source", "path"}）：取注册表 `install == "auto"` 的条目；
    没有 registry.json（老根目录）⇒ 回落内置 FAMILIES，照旧工作，不报错退出。"""
    data, err = read_skill_registry(root)
    if err:
        raise SystemExit(err)
    if data is None:
        return {name: {"source": default_source(name, root),
                       "path": os.path.join("skills", name)}
                for name in FAMILIES}
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
    return plan


def family_candidates(name: str, plan: dict | None = None, root: str | None = None) -> list:
    """某技能的候选源目录（相对正本根）：① 装机源（注册表 source，缺省读配置实例
    registry.skills）② 注册表 path（框架仓布局，如 `skills/航班信息`）③ `skills/<名>`；
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
    for up in (3, 5):
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


def tree_files(root: str) -> dict:
    """技能目录的实文件清单：跳过缓存产物（__pycache__/.pytest_cache/*.pyc）。
    否则跑一次 pytest，装机就把缓存带进中央库、再链到各家宿主——机器上还分不清哪份是正本。"""
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in CACHE_DIRS]
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            p = os.path.join(base, name)
            if not os.path.islink(p):
                out[os.path.relpath(p, root).replace(os.sep, "/")] = p
    return out


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
    for name in plan:
        src, dst = family_src(root, name, plan), os.path.join(library, name)
        if not os.path.isdir(src):
            tried = "、".join(os.path.join(root, r) for r in family_candidates(name, plan, root))
            rows.append((name, "正本缺失", f"试过：{tried}", src, "red"))
            drifted = True
            continue
        a = tree_files(src)
        b = tree_files(dst) if os.path.isdir(dst) else {}
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
        for name in plan:
            if name not in names:
                drifted = True
                rows.append((name, "注册缺条目", registry_path(library), "", "red"))
    return rows, drifted, len(faces)


def copy_family(root: str, library: str, name: str, dry: bool, plan: dict | None = None) -> list:
    src = family_src(root, name, plan)
    written = []
    if not os.path.isdir(src):
        return written
    for rel, p in sorted(tree_files(src).items()):
        dst = os.path.join(library, name, *rel.split("/"))
        if os.path.isfile(dst) and sha256(dst) == sha256(p):
            continue
        if not dry:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(p, dst)
        written.append(f"{name}/{rel}")
    return written


def _only_additions(before: dict, after: dict, names) -> str | None:
    """注册档允许的改动＝末尾追加条目；越界就报原因（宁可中止也不猜）。"""
    if set(before) != set(after):
        return "顶层键集合变了"
    for key in before:
        b, a = before[key], after[key]
        if key == "skills" and isinstance(b, list) and isinstance(a, list):
            if a[: len(b)] != b:
                return "skills[] 既有条目被改写或换序"
            known = {x.get("name") for x in b if isinstance(x, dict)}
            for extra in a[len(b):]:
                if not isinstance(extra, dict) or extra.get("name") not in names or extra["name"] in known:
                    return "skills[] 追加项不是本次三件"
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


def patch_registry(library: str, names, dry: bool = False) -> list:
    path = registry_path(library)
    before, err = read_registry(library)
    if err:
        raise SystemExit(err)
    after = json.loads(json.dumps(before))
    anchor_entry = next((s for s in before.get("skills", []) if s.get("name") == ANCHOR), {})
    agents = list(anchor_entry.get("agents") or [])
    added = []
    existing = {s.get("name") for s in after.get("skills", []) if isinstance(s, dict)}
    for name in names:
        if name in existing:
            continue
        entry = {"name": name}
        if agents:
            entry["agents"] = list(agents)
        after.setdefault("skills", []).append(entry)
        added.append(f"skills[] += {name}")
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


def apply(root: str, library: str, dry: bool, home: str | None = None) -> int:
    plan = install_plan(root)
    rows, drifted, nfaces = check(root, library, home, plan)
    print(f"正本根={root}  库={library}  落点面={nfaces} 家  写前漂移={'有' if drifted else '无'}")
    written = []
    for name in plan:
        written += copy_family(root, library, name, dry, plan)
    added = [] if dry else patch_registry(library, list(plan))
    if dry:
        try:
            added = patch_registry(library, list(plan), dry=True)
        except SystemExit as exc:
            print(f"  注册档预演被自证挡下：{exc}")
    made, failed = link_faces(library, list(plan), home, dry)
    marker = None if dry else write_source_marker(library, root, len(plan))
    for p in written:
        print(f"  {'将写' if dry else '写入'} {p}")
    for a in added:
        print(f"  注册 {a}")
    for l in made:
        print(f"  链接 {'将建' if dry else '建好'} {l}")
    for f in failed:
        print(f"  落点失败 {f}")
    if marker:
        print(f"  装机来源标记 {marker}（记住这个库是从哪个仓装来的）")
    if dry:
        print("（dry-run：盘上未改动）")
        return 0
    _rows, drifted2, _n = check(root, library, home)
    print("回写后复量：", "仍有漂移" if drifted2 else "三面全绿")
    return 1 if drifted2 else 0


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
        # 项目配置实例 registry.skills 自定义落点（框架仓旧裁决）：装机源缺省要认实例
        cfg_root = os.path.join(tmp, "cfgrepo")
        custom_dir = os.path.join(".ai", "skills", "custom")
        custom_loop = os.path.join(".ai", "skills", "custom-loop")
        os.makedirs(os.path.join(cfg_root, custom_dir, ANCHOR), exist_ok=True)
        os.makedirs(os.path.join(cfg_root, custom_loop), exist_ok=True)
        with open(os.path.join(cfg_root, PROJECT_CONFIG), "w", encoding="utf-8") as f:
            json.dump({"schema": 3, "registry": {"skills": {
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
    ap.add_argument("--dry-run", action="store_true")
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
    if a.mode == "check":
        rows, drifted, nfaces = check(root, library)
        print(f"正本根={root}  库={library}  落点面={nfaces} 家")
        for r in rows:
            print("  ", " | ".join(str(c) for c in r).rstrip(" |"))
        print("CHECK", "漂移" if drifted else "全绿")
        return 1 if drifted else 0
    return apply(root, library, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
