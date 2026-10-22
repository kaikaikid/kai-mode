#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kai-mode 框架仓 doctor（单一校验入口）
=====================================
用法：
    python scripts/doctor.py                # 逐项检查（13 项）
    python scripts/doctor.py --with-tests   # 追加跑各技能自己的 pytest
    python scripts/doctor.py --json         # 机器可读：{"ok":bool,"checks":[{id,status,detail}]}

仓根默认＝脚本上溯一级（`<仓根>/scripts/doctor.py` → `<仓根>`），`--root` 可指到别的根（假仓自测用）。
只读：除 pytest 自己的缓存外不写盘；只用标准库，不装任何东西。
注册表口径只有一份：本仓 `skills/set-kai-mode/scripts/magpie-sync.py` 里的注册表读写与装机集派生，
这里 import 那个模块来比，不复制第二份逻辑。
第 13 项 `install-sync` 依赖宿主状态（中央库在不在、装没装）：库定位不到 ⇒ 跳过，不是红。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

try:  # Windows 控制台下中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# import magpie-sync 时别在技能目录里落 __pycache__（那会被装机尺当成正本差异带进中央库）
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
OWN_ROOT = os.path.abspath(os.path.join(HERE, ".."))
MAGPIE_SYNC = os.path.join(OWN_ROOT, "skills", "set-kai-mode", "scripts", "magpie-sync.py")

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
    """01 registry.json 存在、schema 认识、version 是整数。"""
    path = os.path.join(root, "registry.json")
    if not os.path.isfile(path):
        return "fail", f"注册表不存在：{path}"
    data, err = registry(root, ms)
    if data is None:
        return "fail", err
    ver = data.get("version")
    if not isinstance(ver, int) or isinstance(ver, bool):
        return "fail", f"version 不是整数：{ver!r}"
    return "ok", f"schema={data.get('schema')}，version={ver}，条目 {len(data.get('skills') or [])} 条"


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
        if tuple(keys or []) != FRONTMATTER_ORDER:
            missing = [k for k in FRONTMATTER_ORDER if k not in (keys or [])]
            extra = [k for k in (keys or []) if k not in FRONTMATTER_ORDER]
            problems.append(f"{rel}/SKILL.md：frontmatter 字段/顺序不对（缺 {missing} 多 {extra} 实到 {keys}）")
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
    """04 盘上有技能目录但没登记 ⇒ 红（以后还会塞个人 skill，这道闸最要紧）。"""
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return "skip", "没有 skills/ 目录"
    data, _ = registry(root, ms)
    registered = set()
    for entry in (data or {}).get("skills") or []:
        if isinstance(entry, dict) and entry.get("path"):
            registered.add(str(entry["path"]).replace("\\", "/").strip("/"))
    on_disk = [n for n in sorted(os.listdir(skills_dir))
                if os.path.isfile(os.path.join(skills_dir, n, "SKILL.md"))]
    unregistered = [n for n in on_disk if f"skills/{n}" not in registered]
    if unregistered:
        return "fail", f"盘上有技能目录没登记：{'、'.join(unregistered)}（补 registry.json 一行）"
    return "ok", f"盘上 {len(on_disk)} 个技能目录都登记了"


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


def chk_broken_link(root, ms):
    """07 SKILL.md 里的相对 markdown 链接指向的文件不存在 ⇒ 红。"""
    data, err = registry(root, ms)
    if data is None:
        return "skip", f"注册表不可用（01 已报）：{err}"
    broken, scanned = [], 0
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
    if broken:
        return "fail", "；".join(broken[:6]) + (f"（共 {len(broken)} 处）" if len(broken) > 6 else "")
    return "ok", f"{scanned} 份 SKILL.md 的相对链接都在"


