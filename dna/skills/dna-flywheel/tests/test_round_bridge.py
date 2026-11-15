"""dna-flywheel round-file 与 2.0 嵌套 validate 回归（纯文件，不写真库/正本）。"""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dna_flywheel.py"


def _load():
    spec = importlib.util.spec_from_file_location("dna_flywheel_bridge", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


ONTO = {
    "meta": {"ontology_version": "test-1"},
    "loci": [{
        "id": "support",
        "subfields": [{"key": "support", "cardinality": "single"}],
        "alleles": [
            {"id": "texture-002", "subfield_key": "support", "status": "active"},
            {"id": "texture-003", "subfield_key": "support", "status": "active"},
            {"id": "support-001", "subfield_key": "support", "status": "retired"},
        ],
    }],
    "result_labels": [],
}


def test_round_file_derives_gold_pred_and_subfield_metrics(tmp_path, capsys):
    f = tmp_path / "round.json"
    _write(f, {
        "round_id": "round-007",
        "locus_key": "support",
        "records": [
            {"asset_id": "a1", "subfield_key": "support", "human_allele_id": "texture-002",
             "ai_allele_id": "texture-002", "verdict": "confirmed"},
            {"asset_id": "a2", "subfield_key": "support", "human_allele_id": "texture-003",
             "ai_allele_id": "texture-002", "verdict": "rejected",
             "replaced_by_allele_id": "texture-003"},
            {"asset_id": "a3", "subfield_key": "support", "human_allele_id": None,
             "ai_allele_id": None, "verdict": None},
        ],
    })
    mod = _load()
    rc = mod.main(["evaluate", "--round-file", str(f)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["round_id"] == "round-007"
    metrics = out["artifacts"][0]["metrics"]
    assert metrics["samples"] == 3
    assert metrics["tp"] == 1 and metrics["fp"] == 1 and metrics["fn"] == 1
    sf = metrics["by_subfield"]["support"]
    assert sf["tp"] == 1 and sf["fp"] == 1 and sf["fn"] == 1
    assert sf["confirmed"] == 1 and sf["rejected"] == 1
    assert sf["rejected_with_replacement"] == 1
    assert sf["samples"] == 3  # 人工留空样本不丢


def test_old_gold_pred_path_is_unchanged(tmp_path, capsys):
    gold = tmp_path / "gold.json"
    pred = tmp_path / "pred.json"
    _write(gold, {"records": [{"asset_id": "a1", "alleles": ["texture-002"]}]})
    _write(pred, {"records": [{"asset_id": "a1", "alleles": ["texture-002"]}]})
    mod = _load()
    rc = mod.main(["evaluate", "--gold", str(gold), "--pred", str(pred)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    metrics = out["artifacts"][0]["metrics"]
    assert "by_subfield" not in metrics
    assert metrics["tp"] == 1 and metrics["samples"] == 1


def test_validate_accepts_nested_2_0_shape(tmp_path, capsys):
    onto = tmp_path / "onto.json"
    recs = tmp_path / "records.json"
    _write(onto, ONTO)
    _write(recs, {"records": [{
        "asset_id": "a1",
        "visual_dna": {"loci": {"support": {"id": "support", "values": [
            {"subfield_key": "support", "allele_id": "texture-002"},
        ]}}},
    }]})
    mod = _load()
    rc = mod.main(["validate", "--records", str(recs), "--ontology", str(onto)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["blocked_reason"] is None
    assert out["findings"] == []


def test_validate_blocks_retired_nested_allele(tmp_path, capsys):
    onto = tmp_path / "onto.json"
    recs = tmp_path / "records.json"
    _write(onto, ONTO)
    _write(recs, {"records": [{
        "asset_id": "a1",
        "visual_dna": {"loci": {"support": {"id": "support", "values": [
            {"subfield_key": "support", "allele_id": "support-001"},
        ]}}},
    }]})
    mod = _load()
    rc = mod.main(["validate", "--records", str(recs), "--ontology", str(onto)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["blocked_reason"].startswith("V-003")
    assert out["findings"][0]["code"] == "V-003"


def test_validate_warns_when_single_cardinality_exceeded(tmp_path, capsys):
    onto = tmp_path / "onto.json"
    recs = tmp_path / "records.json"
    _write(onto, ONTO)
    _write(recs, {"records": [{
        "asset_id": "a1",
        "visual_dna": {"loci": {"support": {"id": "support", "values": [
            {"subfield_key": "support", "allele_id": "texture-002"},
            {"subfield_key": "support", "allele_id": "texture-003"},
        ]}}},
    }]})
    mod = _load()
    rc = mod.main(["validate", "--records", str(recs), "--ontology", str(onto)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert any(f["code"] == "V-006" and f["level"] == "warn" for f in out["findings"])
    assert out["blocked_reason"] is None


def test_stubs_still_exit_3_and_reflux_does_not_write_canon(capsys):
    mod = _load()
    for name in mod.STUBS:
        assert mod.main([name]) == 3
    capsys.readouterr()
