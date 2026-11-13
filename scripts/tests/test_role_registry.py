# -*- coding: utf-8 -*-
"""角色层只读派生登记：导出幂等 + doctor 指纹门（ADR-0034 D4/D5 门①）。"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY_REL = ("profession-registry/v1.json", "role-registry/v1.json")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


export = _load("_test_registry_export", REPO / "scripts" / "export-role-registry.py")
doctor = _load("_test_registry_doctor", REPO / "scripts" / "doctor.py")


def _root(tmp_path: Path) -> Path:
    """最小可导出/可体检的假仓：roles 全拷，scripts 只拷三件入口。"""
    root = tmp_path / "repo"
    shutil.copytree(REPO / "roles", root / "roles",
                    ignore=shutil.ignore_patterns("registry", "__pycache__"))
    (root / "scripts").mkdir()
    for f in ("rolelib.py", "persona.py", "export-role-registry.py"):
        shutil.copy2(REPO / "scripts" / f, root / "scripts" / f)
    return root


def _export(root: Path) -> dict[str, bytes]:
    out = root / "roles" / "registry"
    export.write_registries(root, out)
    return {rel: (out / rel).read_bytes() for rel in REGISTRY_REL}


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def test_export_is_idempotent_and_lf(tmp_path):
    root = _root(tmp_path)
    first = _export(root)
    second = _export(root)
    assert first == second
    for rel, blob in first.items():
        assert not blob.startswith(b"\xef\xbb\xbf"), rel
        assert b"\r\n" not in blob, rel


def test_export_same_sha_under_crlf_worktree(tmp_path):
    root = _root(tmp_path)
    lf = _export(root)
    p = root / "roles" / "canon" / "reviewer.md"
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    _atomic_write(p, text.replace("\n", "\r\n").encode("utf-8"))
    crlf = _export(root)
    assert lf == crlf


def test_doctor_red_when_canon_changed_without_reexport(tmp_path):
    root = _root(tmp_path)
    _export(root)
    assert doctor.chk_role_registry(str(root), None)[0] == "ok"
    p = root / "roles" / "canon" / "engineer.md"
    _atomic_write(p, p.read_bytes() + "新增一行。\n".encode("utf-8"))
    status, detail = doctor.chk_role_registry(str(root), None)
    assert status == "fail", detail
    assert "profession-registry/v1.json" in detail and "engineer" in detail, detail
    _export(root)
    assert doctor.chk_role_registry(str(root), None)[0] == "ok"


def test_doctor_red_on_manual_registry_edit(tmp_path):
    root = _root(tmp_path)
    _export(root)
    p = root / "roles" / "registry" / "role-registry" / "v1.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["roles"][0]["canon_sha256"] = "0" * 64
    _atomic_write(p, (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    status, detail = doctor.chk_role_registry(str(root), None)
    assert status == "fail", detail
    assert "role-registry/v1.json" in detail and "canon_sha256" in detail, detail


def test_doctor_red_when_registry_missing(tmp_path):
    root = _root(tmp_path)
    status, detail = doctor.chk_role_registry(str(root), None)
    assert status == "fail" and "未导出" in detail, detail


def test_registry_has_pointers_not_bodies(tmp_path):
    root = _root(tmp_path)
    out = root / "roles" / "registry"
    export.write_registries(root, out)
    docs = {rel: json.loads((out / rel).read_text(encoding="utf-8")) for rel in REGISTRY_REL}
    prof_keys = set(docs["profession-registry/v1.json"]["professions"][0])
    role_keys = set(docs["role-registry/v1.json"]["roles"][0])
    required = {"profession_id", "profession_name", "canon_version", "canon_sha256",
                "skin_version", "skin_sha256", "persona_sha256",
                "persona_memory_sha256", "team"}
    assert required <= prof_keys and required <= role_keys
    assert len(docs["profession-registry/v1.json"]["professions"]) == 8
    assert len(docs["role-registry/v1.json"]["roles"]) == 16
    text = (out / REGISTRY_REL[0]).read_text(encoding="utf-8") + \
           (out / REGISTRY_REL[1]).read_text(encoding="utf-8")
    for forbidden in ("mission", "boundaries", "workflow", "output_contract",
                      "personality", "identity_core"):
        assert forbidden not in text, forbidden
