"""人格层契约测试：八份 persona、内核只读、ego 只放引用、记忆走 archivist。"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import persona  # noqa: E402


def test_persona_validates():
    assert persona.validate(REPO) == []


def test_eight_personas_match_role_ids():
    files = {p.stem for p in (REPO / "roles" / "persona").glob("*.json")}
    assert files == set(persona.ROLE_IDS)


def test_identity_core_is_immutable_and_versioned():
    for rid in persona.ROLE_IDS:
        p = persona.load(REPO, rid)
        core = p["identity_core"]
        assert core["immutable"] is True
        assert core["version"]
        assert core["name"] in core["identity"]


def test_ego_holds_refs_only():
    for rid in persona.ROLE_IDS:
        ego = persona.load(REPO, rid)["ego"]
        assert isinstance(ego.get("refs"), list)
        for ref in ego["refs"]:
            assert len(str(ref)) <= 200, f"{rid} ego.refs 内联了长文本"


def test_memory_goes_through_archivist_and_stays_external():
    for rid in persona.ROLE_IDS:
        mem = persona.load(REPO, rid)["memory"]
        assert mem["adapter"] == "archivist"
        assert mem["storage"] == "external"
        assert mem["write_policy"] == "candidate_only"
        assert set(mem["scope"]) <= persona.MEMORY_SCOPE


def test_fingerprint_is_stable_and_sensitive():
    p = persona.load(REPO, "designer")
    assert persona.fingerprint(p) == persona.fingerprint(json.loads(json.dumps(p)))
    changed = json.loads(json.dumps(p))
    changed["identity_core"]["identity"] += "（改）"
    assert persona.fingerprint(changed) != persona.fingerprint(p)


def test_profession_matches_tavern_professions():
    expect = {
        "coordinator": "酒馆守护者、首席掌铃",
        "researcher": "卓尔游侠",
        "architect": "符文法师",
        "engineer": "矮人工匠",
        "designer": "德鲁伊",
        "writer": "游学者",
        "archivist": "青铜龙",
        "reviewer": "圣骑士",
    }
    for rid, prof in expect.items():
        assert persona.load(REPO, rid)["identity_core"]["profession"] == prof
