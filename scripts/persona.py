"""人格层校验与指纹（roles/persona/<role>.json）。

人格层是 canon（职责）与 skin（名字/性格）之外的第三层：
  identity_core  原初内核：只读基线，版本化，不可覆盖
  id             本我：天性与欲望
  ego            自我：成长层，只放记忆引用，不内联事实
  superego       超我：价值与行为准则
  memory         记忆接口声明：记忆本体在仓外，只有 archivist 能写

本模块只做两件事：validate（结构/契约）与 fingerprint（原初内核稳定性）。
记忆读写本身的实现留给外部记忆库（adapter=archivist），框架只定义接口。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROLE_IDS = ("coordinator", "researcher", "architect", "engineer",
            "designer", "writer", "archivist", "reviewer")
REQUIRED_TOP = ("role_id", "persona_version", "identity_core", "id", "ego", "superego", "memory")
MEMORY_SCOPE = {"task_fact", "preference", "skill", "relationship", "failure_lesson"}
# 深度人格层（按需）：五个段位。层内长文本不进 system prompt，只在闲聊／深度情境现取。
DEPTH_SECTIONS = ("three_layers", "stakes", "bond", "voice", "growth")
DEPTH_LAYER = "按需层"
# 单角色 depth 正文上限（UTF-8 字节）：按需层不许悄悄长成常驻层。
# coordinator 实测 4,518 B（1,506 字）；给到 8 KB 留足余量，仍能拦住失控增长。
DEPTH_MAX_BYTES = 8192
# ego.refs 单条上限：字符串与对象一律按字符数算（老口径只管对象型，字符串型是洞）。
EGO_REF_MAX_CHARS = 200


def persona_dir(root: Path | str) -> Path:
    return Path(root) / "roles" / "persona"


def load(root: Path | str, role_id: str) -> dict:
    p = persona_dir(root) / f"{role_id}.json"
    if not p.is_file():
        raise FileNotFoundError(f"缺人格层：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def fingerprint(persona: dict) -> str:
    """原初内核指纹：稳定序列化后 sha256；改内核即变，可用于记忆注入与迁移校验。"""
    core = persona["identity_core"]
    blob = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate(root: Path | str) -> list[str]:
    root = Path(root)
    errs: list[str] = []
    d = persona_dir(root)
    if not d.is_dir():
        return ["缺 roles/persona/ 目录"]
    for rid in ROLE_IDS:
        p = d / f"{rid}.json"
        if not p.is_file():
            errs.append(f"缺 {rid}.json")
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            errs.append(f"{rid}.json 不是合法 JSON：{e}")
            continue
        if data.get("role_id") != rid:
            errs.append(f"{rid}.json role_id 不符：{data.get('role_id')!r}")
        for k in REQUIRED_TOP:
            if k not in data:
                errs.append(f"{rid}.json 缺字段 {k}")
        core = data.get("identity_core") or {}
        if core.get("immutable") is not True:
            errs.append(f"{rid} identity_core.immutable 必须为 true")
        for k in ("version", "name", "profession", "identity"):
            if not core.get(k):
                errs.append(f"{rid} identity_core 缺 {k}")
        ego = data.get("ego") or {}
        if ego.get("refs") and any(len(str(r)) > EGO_REF_MAX_CHARS for r in ego["refs"]):
            errs.append(f"{rid} ego.refs 只放引用，不内联长文本"
                        f"（每条 ≤{EGO_REF_MAX_CHARS} 字符；字符串型与对象型都算）")
        mem = data.get("memory") or {}
        if mem.get("adapter") != "archivist":
            errs.append(f"{rid} memory.adapter 必须是 archivist（记忆唯一写者）")
        if mem.get("storage") != "external":
            errs.append(f"{rid} memory.storage 必须是 external（记忆本体不进仓）")
        if mem.get("write_policy") != "candidate_only":
            errs.append(f"{rid} memory.write_policy 必须是 candidate_only")
        if not set(mem.get("scope") or []) <= MEMORY_SCOPE:
            errs.append(f"{rid} memory.scope 含未知类别")
        errs.extend(_depth_errors(rid, data.get("depth")))
    return errs


def _depth_errors(rid: str, depth) -> list[str]:
    """深度人格层（按需）的结构契约。没接入＝不红，接入了就得合规。"""
    if depth is None:
        return []
    if not isinstance(depth, dict):
        return [f"{rid} depth 不是对象"]
    errs: list[str] = []
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(depth.get("depth_version", ""))):
        errs.append(f"{rid} depth 缺 depth_version（须 x.y.z）")
    if str(depth.get("layer", "")) != DEPTH_LAYER:
        errs.append(f"{rid} depth.layer 必须是「{DEPTH_LAYER}」")
    for k in DEPTH_SECTIONS:
        if not str(depth.get(k) or "").strip():
            errs.append(f"{rid} depth 缺 {k}")
    scope = str(depth.get("scope") or "")
    if "不进 system prompt" not in scope:
        errs.append(f"{rid} depth.scope 必须写明「不进 system prompt」")
    blob = "".join(str(depth.get(k) or "") for k in DEPTH_SECTIONS)
    nbytes = len(blob.encode("utf-8"))
    if nbytes > DEPTH_MAX_BYTES:
        errs.append(f"{rid} depth 正文超上限（{nbytes} > {DEPTH_MAX_BYTES} 字节）"
                    f"——按需层不许悄悄长成常驻层")
    return errs


def cli(argv: list[str]) -> int:
    root = Path(os.getcwd())
    cmd = argv[0] if argv else "validate"
    if cmd == "validate":
        errs = validate(root)
        if errs:
            print("人格层不合契约：")
            for e in errs:
                print(" -", e)
            return 1
        print(f"人格层合规：{len(ROLE_IDS)} 份（原初内核只读、ego 只放引用、记忆走 archivist）")
        return 0
    if cmd == "fingerprint":
        rid = argv[1] if len(argv) > 1 else "coordinator"
        print(fingerprint(load(root, rid)))
        return 0
    if cmd == "list":
        for rid in ROLE_IDS:
            p = load(root, rid)
            print(f"{rid:12s} {p['identity_core']['profession']:8s} {fingerprint(p)[:12]}")
        return 0
    print("用法：python scripts/persona.py [validate|fingerprint <role>|list]")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(cli(sys.argv[1:]))