def chk_tracked_cache(root, ms):
    """08 git 跟踪的文件里出现 __pycache__／.pyc／.pytest_cache ⇒ 红。"""
    if not os.path.isdir(os.path.join(root, ".git")):
        return "skip", "不是 git 仓（不适用）"
    try:
        p = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        return "skip", f"git 不可用：{exc}"
    if p.returncode != 0:
        return "skip", "git ls-files 失败（不适用）"
    bad = [x for x in p.stdout.splitlines()
           if "__pycache__" in x or x.endswith(".pyc") or ".pytest_cache" in x]
    if bad:
        return "fail", "；".join(bad[:6]) + (f"（共 {len(bad)} 处）" if len(bad) > 6 else "")
    return "ok", "git 跟踪的文件里没有缓存产物"


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
    """12 --with-tests：跑各技能自己的 pytest（skills/*/scripts/tests/ 与 skills/*/tests/），全绿才算绿。"""
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return "skip", "没有 skills/ 目录"
    targets = []
    for name in sorted(os.listdir(skills_dir)):
        for sub in ("scripts/tests", "tests"):
            d = os.path.join(skills_dir, name, *sub.split("/"))
            if os.path.isdir(d):
                targets.append((name, d))
    if not targets:
        return "skip", "没有技能自带的测试目录"
    bad = []
    for name, d in targets:
        p = subprocess.run([sys.executable, "-m", "pytest", d, "-q", "-p", "no:cacheprovider"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=root)
        if p.returncode != 0:
            tail = (p.stdout or "").strip().splitlines()[-1:] or [""]
            bad.append(f"{name}：{tail[0][:120]}")
    if bad:
        return "fail", "；".join(bad)
    return "ok", f"{len(targets)} 个技能测试目录全绿（{'、'.join(n for n, _ in targets)}）"


def chk_install_sync(root, ms):
    """13 装机同步：中央库里的技能副本还等于本仓吗？库记住的装机来源是不是本仓？（只读，不写盘）
    这是「本仓为准」从口头约定变成可发现的关键闸：项目仓那份旧脚本若被再跑会把库刷回旧版，
    这项检查当场点名并给修法。库定位不到 ⇒ 跳过（本仓可以脱离宿主单跑）。"""
    if ms is None:
        return "fail", "magpie-sync 读不出来"
    lib = ms.find_library()
    if not lib or not os.path.isdir(lib):
        return "skip", f"中央库定位不到（{getattr(ms, 'LIBRARY_ENV', 'KAI_MAGPIE_LIBRARY')} 未设，~/*/skills/kai-mode 没有指向库的链接）"
    fix = (f"python skills/set-kai-mode/scripts/magpie-sync.py apply --root {root} --library {lib}")
    try:
        plan = ms.install_plan(root)
    except SystemExit as exc:
        return "fail", f"magpie-sync 拒绝这份注册表：{exc}"
    problems = []
    # ① 库副本 vs 本仓正本：逐文件 SHA-256（tree_files 已跳过缓存产物，不会误报 __pycache__）
    for name in plan:
        src = ms.family_src(root, name, plan)
        dst = os.path.join(lib, name)
        if not os.path.isdir(dst):
            problems.append(f"{name}：库内没有这一条")
            continue
        a, b = ms.tree_files(src), ms.tree_files(dst)
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
    if problems:
        head = "；".join(problems[:6])
        more = f"（共 {len(problems)} 处）" if len(problems) > 6 else ""
        return "fail", f"{head}{more}。修法：{fix}"
    return "ok", f"{len(plan)} 个技能副本与本仓逐字相同；装机来源＝本仓（{root}）"


CHECKS = (
    ("registry-file", "注册表文件", chk_registry_file),
    ("registry-fields", "注册表字段", chk_registry_fields),
    ("skill-frontmatter", "frontmatter 与 name 三处一致", chk_frontmatter),
    ("unregistered-skill", "盘上技能都登记了", chk_unregistered),
    ("missing-skill-path", "注册条目路径都在", chk_missing_path),
    ("machine-path", "没有机器绝对路径", chk_machine_path),
    ("broken-link", "SKILL.md 相对链接都在", chk_broken_link),
    ("tracked-cache", "git 跟踪文件无缓存产物", chk_tracked_cache),
    ("gitattributes-bat", ".gitattributes 钉住 .bat 行尾", chk_gitattributes),
    ("install-set-match", "装机集合与注册表一致", chk_install_set),
    ("version-in-readme", "VERSION 与 README 口径一致", chk_version_readme),
    ("skill-tests", "各技能 pytest 全绿", chk_skill_tests),
    ("install-sync", "装机同步（库副本与来源）", chk_install_sync),
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
