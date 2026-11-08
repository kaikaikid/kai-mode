"""角色经验记忆的测例（Issue #7 AC-07）。

判据实现住 scripts/role-memory.py。测例走**真 CLI**（subprocess），不走内部函数：
AC 断的是「别的角色写入被拒」这个可观测行为，不是「有没有调用某个函数」。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "role-memory.py"


def run(*args, cwd=REPO):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def append(log: Path, writer="archivist", scope="task_fact", statement="测一条",
           evidence=("scripts/x.py:1",), extra=()):
    args = ["append", "--log", str(log), "--writer", writer, "--scope", scope,
            "--statement", statement]
    for e in evidence:
        args += ["--evidence", e]
    return run(*args, *extra)


def records(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── 单写者 ──────────────────────────────────────────────────────────────────
def test_archivist_can_write(tmp_path):
    log = tmp_path / "mem.jsonl"
    r = append(log)
    assert r.returncode == 0, r.stderr
    recs = records(log)
    assert len(recs) == 1
    assert recs[0]["id"] == "m-0001"
    assert recs[0]["writer"] == "archivist"
    assert recs[0]["layer"] == "ego"


def test_every_other_role_is_refused(tmp_path):
    """康娜也不行。写者唯一性不是礼貌，是拒写。"""
    log = tmp_path / "mem.jsonl"
    for role in ("coordinator", "engineer", "reviewer", "researcher",
                 "architect", "designer", "writer", "康娜", "kanna", ""):
        r = append(log, writer=role or "coordinator")
        assert r.returncode == 3, f"{role} 居然写进去了：{r.stdout}"
        assert "唯一读写改者" in r.stderr
    assert records(log) == [], "被拒的写入不许留痕"


# ── 无证据不写 ──────────────────────────────────────────────────────────────
def test_no_evidence_is_refused(tmp_path):
    r = append(tmp_path / "m.jsonl", evidence=())
    assert r.returncode == 2
    assert "至少给一个证据引用" in r.stderr


def test_self_report_is_not_evidence(tmp_path):
    for fake in ("我确认过", "已确认", "无", "-"):
        r = append(tmp_path / "m.jsonl", evidence=(fake,))
        assert r.returncode == 2, fake
        assert "自述类" in r.stderr


def test_bad_scope_is_refused(tmp_path):
    r = append(tmp_path / "m.jsonl", scope="随便")
    assert r.returncode == 2


# ── 追加式 ──────────────────────────────────────────────────────────────────
def test_ids_increment_and_earlier_bytes_never_change(tmp_path):
    log = tmp_path / "mem.jsonl"
    append(log, statement="第一条")
    first = log.read_bytes()
    append(log, statement="第二条")
    append(log, statement="第三条")
    assert log.read_bytes().startswith(first), "追加式：旧行一个字节都不许变"
    assert [r["id"] for r in records(log)] == ["m-0001", "m-0002", "m-0003"]


# ── 回滚与审计 ──────────────────────────────────────────────────────────────
def test_rollback_appends_and_keeps_original(tmp_path):
    log = tmp_path / "mem.jsonl"
    append(log, statement="原先的判断")
    r = run("rollback", "--log", str(log), "--writer", "archivist",
            "--target", "m-0001", "--reason", "后面发现证据不支持")
    assert r.returncode == 0, r.stderr
    recs = records(log)
    assert len(recs) == 2
    assert recs[0]["statement"] == "原先的判断", "原记录必须留着"
    assert recs[1]["rollback_of"] == "m-0001"
    assert "证据不支持" in recs[1]["statement"]


def test_rollback_requires_reason_and_existing_target(tmp_path):
    log = tmp_path / "mem.jsonl"
    append(log)
    assert run("rollback", "--log", str(log), "--writer", "archivist",
               "--target", "m-0001", "--reason", "").returncode == 2
    assert run("rollback", "--log", str(log), "--writer", "archivist",
               "--target", "m-9999", "--reason", "x").returncode == 2


def test_rollback_by_non_archivist_is_refused(tmp_path):
    log = tmp_path / "mem.jsonl"
    append(log)
    r = run("rollback", "--log", str(log), "--writer", "coordinator",
            "--target", "m-0001", "--reason", "x")
    assert r.returncode == 3
    assert len(records(log)) == 1


def test_show_hides_rolled_back_but_file_keeps_it(tmp_path):
    log = tmp_path / "mem.jsonl"
    append(log, statement="会被撤的")
    run("rollback", "--log", str(log), "--writer", "archivist",
        "--target", "m-0001", "--reason", "撤")
    out = json.loads(run("show", "--log", str(log), "--json").stdout)
    assert out == [], "活跃视图里不该有被撤的条目"
    assert len(records(log)) == 2, "文件里必须有两条（审计靠它）"


# ── 校验器抓得到被手改的日志 ────────────────────────────────────────────────
def test_check_green_on_real_log(tmp_path):
    log = tmp_path / "mem.jsonl"
    append(log)
    append(log, scope="failure_lesson", statement="教训")
    r = run("check", "--log", str(log), "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["ok"] is True


def test_check_catches_foreign_writer(tmp_path):
    """有人绕开工具手写一条 coordinator 的记录，校验必须红。"""
    log = tmp_path / "mem.jsonl"
    append(log)
    log.write_text(log.read_text(encoding="utf-8") + json.dumps({
        "id": "m-0002", "ts": "2026-01-01T00:00:00Z", "writer": "coordinator",
        "scope": "task_fact", "layer": "ego", "statement": "手写进来的",
        "evidence_refs": ["x:1"], "before": "", "after": "",
        "conflicts_with": [], "rollback_of": None,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    r = run("check", "--log", str(log), "--json")
    assert r.returncode == 4
    problems = json.loads(r.stdout)["problems"]
    assert any("只许 archivist" in p for p in problems), problems


def test_check_catches_missing_evidence_and_bad_layer(tmp_path):
    log = tmp_path / "mem.jsonl"
    log.write_text(json.dumps({
        "id": "m-0001", "ts": "2026-01-01T00:00:00Z", "writer": "archivist",
        "scope": "task_fact", "layer": "superego", "statement": "x",
        "evidence_refs": [], "before": "", "after": "",
        "conflicts_with": [], "rollback_of": None,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    out = json.loads(run("check", "--log", str(log), "--json").stdout)
    joined = " ".join(out["problems"])
    assert "没有证据引用" in joined
    assert "只许 ego" in joined
    assert out["ok"] is False


def test_check_empty_log_is_green(tmp_path):
    r = run("check", "--log", str(tmp_path / "nope.jsonl"), "--json")
    assert r.returncode == 0
    assert json.loads(r.stdout)["records"] == 0


# ── 反向：尺子不是恒绿 ──────────────────────────────────────────────────────
def test_reverse_writer_gate_actually_depends_on_role(tmp_path):
    """同一个 log，换个 writer 结果必须翻——自证拒写不是因为别的错。"""
    log = tmp_path / "mem.jsonl"
    assert append(log, writer="archivist").returncode == 0
    assert append(log, writer="writer").returncode == 3
    assert len(records(log)) == 1