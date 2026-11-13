#!/usr/bin/env python3
"""深度人格层 → 安装面技能资源（发布路径）。

深度材料住在 `roles/persona/<role_id>.json`（role 层的按需层，**唯一可写源**）。
装机面到不了 `roles/`（repo_only，见 manifests/package-layout.json），所以把它**投影**成
技能资源随技能发布：`core/skills/kai-persona-deep/resources/depth/<role_id>.md`。

投影是生成物：正文由 `rolelib.render_depth()` 现拼（只有一个组装点），手改会被
doctor 的 `depth-publish` 门判红。权威源永远是 persona 里的 depth 块。

用法：
  python scripts/depth-publish.py            # 写盘
  python scripts/depth-publish.py --check    # 只报漂移，不写盘
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rolelib  # noqa: E402

SKILL_DIR_REL = "core/skills/kai-persona-deep"
RESOURCES_REL = "resources/depth"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def dest_dir(root: Path) -> Path:
    return Path(root) / SKILL_DIR_REL / RESOURCES_REL


def build(root: Path) -> dict:
    """返回 {role_id: 资源正文}。正文一律由 render_depth 现拼。"""
    root = Path(root)
    out = {}
    for rid in rolelib.ROLE_IDS:
        try:
            out[rid] = rolelib.render_depth(root, rid)
        except rolelib.RoleError:
            continue  # 没接入 depth 的角色不投影
    return out


def check(root: Path) -> list:
    """返回漂移列表，空＝一致。"""
    root = Path(root)
    want = build(root)
    dest = dest_dir(root)
    problems = []
    for rid, text in want.items():
        p = dest / f"{rid}.md"
        if not p.is_file():
            problems.append(f"缺投影件：{p.relative_to(root)}")
            continue
        if p.read_text(encoding="utf-8") != text:
            problems.append(f"投影件与正本不一致：{p.relative_to(root)}"
                            f"（正本＝roles/persona/{rid}.json 的 depth 块）")
    for p in sorted(dest.glob("*.md")) if dest.is_dir() else []:
        if p.stem not in want:
            problems.append(f"多出投影件：{p.relative_to(root)}（正本里没有这个角色的 depth）")
    problems.extend(_dispatch_gate(root))
    return problems


def _dispatch_gate(root: Path) -> list:
    """分发门：skill body 只放取用口，不放 depth 正文。

    深度材料随技能发布时，技能正文必须还是「怎么取」的说明，不是材料本身——
    否则材料就多了一个家（技能正文），且会被读进常驻上下文。
    """
    import persona as persona_lib
    skill = Path(root) / "core" / "skills" / "kai-persona-deep" / "SKILL.md"
    if not skill.is_file():
        return [f"缺技能正文：{skill.relative_to(root)}"]
    body = skill.read_text(encoding="utf-8")
    problems = []
    for rid in rolelib.ROLE_IDS:
        depth = (persona_lib.load(Path(root), rid) or {}).get("depth") or {}
        for k in persona_lib.DEPTH_SECTIONS:
            frag = str(depth.get(k) or "").strip()
            if frag and frag[:24] in body:
                problems.append(f"技能正文内联了 {rid}.depth.{k}"
                                f"（分发门：skill body 只放取用口，不放正文）")
    return problems


def apply(root: Path) -> int:
    root = Path(root)
    dest = dest_dir(root)
    dest.mkdir(parents=True, exist_ok=True)
    want = build(root)
    changed = []
    for rid, text in want.items():
        p = dest / f"{rid}.md"
        old = p.read_text(encoding="utf-8") if p.is_file() else None
        if old != text:
            p.write_text(text, encoding="utf-8", newline="\n")
            changed.append(rid)
    print(f"深度层投影：{len(want)} 个角色 → {dest}")
    for rid in changed:
        print(f"  写入：{rid}.md")
    if not changed:
        print("  （无变化）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="深度人格层 → 技能资源投影")
    p.add_argument("--root", help="仓根（默认脚本所在仓）")
    p.add_argument("--check", action="store_true", help="只报漂移，不写盘")
    args = p.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root()
    if args.check:
        problems = check(root)
        if problems:
            print(f"深度层投影漂移（{len(problems)} 处）：")
            for x in problems:
                print(f"  - {x}")
            return 1
        print(f"深度层投影一致：{len(build(root))} 份与 persona 正本逐字相同")
        return 0
    return apply(root)


if __name__ == "__main__":
    raise SystemExit(main())
