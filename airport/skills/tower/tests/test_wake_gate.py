#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唤醒门卫的回归网：跳过/放行/死牌接管三态。

跑法：pytest airport/skills/tower/tests
约定：每个用例一个临时仓（真 JSON 实例、真令牌文件、真日表），只调脚本对外命令。
ship-queue 用离线夹具（门卫通过 `--repo` 转调，夹具路径写进实例的同级环境无法传，
故用例覆盖「ship-queue 探测不出」的降级＝放行，以及日表/令牌两条纯本地判据）。
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "wake-gate.py")


def make_repo(interval_min=60, lanes=("main", "deputy", "second")):
    root = tempfile.mkdtemp(prefix="wake-gate-test-")
    os.makedirs(os.path.join(root, ".ai"), exist_ok=True)
    inst = {"schema": 4, "project": "t",
            "paths": {"state_dir": ".git/kai-mode", "day_tables_dir": "tables",
                      "day_table_pattern": "YYYY-MM-DD-{lane}.md", "lanes": list(lanes)},
            "tower_cron": {"interval_min": interval_min}}
    with open(os.path.join(root, ".ai", "kai-mode.project.json"), "w", encoding="utf-8") as f:
        json.dump(inst, f)
    os.makedirs(os.path.join(root, "tables"), exist_ok=True)
    return root


def write_token(repo, holder="A", age_min=0):
    path = os.path.join(repo, ".git", "kai-mode", "tower-token.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    hb = (datetime.now(timezone.utc) - timedelta(minutes=age_min)).isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"holder": holder, "acquired_at": hb, "heartbeat_at": hb, "ttl_min": 125}, f)
    return path


def write_lanes(repo, spec):
    """车道开关：门卫只按启用道判定日表。"""
    path = os.path.join(repo, ".git", "kai-mode", "tower-lanes.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schema": "kai-mode-tower-lanes/1", "spec": spec, "lanes": [],
                   "set_at": "", "source": "command"}, f)


def write_table(repo, lane="main", rows=7, day=None):
    day = day or datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(repo, "tables", f"{day}-{lane}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n|---|---|---|---|---|\n")
        for i in range(rows):
            f.write(f"| {i + 1} | {1800 + i} | m | 干点活 | |\n")
    return path


def run(repo, *args):
    cmd = [sys.executable, SCRIPT, "--repo", repo, *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def test_skip_when_previous_round_still_running():
    repo = make_repo()
    write_token(repo, holder="A", age_min=10)
    write_table(repo, "main"); write_table(repo, "deputy"); write_table(repo, "second")
    rc, out = run(repo)
    assert rc == 10 and "SKIP" in out and "还在跑" in out


def test_stale_token_does_not_block_wake():
    """心跳超过本轮上限（interval+5）＝死牌，门卫不拦，让塔台进去接管。"""
    repo = make_repo(interval_min=60)
    write_token(repo, holder="A", age_min=90)
    write_table(repo, "main", rows=1)  # 顺便让日表见底，保证放行原因是日表
    rc, out = run(repo)
    assert rc == 0 and "WAKE" in out


def test_wake_when_day_table_short():
    repo = make_repo()
    write_table(repo, "main", rows=2)
    write_table(repo, "deputy", rows=7)
    write_table(repo, "second", rows=7)
    rc, out = run(repo)
    assert rc == 0 and "WAKE" in out and "日表" in out and "main=2" in out


def test_wake_when_day_table_absent():
    repo = make_repo()
    rc, out = run(repo)
    assert rc == 0 and "WAKE" in out and "缺表" in out


def test_skip_requires_full_tables_and_empty_queue():
    """日表满 ＋ 队列空（非 git 仓 ⇒ ship-queue 探测失败 ⇒ 按放行处理，不会误 SKIP）。"""
    repo = make_repo()
    for lane in ("main", "deputy", "second"):
        write_table(repo, lane, rows=7)
    rc, out = run(repo)
    # 探测失败必须放行（失败≠零票），所以这里断言 WAKE
    assert rc == 0 and "WAKE" in out


def test_ace_lane_not_counted_as_normal_table():
    repo = make_repo(lanes=("main", "deputy", "second", "ace"))
    for lane in ("main", "deputy", "second"):
        write_table(repo, lane, rows=7)
    write_table(repo, "ace", rows=0)
    rc, out = run(repo)
    assert rc == 0 and "日表" not in out  # ace 不参与下限判定


def test_json_output_has_wake_and_reason():
    repo = make_repo()
    write_token(repo, holder="B", age_min=3)
    rc, out = run(repo, "--json")
    data = json.loads(out)
    assert rc == 10 and data["wake"] is False and "还在跑" in data["reason"]
    assert data["detail"]["token"]["holder"] == "B"


def test_no_token_means_free():
    repo = make_repo()
    write_table(repo, "main", rows=1)
    rc, out = run(repo, "--json")
    data = json.loads(out)
    assert data["wake"] is True
    assert data["detail"]["token"]["state"] == "free"


def test_missing_instance_reports_three_boxes():
    root = tempfile.mkdtemp(prefix="wake-gate-test-")
    rc, out = run(root)
    assert rc == 2 and "缺什么" in out and "谁需要" in out and "怎么补" in out


def test_round_limit_follows_interval():
    repo = make_repo(interval_min=30)
    write_token(repo, holder="A", age_min=45)  # 30+5=35，45 分钟算死牌
    write_table(repo, "main", rows=1)
    rc, out = run(repo, "--json")
    data = json.loads(out)
    assert data["detail"]["token"]["state"] == "stale"
    assert data["detail"]["token"]["limit_min"] == 35


def test_default_spec_ignores_disabled_third_lane():
    """默认 1+2：二副道没开，缺表也不算唤醒理由。"""
    repo = make_repo()
    write_table(repo, "main", rows=7)
    write_table(repo, "deputy", rows=7)
    rc, out = run(repo, "--json")
    data = json.loads(out)
    tables = data["detail"]["day_tables"]
    assert tables["spec"] == "1+2" and tables["absent"] == [] and tables["short"] == []


def test_enabled_third_lane_absent_is_a_wake_reason():
    repo = make_repo()
    write_lanes(repo, "1+2+3")
    write_table(repo, "main", rows=7)
    write_table(repo, "deputy", rows=7)
    rc, out = run(repo, "--json")
    data = json.loads(out)
    tables = data["detail"]["day_tables"]
    assert tables["spec"] == "1+2+3" and "second" in tables["absent"]


def test_ace_only_spec_is_reported_not_silently_skipped():
    repo = make_repo()
    write_lanes(repo, "0")
    rc, out = run(repo, "--json")
    data = json.loads(out)
    assert data["wake"] is True
    assert data["detail"]["day_tables"]["state"] == "error"
    assert "王牌" in data["detail"]["day_tables"]["detail"]
