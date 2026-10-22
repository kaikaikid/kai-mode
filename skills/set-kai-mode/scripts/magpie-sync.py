#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能回写中央库（#1819）
========================
本仓 `.ai/skills/**` 是正本，Magpie 中央库才是各家宿主真正读到的那份：库里每条是一个目录，
`~/.<agent>/skills/<名>` 是指向库目录的符号链接。正本与库是**拷贝**关系 ⇒ 「改了正本」≠「家家生效」。
本脚本把这一步变成一条命令，并让漂移可复查。
正本根认两种布局：项目仓 `.ai/skills/project-skills/<名>`（`loop` 在 `.ai/skills/loop`）与框架仓 `skills/<名>`。

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

try:  # Windows 控制台下中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ANCHOR = "kai-mode"  # 库位与落点面都沿这条既有条目反查，不写死机器路径
LIBRARY_ENV = "KAI_MAGPIE_LIBRARY"
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
# 正本根认两种布局：项目仓 `.ai/skills/project-skills/<名>` 与框架仓 `skills/<名>`。
ANCHOR_MARKERS = (
    os.path.join(".ai", "skills", "project-skills", ANCHOR, "SKILL.md"),
    os.path.join("skills", ANCHOR, "SKILL.md"),
)
ROOT_WALK_LIMIT = 8  # 上溯层级上限（脚本最深在仓根下 5 层，留余量）


def has_anchor(root: str) -> bool:
    """这个根下有没有 anchor 正本（两种布局任一）。"""
    return any(os.path.isfile(os.path.join(root, m)) for m in ANCHOR_MARKERS)


def family_candidates(name: str) -> list:
    """某技能的候选源目录（相对正本根）：项目仓布局在前，框架仓布局在后，重复去重。"""
    primary = FAMILIES[name]
    out = [primary]
    alt = os.path.join("skills", name)
    if alt not in out:
        out.append(alt)
    return out


def family_src(root: str, name: str) -> str:
    """候选里第一个真实存在的源目录；都不在就退回首选（报错文案用）。"""
    for rel in family_candidates(name):
        p = os.path.join(root, rel)
        if os.path.isdir(p):
            return p
    return os.path.join(root, FAMILIES[name])


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
    """候选根其实是中央库根（跑的是库里那份脚本时，上溯会撞到它）：
    那层的 `skills/` 就是库本身，拿它当正本根＝拿库跟自己比，永远「一致」。跳过。"""
    if not lib:
        return False
    return os.path.realpath(os.path.join(cand, "skills")) == os.path.realpath(lib)


def default_root() -> str:
    """脚本位置反查的仓库根：项目仓布局下脚本住 `<repo>/.ai/skills/project-skills/set-kai-mode/scripts/`
    ⇒ 上溯五级是仓库根；框架仓布局下脚本住 `<repo>/skills/set-kai-mode/scripts/` ⇒ 上溯三级是仓库根。
    两种布局都试，谁有 anchor 正本谁算数；都没有就退回五级的老读数。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for up in (3, 5):
        cand = os.path.abspath(os.path.join(here, *[".."] * up))
        if has_anchor(cand):
            return cand
    return os.path.abspath(os.path.join(here, *[".."] * 5))


def resolve_root(script_dir: str | None = None) -> str | None:
    """正本根：先按脚本位置上溯认（认两种布局），再退到 cwd 上溯认——各家宿主可能跑的是**库里那份脚本**，
    那时脚本位置不在仓里，只有 cwd（工作区根）才是正本。两处都没有就如实读不出。"""
    lib = find_library()
    for cand in _root_candidates(script_dir):
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


def tree_files(root: str) -> dict:
    out = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
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


def check(root: str, library: str, home: str | None = None) -> tuple:
    rows, drifted = [], False
    faces = find_faces(library, home)
    data, reg_err = read_registry(library)
    for name in FAMILIES:
        src, dst = family_src(root, name), os.path.join(library, name)
        if not os.path.isdir(src):
            tried = "、".join(os.path.join(root, r) for r in family_candidates(name))
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
    for name in FAMILIES:
        absent = [f for f in faces if not os.path.lexists(os.path.join(f, name))]
        if absent:
            drifted = True
            rows.append((name, "落点缺失", f"{len(faces) - len(absent)}/{len(faces)} 家", ";".join(absent), "red"))
    if reg_err:
        drifted = True
        rows.append(("注册档", "读不出", reg_err, "", "red"))
    else:
        names = {s.get("name") for s in data.get("skills", []) if isinstance(s, dict)}
        for name in FAMILIES:
            if name not in names:
                drifted = True
                rows.append((name, "注册缺条目", registry_path(library), "", "red"))
    return rows, drifted, len(faces)


def copy_family(root: str, library: str, name: str, dry: bool) -> list:
    src = family_src(root, name)
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
    rows, drifted, nfaces = check(root, library, home)
    print(f"正本根={root}  库={library}  落点面={nfaces} 家  写前漂移={'有' if drifted else '无'}")
    written = []
    for name in FAMILIES:
        written += copy_family(root, library, name, dry)
    added = [] if dry else patch_registry(library, list(FAMILIES))
    if dry:
        try:
            added = patch_registry(library, list(FAMILIES), dry=True)
        except SystemExit as exc:
            print(f"  注册档预演被自证挡下：{exc}")
    made, failed = link_faces(library, list(FAMILIES), home, dry)
    for p in written:
        print(f"  {'将写' if dry else '写入'} {p}")
    for a in added:
        print(f"  注册 {a}")
    for l in made:
        print(f"  链接 {'将建' if dry else '建好'} {l}")
    for f in failed:
        print(f"  落点失败 {f}")
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
        # 有 skills/kai-mode/SKILL.md 的仓，正本根必须读得出（不再报「正本根读不出」）
        fw_script = os.path.join(fw_root, "skills", "set-kai-mode", "scripts")
        os.makedirs(fw_script, exist_ok=True)
        picked_fw = resolve_root(script_dir=fw_script)
        if picked_fw is None:
            fails.append("框架仓布局仍读不出正本根")
        elif os.path.normcase(picked_fw) != os.path.normcase(os.path.abspath(fw_root)):
            fails.append(f"框架仓布局正本根认错：{picked_fw}")
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
        # 幂等：再跑一次不该写出任何字节
        again = []
        for name in FAMILIES:
            again += copy_family(root, library, name, dry=False)
        if again:
            fails.append(f"二次 apply 仍在写字节（不幂等）：{again}")
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
