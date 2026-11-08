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
from pathlib import Path

ROLE_IDS = ("coordinator", "researcher", "architect", "engineer",
            "designer", "writer", "archivist", "reviewer")
REQUIRED_TOP = ("role_id", "persona_version", "identity_core", "id", "ego", "superego", "memory")
MEMORY_SCOPE = {"task_fact", "preference", "skill", "relationship", "failure_lesson"}


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
        if ego.get("refs") and any(isinstance(r, dict) and len(str(r)) > 200 for r in ego["refs"]):
            errs.append(f"{rid} ego.refs 只放引用，不内联长文本")
        mem = data.get("memory") or {}
        if mem.get("adapter") != "archivist":
            errs.append(f"{rid} memory.adapter 必须是 archivist（记忆唯一写者）")
        if mem.get("storage") != "external":
            errs.append(f"{rid} memory.storage 必须是 external（记忆本体不进仓）")
        if mem.get("write_policy") != "candidate_only":
            errs.append(f"{rid} memory.write_policy 必须是 candidate_only")
        if not set(mem.get("scope") or []) <= MEMORY_SCOPE:
            errs.append(f"{rid} memory.scope 含未知类别")
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
