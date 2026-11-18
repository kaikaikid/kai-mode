# -*- coding: utf-8 -*-
"""map-check 自身的测试：schema 自检、正常地图、坏 JSON、缺攻略、重复 region-id。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "scripts" / "map-check.py"
GUIDE_SCHEMA = ROOT / "schemas" / "guide.schema.json"
MAP_SCHEMA = ROOT / "schemas" / "map.schema.json"
GUIDE_TEMPLATE = ROOT / "templates" / "GUIDE-template.md"


def _mod():
    spec = importlib.util.spec_from_file_location("map_check", SPEC)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(m)
    return m


def _sections():
    return json.loads(GUIDE_SCHEMA.read_text(encoding="utf-8"))["x-guide-sections"]


def _region(repo: Path, **over):
    region = {
        "id": "demo",
        "name": "Demo",
        "path": str(repo),
        "remote": "https://example.com/demo.git",
        "default_branch": "main",
        "instance": ".ai/kai-mode.project.json",
        "guide": ".ai/GUIDE.md",
        "runtime": {"backend_python": None, "node": None, "deps": None},
        "channels": ["claude"],
        "trust": "trusted",
    }
    region.update(over)
    return region


def _make_region(root: Path, name: str = "demo", guide: bool = True, **over):
    repo = root / name
    (repo / ".ai").mkdir(parents=True)
    (repo / ".ai" / "kai-mode.project.json").write_text("{}", encoding="utf-8")
    if guide:
        headings = "\n".join(f"## {s['title']}" for s in _sections())
        (repo / ".ai" / "GUIDE.md").write_text(headings + "\n", encoding="utf-8")
    return _region(repo, id=name, name=name, **over)


def _write_map(root: Path, regions, raw: str | None = None) -> Path:
    path = root / "map.json"
    if raw is None:
        raw = json.dumps({"schema": "kai-map/1", "regions": regions}, ensure_ascii=False)
    path.write_text(raw, encoding="utf-8")
    return path


def test_schemas_self_check_and_template_matches():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(json.loads(MAP_SCHEMA.read_text(encoding="utf-8")))
    jsonschema.Draft202012Validator.check_schema(json.loads(GUIDE_SCHEMA.read_text(encoding="utf-8")))
    template = GUIDE_TEMPLATE.read_text(encoding="utf-8")
    for section in _sections():
        assert f"## {section['title']}" in template, section["title"]


def test_valid_map_passes(tmp_path, capsys):
    regions = [_make_region(tmp_path)]
    code = _mod().main(["--map", str(_write_map(tmp_path, regions))])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "[红]" not in out
    assert "region-id 唯一" in out


def test_bad_json_is_reported(tmp_path, capsys):
    path = _write_map(tmp_path, [], raw="{not json")
    code = _mod().main(["--map", str(path)])
    out = capsys.readouterr().out
    assert code == 2, out
    assert "JSON" in out


def test_missing_guide_is_red(tmp_path, capsys):
    region = _make_region(tmp_path, guide=False)
    code = _mod().main(["--map", str(_write_map(tmp_path, [region]))])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "guide" in out
    assert "[红]" in out


def test_duplicate_region_id_is_red(tmp_path, capsys):
    region = _make_region(tmp_path)
    code = _mod().main(["--map", str(_write_map(tmp_path, [region, dict(region)]))])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "重复 region-id" in out
    assert "demo" in out
