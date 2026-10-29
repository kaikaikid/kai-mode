#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""车道代号的回归网：语法、优先级、状态文件、命令行三态。

跑法：pytest airport/skills/tower/tests
约定：每个用例一个临时仓（真 JSON 实例、真状态目录），只调模块函数与脚本对外命令。
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "lane_spec.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import lane_spec  # noqa: E402


def make_repo(lanes=("main", "deputy", "second", "ace")):
    root = tempfile.mkdtemp(prefix="lane-spec-test-")
    os.makedirs(os.path.join(root, ".ai"), exist_ok=True)
    inst = {"schema": 4, "project": "t",
            "paths": {"state_dir": ".git/kai-mode", "lanes": list(lanes)}}
    with open(os.path.join(root, ".ai", "kai-mode.project.json"), "w", encoding="utf-8") as f:
        json.dump(inst, f)
    return root


def load(root):
    cfg, state_dir = lane_spec.load_instance(root)
    assert cfg is not None, state_dir
    return cfg, state_dir


def run(*args):
    p = subprocess.run([sys.executable, SCRIPT, *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ---------- 语法 ----------

def test_parse_default_spec():
    assert lane_spec.parse("1+2") == ["main", "deputy"]


def test_parse_all_covers_the_three_normal_lanes():
    assert lane_spec.parse("all") == ["main", "deputy", "second"]
    assert lane_spec.parse("all+0") == ["ace", "main", "deputy", "second"]


def test_parse_normalizes_order_and_duplicates():
    assert lane_spec.parse("3+1+1") == ["main", "second"]


def test_parse_accepts_fullwidth_digits_plus_and_spaces():
    assert lane_spec.parse(" 1 ＋ 3 ") == ["main", "second"]
    assert lane_spec.parse("１＋２") == ["main", "deputy"]


def test_parse_rejects_unknown_code():
    try:
        lane_spec.parse("1+9")
    except ValueError as exc:
        assert "9" in str(exc)
    else:
        raise AssertionError("不认识的代号必须报错")


def test_parse_rejects_empty():
    try:
        lane_spec.parse("   ")
    except ValueError:
        pass
    else:
        raise AssertionError("空代号必须报错，不许静默回落")


def test_canonical_roundtrip():
    assert lane_spec.canonical(lane_spec.parse("all")) == "1+2+3"
    assert lane_spec.canonical(["deputy", "main"]) == "1+2"


# ---------- 优先级 ----------

def test_resolve_defaults_to_1_plus_2():
    root = make_repo()
    cfg, state_dir = load(root)
    got = lane_spec.resolve(cfg, state_dir)
    assert got["spec"] == "1+2" and got["normal"] == ["main", "deputy"]
    assert got["source"] == "default"


def test_explicit_beats_state_file():
    root = make_repo()
    cfg, state_dir = load(root)
    lane_spec.write_setting(state_dir, ["main", "deputy", "second"], "command")
    assert lane_spec.resolve(cfg, state_dir)["spec"] == "1+2+3"
    got = lane_spec.resolve(cfg, state_dir, explicit="3")
    assert got["spec"] == "3" and got["normal"] == ["second"] and got["source"] == "arg"


def test_state_file_survives_reload():
    root = make_repo()
    cfg, state_dir = load(root)
    lane_spec.write_setting(state_dir, lane_spec.parse("1+2+3"), "timer")
    assert lane_spec.read_setting(state_dir)["spec"] == "1+2+3"
    assert lane_spec.resolve(cfg, state_dir)["source"] == "state"


def test_lane_missing_from_inventory_is_dropped():
    root = make_repo(lanes=("main", "ace"))
    cfg, state_dir = load(root)
    got = lane_spec.resolve(cfg, state_dir, explicit="1+2")
    assert got["spec"] == "1" and got["dropped"] == ["deputy"]


def test_ace_only_spec_is_refused_for_scheduling():
    root = make_repo()
    cfg, state_dir = load(root)
    try:
        lane_spec.resolve(cfg, state_dir, explicit="0")
    except ValueError as exc:
        assert "王牌" in str(exc)
    else:
        raise AssertionError("只有王牌道时塔台没得排，必须报错")


def test_corrupt_state_file_falls_back_to_default():
    root = make_repo()
    cfg, state_dir = load(root)
    os.makedirs(state_dir, exist_ok=True)
    with open(lane_spec.setting_path(state_dir), "w", encoding="utf-8") as f:
        f.write("{ not json")
    assert lane_spec.resolve(cfg, state_dir)["source"] == "default"


# ---------- 命令行 ----------

def test_cli_show_reports_default():
    root = make_repo()
    rc, out = run("show", "--repo", root, "--json")
    data = json.loads(out)
    assert rc == 0 and data["spec"] == "1+2" and data["normal"] == ["main", "deputy"]


def test_cli_set_then_show():
    root = make_repo()
    rc, out = run("set", "1+2+3", "--repo", root, "--source", "timer")
    assert rc == 0 and "1+2+3" in out
    rc, out = run("show", "--repo", root, "--json")
    data = json.loads(out)
    assert rc == 0 and data["spec"] == "1+2+3" and data["source"] == "state"


def test_cli_set_rejects_unknown_code():
    root = make_repo()
    rc, out = run("set", "1+7", "--repo", root)
    assert rc == 2 and "7" in out


def test_cli_parse_prints_normalized():
    rc, out = run("parse", "3+1")
    assert rc == 0 and "spec=1+3" in out


def test_cli_missing_instance_is_reported():
    root = tempfile.mkdtemp(prefix="lane-spec-empty-")
    rc, out = run("show", "--repo", root)
    assert rc == 2 and "缺件" in out
