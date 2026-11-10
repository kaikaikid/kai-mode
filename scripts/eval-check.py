#!/usr/bin/env python3
"""eval-check：固定案例/COM 的确定性检查器（W4.1）。

只管机器可判的维度：信封字段、枚举、证据引用、旧判词禁用、密钥泄露、大白话只考康娜。
人工盲评（清晰度、角色辨识度）不在这里，须由独立评审做，执行者不自评。

用法：
    python scripts/eval-check.py --output <信封 JSON 文件> [--role <role_id>] [--case E-xxx]
输出：{ok: bool, case, role, problems: [...]}，ok=false 时 rc=1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FORBIDDEN_VERDICTS = {"PASS", "CONDITIONAL_PASS", "FAIL", "NEEDS_INFO"}
ROLE_ENUMS = {
    "coordinator", "researcher", "architect", "engineer",
    "designer", "writer", "archivist", "reviewer",
}
CLAIM_KINDS = {"fact", "inference", "unknown", "recommendation"}
VERDICT_VALUES = {"accept", "return", "defer"}
SEVERITIES = {"BLOCKER", "MAJOR", "MINOR", "INFO"}
# 与 engine/coding/state.py 的 _SECRET_PATTERNS 同形（此处独立一份，脚本可脱离包运行）
SECRETS = (
    ("api_key_sk", re.compile(r"sk-[A-Za-z0-9_-]{16,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|github_pat_[A-Za-z0-9_]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("chatops_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


def check(envelope: dict, case: str, role: str | None) -> list[str]:
    p: list[str] = []
    if not isinstance(envelope, dict):
        return ["output must be a JSON object"]

    # 信封头三行
    for key in ("schema_version", "task_id", "role_id", "idempotency_key"):
        if key not in envelope:
            p.append(f"missing required field: {key}")
    rid = envelope.get("role_id") or role
    if rid is not None and rid not in ROLE_ENUMS:
        p.append(f"unknown role_id: {rid}")

    # claims：四类、fact 必带 evidence_refs
    claims = envelope.get("claims")
    if not isinstance(claims, list) or not claims:
        p.append("claims must be a non-empty list")
    else:
        for i, c in enumerate(claims):
            if not isinstance(c, dict) or c.get("kind") not in CLAIM_KINDS:
                p.append(f"claims[{i}]: kind must be one of {sorted(CLAIM_KINDS)}")
                continue
            if c["kind"] == "fact" and not c.get("evidence_refs"):
                p.append(f"claims[{i}]: fact must carry evidence_refs")

    # 判词：三态、严重等级、旧值禁用、仅 reviewer
    v = envelope.get("verdict")
    text = json.dumps(envelope, ensure_ascii=False)
    for old in FORBIDDEN_VERDICTS:
        if f'"{old}"' in text:
            p.append(f"forbidden legacy verdict value: {old}")
    if v is not None:
        if not isinstance(v, dict) or v.get("value") not in VERDICT_VALUES:
            p.append(f"verdict.value must be one of {sorted(VERDICT_VALUES)}")
        if rid != "reviewer":
            p.append("only role_id=reviewer may carry a verdict")
        for i, d in enumerate(v.get("defects") or []):
            sev = d.get("severity") if isinstance(d, dict) else None
            if sev not in SEVERITIES:
                p.append(f"verdict.defects[{i}]: severity must be one of {sorted(SEVERITIES)}")
        if isinstance(v, dict) and v.get("value") == "defer" and not v.get("deferred_items"):
            p.append("verdict=defer must carry deferred_items")

    # artifacts 全字段
    for i, a in enumerate(envelope.get("artifacts") or []):
        need = {"artifact_id", "type", "format", "uri", "version", "created_by"}
        if not isinstance(a, dict) or not need <= set(a):
            p.append(f"artifacts[{i}]: need {sorted(need)}")

    # 密钥泄露（只报模式名）
    for name, pat in SECRETS:
        if pat.search(text):
            p.append(f"secret-like content detected: {name}")

    # COM 只考康娜大白话：只有 coordinator 的 COM 输出不因「专业直述」判错；
    # 反之，非 coordinator 角色不得出现大白话口径标记（避免角色混用）。
    if case.upper().startswith("COM") and rid not in (None, "coordinator"):
        p.append("COM cases are for coordinator only")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, help="envelope JSON file produced by the role")
    ap.add_argument("--role", default=None)
    ap.add_argument("--case", default="")
    a = ap.parse_args()
    path = Path(a.output)
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "case": a.case, "role": a.role,
                          "problems": [f"output not parseable: {e}"]}, ensure_ascii=False))
        return 1
    problems = check(envelope, a.case, a.role)
    print(json.dumps({"ok": not problems, "case": a.case, "role": a.role,
                      "problems": problems}, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
