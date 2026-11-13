#!/usr/bin/env python3
"""角色层只读派生登记导出（ADR-0034 D4/D5 门①）。

唯一导出入口：从 `roles/canon`、`roles/skins`、`roles/persona` 现读，产出两份只读 JSON：

  roles/registry/profession-registry/v1.json   职业表（8 条，通用职业名）
  roles/registry/role-registry/v1.json         角色表（8 role × generic/guild 两张脸）

纪律：
- 不搬正文：只放名字、版本、指纹与团队归属占位；mission/boundaries/workflow/output_contract、
  personality 全文、identity_core 全文一律不导出。
- 指纹口径与 #14 一致：canon 指纹走 `rolelib.load_canon` 的 LF 归一哈希；skin 指纹走
  `rolelib.entry_sha256`；persona 指纹走 `persona.fingerprint`；memory 契约按稳定 JSON 哈希。
- 幂等：无时间戳、无路径、无随机量；连跑两次逐字节相等。
- 下游只读消费：kai-vass #2011（后端切源）· #2012（只读桥 + 前端页签）· #2013（四门验收）。

用法：
  python scripts/export-role-registry.py [--root <仓根>] [--out <输出目录>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import persona as persona_lib  # noqa: E402
import rolelib  # noqa: E402

SCHEMA_PROFESSION = "profession-registry/v1"
SCHEMA_ROLE = "role-registry/v1"
CONTRACT_VERSION = "1.0.0"
ADR = "0034"
CONSUMERS = (
    "kai-vass#2011 后端切源（registry 为 seed 唯一来源）",
    "kai-vass#2012 只读桥 + 前端页签（按 registry 版本与 sha 对账）",
    "kai-vass#2013 四门验收（版本漂移 / seed 哈希 / UI 角标 / 旧柜只读）",
)
TEAM_PLACEHOLDER = {"team_id": None, "status": "pending"}


def _sha_json(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rolelib.sha256_bytes(blob.encode("utf-8"))


def _header(schema: str) -> dict:
    return {
        "schema": schema,
        "contract_version": CONTRACT_VERSION,
        "generator": "export-role-registry",
        "adr": ADR,
        "consumers": list(CONSUMERS),
    }


def build_registries(root: Path) -> dict[str, dict]:
    """返回 {相对输出路径: JSON 对象}；纯函数，供 doctor 对账复用。"""
    root = Path(root)
    canon = rolelib.load_canon(root)
    skins = {name: rolelib.load_skin(root, name) for name in rolelib.SKINS}
    personas = {rid: persona_lib.load(root, rid) for rid in rolelib.ROLE_IDS}

    def common(rid: str, skin_name: str) -> dict:
        skin = skins[skin_name]
        entry = skin["roles"][rid]
        p = personas[rid]
        return {
            "profession_id": rid,
            "profession_name": skins["generic"]["roles"][rid]["name"],
            "canon_version": canon[rid]["meta"]["canon_version"],
            "canon_sha256": canon[rid]["sha256"],
            "skin_version": skin["skin_version"],
            "skin_sha256": rolelib.entry_sha256(entry),
            "persona_sha256": persona_lib.fingerprint(p),
            "persona_memory_sha256": _sha_json(p["memory"]),
            "persona_depth_sha256": _sha_json(p.get("depth")),
            "team": dict(TEAM_PLACEHOLDER),
        }

    professions = []
    for rid in sorted(canon):
        item = common(rid, "generic")
        professions.append(item)

    roles = []
    for rid in sorted(canon):
        for skin_name in rolelib.SKINS:
            item = common(rid, skin_name)
            item.update({
                "role_id": rid,
                "name": skins[skin_name]["roles"][rid]["name"],
                "skin": skin_name,
            })
            roles.append(item)

    profession_doc = _header(SCHEMA_PROFESSION)
    profession_doc["professions"] = professions
    role_doc = _header(SCHEMA_ROLE)
    role_doc["roles"] = roles
    return {
        "profession-registry/v1.json": profession_doc,
        "role-registry/v1.json": role_doc,
    }


def render_bytes(doc: dict) -> bytes:
    """确定性 JSON 字节：键排序、两空格缩进、LF、无 BOM。"""
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_registries(root: Path, out_dir: Path) -> list[Path]:
    written = []
    for rel, doc in sorted(build_registries(root).items()):
        p = Path(out_dir) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(render_bytes(doc))
        written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="导出角色层只读派生登记（ADR-0034）")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--out", default=None, help="输出目录（默认 <root>/roles/registry）")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out).resolve() if args.out else root / "roles" / "registry"
    for p in write_registries(root, out):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
