#!/usr/bin/env python3
"""plugin-check —— 插件清单体检（KWP 形态的本地版）。

检查五件事：
  1. .claude-plugin/marketplace.json 是合法市场清单，本地 source 目录都在；
  2. 每个插件有两份 plugin.json（Claude Code / Qoder），name 与 version 一致且为 semver；
  3. 每个 skills/<名>/SKILL.md 的 frontmatter name 与目录名一致、version 是 semver；
  4. 同一技能名不跨插件重复；每个插件至少一个技能；
  5. manifests/install-profiles.json 的 core/full 只引用发现的自动技能，core ⊆ full，full 覆盖全部自动技能。

版本钉死：manifests/plugins.lock.json 记录每个插件的 version、内容摘要与逐技能版本。
默认运行比对锁文件；不一致即红，并提示跑 `--bump` 刷新。`--bump` 重写锁文件。

退出码：0 全绿；1 有红；2 市场清单缺失/不可读。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
FRONTMATTER_NAME_RE = re.compile(r"^name:\s*([^\s#]+)\s*$", re.M)
FRONTMATTER_VERSION_RE = re.compile(r"^version:\s*([^\s#]+)\s*$", re.M)
EXCLUDE_DIRS = {"tests", "__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo")
MANUAL_SKILLS = {"harness-audit"}
LOCK_REL = "manifests/plugins.lock.json"
PROFILES_REL = "manifests/install-profiles.json"
LOCK_SCHEMA = "kai-mode-plugins-lock/1"
PROFILES_SCHEMA = "kai-mode-install-profiles/1"


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def plugin_digest(plugin_dir: str) -> str:
    """插件安装面的内容摘要：排除 tests/缓存，按相对路径排序。"""
    rows = []
    for base, dirs, files in os.walk(plugin_dir):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for fn in sorted(files):
            if fn.endswith(EXCLUDE_SUFFIXES):
                continue
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, plugin_dir).replace("\\", "/")
            rows.append((rel, sha256_file(p)))
    h = hashlib.sha256()
    for rel, digest in rows:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\0")
    return h.hexdigest()


def frontmatter(text: str):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    head = text[3:end] if end != -1 else text[3:]
    return {
        "name": (FRONTMATTER_NAME_RE.search(head) or [None, ""])[1],
        "version": (FRONTMATTER_VERSION_RE.search(head) or [None, ""])[1],
    }


def discover(root: str):
    """返回 (plugins, problems)。plugins[name] = {dir, version, skills{name: version}}"""
    market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
    if not os.path.isfile(market_path):
        return None, [f"缺市场清单：{market_path}"]
    try:
        market = read_json(market_path)
    except (OSError, ValueError) as exc:
        return None, [f"市场清单读不出：{exc}"]

    plugins = {}
    problems = []
    entries = market.get("plugins") if isinstance(market, dict) else None
    if not isinstance(entries, list) or not entries:
        return None, ["市场清单没有 plugins[]"]

    for entry in entries:
        if not isinstance(entry, dict):
            problems.append(f"plugins[] 里有非对象条目：{entry!r}")
            continue
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(name, str) or not name:
            problems.append(f"插件条目缺 name：{entry!r}")
            continue
        if not isinstance(source, str) or not source.startswith("./"):
            problems.append(f"{name}：source 必须是本地相对目录（./<插件>），实到 {source!r}")
            continue
        plugin_dir = os.path.normpath(os.path.join(root, source))
        if not os.path.isdir(plugin_dir):
            problems.append(f"{name}：source 目录不存在：{source}")
            continue
        if name in plugins:
            problems.append(f"插件名重复：{name}")
            continue

        manifests = {}
        for rel in (".claude-plugin/plugin.json", ".qoder-plugin/plugin.json"):
            p = os.path.join(plugin_dir, *rel.split("/"))
            if not os.path.isfile(p):
                problems.append(f"{name}：缺 {rel}")
                continue
            try:
                manifests[rel] = read_json(p)
            except (OSError, ValueError) as exc:
                problems.append(f"{name}：{rel} 读不出：{exc}")
        versions = set()
        for rel, data in manifests.items():
            if not isinstance(data, dict):
                problems.append(f"{name}：{rel} 不是对象")
                continue
            if data.get("name") != name:
                problems.append(f"{name}：{rel} 的 name={data.get('name')!r} 与市场清单不一致")
            ver = data.get("version")
            if not isinstance(ver, str) or not SEMVER_RE.match(ver):
                problems.append(f"{name}：{rel} 的 version 不是 semver：{ver!r}")
            else:
                versions.add(ver)
            if not data.get("description"):
                problems.append(f"{name}：{rel} 缺 description")
        if len(versions) > 1:
            problems.append(f"{name}：两份 plugin.json 的 version 不一致：{sorted(versions)}")
        version = next(iter(versions), "0.0.0")

        skills_dir = os.path.join(plugin_dir, "skills")
        skills = {}
        if not os.path.isdir(skills_dir):
            problems.append(f"{name}：没有 skills/ 目录")
        else:
            for skill in sorted(os.listdir(skills_dir)):
                smd = os.path.join(skills_dir, skill, "SKILL.md")
                if not os.path.isfile(smd):
                    continue
                try:
                    with open(smd, encoding="utf-8") as f:
                        fm = frontmatter(f.read())
                except (OSError, UnicodeDecodeError) as exc:
                    problems.append(f"{name}/{skill}：SKILL.md 读不出：{exc}")
                    continue
                if fm.get("name") != skill:
                    problems.append(f"{name}/{skill}：frontmatter name={fm.get('name')!r} 与目录名不一致")
                if not SEMVER_RE.match(fm.get("version", "")):
                    problems.append(f"{name}/{skill}：version 不是 semver：{fm.get('version')!r}")
                skills[skill] = fm.get("version", "")
        if not skills:
            problems.append(f"{name}：一个技能都没有")
        plugins[name] = {"dir": plugin_dir, "version": version, "skills": skills}

    # 技能名跨插件唯一
    seen = {}
    for name, info in plugins.items():
        for skill in info["skills"]:
            if skill in seen:
                problems.append(f"技能名跨插件重复：{skill}（{seen[skill]} 与 {name}）")
            seen[skill] = name
    return plugins, problems


def check_profiles(root: str, plugins: dict):
    path = os.path.join(root, *PROFILES_REL.split("/"))
    if not os.path.isfile(path):
        return [f"缺档位清单：{PROFILES_REL}"]
    try:
        cfg = read_json(path)
    except (OSError, ValueError) as exc:
        return [f"{PROFILES_REL} 读不出：{exc}"]
    problems = []
    if not isinstance(cfg, dict) or cfg.get("schema") != PROFILES_SCHEMA:
        return [f"{PROFILES_REL} schema 不是 {PROFILES_SCHEMA}"]
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        return [f"{PROFILES_REL} 没有 profiles"]
    auto = {s for info in plugins.values() for s in info["skills"] if s not in MANUAL_SKILLS}
    expanded = {}
    for name in ("core", "full"):
        item = profiles.get(name)
        if not isinstance(item, dict):
            problems.append(f"缺档位 {name}")
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
            problems.append(f"{name} 引用了不存在的自动技能：{', '.join(unknown)}")
        expanded[name] = set(skills)
    if "core" in expanded and "full" in expanded:
        extra = sorted(expanded["core"] - expanded["full"])
        if extra:
            problems.append(f"core 不是 full 的子集：{', '.join(extra)}")
        missing = sorted(auto - expanded["full"])
        if missing:
            problems.append(f"full 漏了自动技能：{', '.join(missing)}")
    return problems


def build_lock(plugins: dict) -> dict:
    return {
        "schema": LOCK_SCHEMA,
        "_note": "版本钉死：由 scripts/plugin-check.py --bump 生成，不手改。digest 是插件安装面的内容摘要。",
        "plugins": {
            name: {
                "version": info["version"],
                "digest": plugin_digest(info["dir"]),
                "skills": dict(sorted(info["skills"].items())),
            }
            for name, info in sorted(plugins.items())
        },
    }


def check_lock(root: str, plugins: dict):
    path = os.path.join(root, *LOCK_REL.split("/"))
    if not os.path.isfile(path):
        return [f"缺锁文件 {LOCK_REL}；跑 python scripts/plugin-check.py --bump 生成"]
    try:
        lock = read_json(path)
    except (OSError, ValueError) as exc:
        return [f"{LOCK_REL} 读不出：{exc}"]
    if not isinstance(lock, dict) or lock.get("schema") != LOCK_SCHEMA:
        return [f"{LOCK_REL} schema 不是 {LOCK_SCHEMA}"]
    pinned = lock.get("plugins") if isinstance(lock.get("plugins"), dict) else {}
    problems = []
    for name, info in sorted(plugins.items()):
        want = pinned.get(name)
        if not isinstance(want, dict):
            problems.append(f"{name}：锁文件没有这个插件；跑 --bump")
            continue
        if want.get("version") != info["version"]:
            problems.append(f"{name}：version 漂移（锁 {want.get('version')} / 实 {info['version']}）")
        if want.get("digest") != plugin_digest(info["dir"]):
            problems.append(f"{name}：内容摘要漂移；确认改动后跑 --bump")
        if want.get("skills") != dict(sorted(info["skills"].items())):
            problems.append(f"{name}：技能版本与锁文件不一致；跑 --bump")
    for name in sorted(set(pinned) - set(plugins)):
        problems.append(f"锁文件里有已不存在的插件：{name}")
    return problems


def write_lock(root: str, plugins: dict):
    path = os.path.join(root, *LOCK_REL.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(build_lock(plugins), f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="kai-mode 插件清单体检")
    ap.add_argument("--root", default=None, help="仓根（默认＝脚本上溯一级）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--bump", action="store_true", help="刷新 manifests/plugins.lock.json")
    args = ap.parse_args()
    root = os.path.abspath(args.root) if args.root else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    plugins, problems = discover(root)
    if plugins is None:
        for p in problems:
            print(f"[红] {p}")
        return 2
    problems += check_profiles(root, plugins)
    if args.bump:
        path = write_lock(root, plugins)
        print(f"[刷新] {os.path.relpath(path, root)}：{len(plugins)} 个插件")
    else:
        problems += check_lock(root, plugins)

    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems,
                          "plugins": {n: {"version": i["version"], "skills": i["skills"]}
                                      for n, i in plugins.items()}}, ensure_ascii=False, indent=2))
    else:
        total = sum(len(i["skills"]) for i in plugins.values())
        print(f"plugin-check —— 根 {root}")
        for name, info in sorted(plugins.items()):
            print(f"[绿] {name:<8} v{info['version']:<6} skills={len(info['skills'])}")
        for p in problems:
            print(f"[红] {p}")
        print(f"总结：{len(plugins)} 个插件 / {total} 个技能 / {len(problems)} 项红"
              + ("；结论：绿" if not problems else "；结论：红"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
