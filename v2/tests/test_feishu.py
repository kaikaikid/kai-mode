"""飞书桥：纯逻辑与桥的编排（不碰真 lark-cli、不碰真模型）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from v2.coding import adapters
from v2.coding.feishu import bridge as fbridge
from v2.coding.feishu import cards, config as fcfg, ledger as fledger, notify, outbox, policy, triage
from v2.coding.feishu import wake as fwake

REPO = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# 配置


def test_config_defaults_are_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    cfg = fcfg.load(tmp_path / "proj")
    assert cfg["enabled"] is False
    assert cfg["allow"]["users"] == []
    assert cfg["chat"]["enabled"] is True and cfg["chat"]["max_turns"] == 20
    assert cfg["bots"][0]["name"] == "default"
    assert fcfg.problems(cfg)                       # 默认配置必然有问题（未启用/无白名单）


def test_config_merges_machine_and_project(monkeypatch, tmp_path):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    fcfg.save_machine({"enabled": True, "allow": {"users": ["ou_me"]},
                       "bots": [{"name": "work", "profile": "p1", "chat_id": "oc_1"}]})
    proj = tmp_path / "proj"
    (proj / ".coding").mkdir(parents=True)
    (proj / ".coding" / "feishu.json").write_text('{"chat": {"enabled": false}}', encoding="utf-8")

    cfg = fcfg.load(proj)
    assert cfg["enabled"] is True and cfg["allow"]["users"] == ["ou_me"]
    assert cfg["bots"][0]["name"] == "work"
    assert cfg["chat"]["enabled"] is False          # 项目级覆盖
    assert cfg["chat"]["max_turns"] == 20           # 其余仍取默认


def test_single_bot_shorthand_normalized(monkeypatch, tmp_path):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    fcfg.save_machine({"bots": {"name": "solo", "chat_id": "oc_x"}})
    cfg = fcfg.load(None)
    assert cfg["bots"] == [{"name": "solo", "profile": "", "app_id": "", "chat_id": "oc_x"}]


# ---------------------------------------------------------------------------
# 归一化与白名单


def _msg(**kw):
    raw = {"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me",
           "message_id": "om_1", "content": "@_user_1 状态", "mentions": [{"id": "ou_bot"}]}
    raw.update(kw)
    return policy.normalize(raw, "im.message.receive_v1", "work")


def test_message_dedups_by_message_id_not_delivery_id():
    a = _msg(event_id="evt-1")
    b = _msg(event_id="evt-2")            # 同一条消息重投，投递 id 变了
    assert a["dedup_key"] == b["dedup_key"] == "msg:om_1"


def test_card_action_dedups_by_nonce():
    raw = {"chat_id": "oc_1", "chat_type": "group", "operator_id": "ou_me",
           "action": {"nonce": "n1", "kind": "gate", "run_id": "r-1"}}
    ev = policy.normalize(raw, "card.action.trigger", "work")
    assert ev["dedup_key"] == "card:n1" and ev["action"]["run_id"] == "r-1"


def test_allow_is_closed_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "d"))
    cfg = fcfg.load(None)
    assert policy.allowed(cfg, _msg()) is False


def test_allow_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "d"))
    cfg = fcfg.load(None)
    cfg["allow"] = {"users": ["ou_me"], "chats": ["oc_1"], "dm": True, "require_mention": True}
    assert policy.allowed(cfg, _msg()) is True
    assert policy.allowed(cfg, _msg(chat_id="oc_other")) is False
    assert policy.allowed(cfg, _msg(mentions=[])) is False          # 群里必须 @
    assert policy.allowed(cfg, _msg(chat_type="p2p", mentions=[])) is True
    assert policy.allowed(cfg, _msg(sender_id="ou_someone")) is False


def test_mention_stripping():
    assert policy.strip_mentions("@_user_1  帮我看看") == "帮我看看"


# ---------------------------------------------------------------------------
# 分诊


@pytest.mark.parametrize("text,kind,needs_ai", [
    ("状态", "status", False),
    ("看板", "board", False),
    ("想法 导出支持 CSV", "idea", False),
    ("记住 我不喜欢自动合并", "remember", False),
    ("新话题", "new_topic", False),
    ("票 导出支持 CSV", "ticket", True),
    ("曲速 给导出加 CSV", "run", True),
    ("跃迁 给导出加 CSV", "run", True),
    ("批 g2 r-abc", "gate", False),
    ("拒 g1 r-abc", "gate", False),
    ("停 r-abc", "stop", False),
    ("发货 r-abc", "ship_confirm", False),
    ("确认发货 r-abc", "gate", False),
    ("今天天气不错", "chat", True),
])
def test_triage_decisions(text, kind, needs_ai):
    d = triage.decide(text)
    assert d["kind"] == kind
    assert d["needs_ai"] is needs_ai


def test_triage_gate_defaults_and_args():
    d = triage.decide("批 g2 r-abc")
    assert d["args"] == {"gate": "g2", "run_id": "r-abc", "decision": "approve"}
    d = triage.decide("驳回 r-abc")
    assert d["args"]["decision"] == "reject" and d["args"]["gate"] == "g2"
    assert triage.decide("确认发货 r-abc")["args"]["decision"] == "approve"


def test_six_pieces_hint():
    text = "目标：能导 CSV；AC：空数据也能导；允许改 src/export；禁止动其它模块；验证：pytest；依赖：无"
    assert triage.missing_pieces(text) == []


# ---------------------------------------------------------------------------
# 卡片


def test_board_card_lists_runs_and_caps():
    rows = [{"run_id": f"r-{i}", "phase": "delegating", "progress": "1/2",
             "next_action": "施工"} for i in range(12)]
    c = cards.board(rows)
    body = json.dumps(c, ensure_ascii=False)
    assert "r-0" in body and "还有 2 个未显示" in body


def test_gate_card_has_two_buttons():
    c = cards.gate_request("r-1", "g2", "等你批", "nonce1")
    actions = [e for e in c["elements"] if e["tag"] == "action"][0]["actions"]
    assert [a["text"]["content"] for a in actions] == ["批准", "打回"]


# ---------------------------------------------------------------------------
# 账本


@pytest.fixture
def ledger(tmp_path):
    lg = fledger.Ledger(tmp_path / "l.sqlite3")
    yield lg
    lg.close()


def test_ledger_event_dedup(ledger):
    assert ledger.remember_event("k1", "bot", "message") is True
    assert ledger.remember_event("k1", "bot", "message") is False
    assert ledger.has_event("k1") is True


def test_ledger_session_lifecycle(ledger):
    ledger.bind_session("b|dm|u", "bot", "s-1", "claude-cli")
    s = ledger.session("b|dm|u")
    assert s["host_session"] == "s-1" and s["turns"] == 0
    ledger.touch_session("b|dm|u", 1, 1200)
    s = ledger.session("b|dm|u")
    assert s["turns"] == 1 and s["tokens"] == 1200
    ledger.drop_session("b|dm|u")
    assert ledger.session("b|dm|u") is None


def test_ledger_counters_and_outbox(ledger):
    assert ledger.bump("rate:ou_me", "minute", 1) == 1
    assert ledger.bump("rate:ou_me", "minute", 1) == 2
    assert ledger.count("rate:ou_me", "minute") == 2
    assert ledger.enqueue("idem-1", "bot", "oc_1", '{"text":"hi"}') is True
    assert ledger.enqueue("idem-1", "bot", "oc_1", '{"text":"hi"}') is False
    assert len(ledger.pending()) == 1


# ---------------------------------------------------------------------------
# 状态与播报


def _state(root: Path, run: str, phase: str, gates=None, tasks=()):
    d = root / ".coding" / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps({
        "run_id": run, "phase": phase, "gates": gates or {}, "updated_at": 1,
        "tasks": [{"id": t, "status": "accepted"} for t in tasks],
        "resume": {"next_action": "等你批 G2"},
    }, ensure_ascii=False), encoding="utf-8")


def test_run_rows_and_transitions(tmp_path):
    _state(tmp_path, "r-1", "done", tasks=("t1",))
    rows = notify.run_rows(tmp_path)
    assert rows[0]["run_id"] == "r-1" and rows[0]["progress"] == "1/1"
    t = notify.transitions({}, rows)
    assert t and t[0]["kind"] == "done"
    fp = t[0]["fingerprint"]
    assert notify.transitions({"r-1": fp}, notify.run_rows(tmp_path)) == []


def test_gate_pending_triggers_card(tmp_path):
    _state(tmp_path, "r-2", "closing", gates={"g2": "pending"})
    t = notify.transitions({}, notify.run_rows(tmp_path))
    assert t[0]["kind"] == "gate"


# ---------------------------------------------------------------------------
# 桥


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    cfg = fcfg.load(tmp_path)
    cfg["allow"] = {"users": ["ou_me"], "chats": ["oc_1"], "dm": True, "require_mention": True}
    cfg["enabled"] = True
    cfg["bots"] = [{"name": "work", "profile": "", "chat_id": "oc_1"}]   # 播报要有落点
    woken = []

    def wake(brief, cwd, resume=None):
        woken.append({"brief": brief, "resume": resume})
        return {"text": f"回答 #{len(woken)}", "session_id": resume or "s-host-1",
                "tokens": 100, "adapter": "mock"}

    b = fbridge.Bridge(tmp_path, cfg, wake_fn=wake)
    b.woken = woken                      # type: ignore[attr-defined]
    yield b
    b.ledger.close()


def _event(b, **kw):
    raw = {"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me",
           "message_id": "om_1", "content": "@_user_1 状态", "mentions": [{"id": "ou_bot"}]}
    raw.update(kw)
    return policy.normalize(raw, "im.message.receive_v1", "work")


def test_unauthorized_is_dropped_and_audited(bridge, tmp_path):
    ev = _event(bridge, sender_id="ou_stranger")
    assert bridge.handle(ev) == []
    audit = (tmp_path / ".coding" / "feishu" / "audit" / "unauthorized.ndjson").read_text(encoding="utf-8")
    assert "ou_stranger" in audit
    assert "状态" not in audit            # 默认不存正文


def test_duplicate_event_handled_once(bridge):
    ev = _event(bridge)
    assert bridge.handle(ev)
    assert bridge.handle(ev) == []


def test_status_returns_board_card(bridge, tmp_path):
    _state(tmp_path, "r-1", "delegating")
    out = bridge.handle(_event(bridge, message_id="om_2"))
    assert out and out[0]["card"]["header"]["title"]["content"] == "任务看板"
    assert "r-1" in json.dumps(out[0]["card"], ensure_ascii=False)


def test_idea_written_verbatim(bridge, tmp_path):
    ev = _event(bridge, message_id="om_3", content="@_user_1 想法 导出要支持空数据")
    out = bridge.handle(ev)
    assert "记进想法池" in out[0]["text"]
    files = list((tmp_path / "ideas").glob("*.md"))
    assert files and "导出要支持空数据" in files[0].read_text(encoding="utf-8")


def test_remember_writes_notes_and_drops_session(bridge):
    bridge.handle(_event(bridge, message_id="om_4", content="@_user_1 记住 我不喜欢自动合并"))
    notes = bridge.dir / "notes.md"
    assert "我不喜欢自动合并" in notes.read_text(encoding="utf-8")


def test_chat_binds_session_then_resumes(bridge):
    a = bridge.handle(_event(bridge, message_id="om_5", content="@_user_1 这段代码为什么慢"))
    assert a[0]["text"].startswith("回答 #1")
    sess = bridge.ledger.session(policy.binding_key(_event(bridge, message_id="om_5")))
    assert sess and sess["host_session"] == "s-host-1"

    bridge.handle(_event(bridge, message_id="om_6", content="@_user_1 那要怎么改"))
    assert bridge.woken[-1]["resume"] == "s-host-1"      # 第二条续上了同一个会话


def test_chat_turn_limit_starts_new_session(bridge):
    bridge.cfg["chat"]["max_turns"] = 1
    bridge.handle(_event(bridge, message_id="om_7", content="@_user_1 第一句"))
    bridge.handle(_event(bridge, message_id="om_8", content="@_user_1 第二句"))
    assert bridge.woken[-1]["resume"] is None            # 到轮数上限 → 新会话


def test_new_topic_command_drops_session(bridge):
    bridge.handle(_event(bridge, message_id="om_9", content="@_user_1 聊聊"))
    out = bridge.handle(_event(bridge, message_id="om_10", content="@_user_1 新话题"))
    assert "新话题" in out[0]["text"]
    assert bridge.ledger.session(policy.binding_key(_event(bridge, message_id="om_9"))) is None


def test_gate_command_goes_through_serve(bridge):
    calls = []
    bridge.serve_fn = lambda path, body: (calls.append((path, body)) or (True, "200"))
    out = bridge.handle(_event(bridge, message_id="om_11", content="@_user_1 批 g2 r-abc"))
    assert calls == [("/api/runs/r-abc/gate", {"gate": "g2", "decision": "approve"})]
    assert "已提交" in out[0]["text"]


def test_ship_asks_for_confirmation_first(bridge):
    out = bridge.handle(_event(bridge, message_id="om_12", content="@_user_1 发货 r-abc"))
    assert out[0]["card"]["header"]["title"]["content"] == "确认发货？"


def test_serve_down_reports_instead_of_writing_state(bridge):
    bridge.serve_fn = lambda path, body: (False, "监工服务未启动（refused）")
    out = bridge.handle(_event(bridge, message_id="om_13", content="@_user_1 停 r-abc"))
    assert "监工服务未启动" in out[0]["text"]


# ---------------------------------------------------------------------------
# 唤醒与适配器续接


def test_wake_uses_injected_transport():
    wake = fwake.make_wake({"wake": {}}, ".", spawn=lambda b, c, r: {"adapter": "x", "pid": 0},
                           wait=lambda h: 0, read=lambda h: '{"result":"done","notes":"好的","session_id":"s9"}')
    res = wake("brief", ".", None)
    assert res["text"] == "好的" and res["session_id"] == "s9"


def test_worker_cmd_carries_resume():
    cmd = adapters.worker_cmd(resume="sess-123")
    assert "--resume" in cmd and cmd[cmd.index("--resume") + 1] == "sess-123"


def test_parse_report_keeps_session_id():
    envelope = json.dumps({"type": "result", "result": json.dumps(
        {"result": "done", "notes": "hi"}), "session_id": "s-1"})
    rep = adapters.parse_report(envelope)
    assert rep.get("session_id") == "s-1"


def test_claude_cli_declares_resume():
    assert adapters.ClaudeCli.caps["resume"] is True


# ---------------------------------------------------------------------------
# CLI 预览


def test_cli_triage_preview_is_side_effect_free():
    r = subprocess.run([sys.executable, str(REPO / "v2" / "coding_main.py"), "feishu", "triage", "批", "g2", "r-1"],
                       cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["kind"] == "gate" and data["args"]["run_id"] == "r-1"


# ---------------------------------------------------------------------------
# 加固后的行为：签名、限速、run_id 校验、预算、私聊目标


def _action(b, value, nonce="n1"):
    raw = {"chat_id": "oc_1", "chat_type": "group", "operator_id": "ou_me",
           "action": {"nonce": nonce, **value}}
    return policy.normalize(raw, "card.action.trigger", "work")


def test_card_action_requires_valid_signature(bridge):
    calls = []
    bridge.serve_fn = lambda path, body: (calls.append(path) or (True, "200"))
    out = bridge.handle(_action(bridge, {"kind": "gate", "run_id": "r-1", "gate": "g2",
                                        "decision": "approve"}))
    assert calls == [] and "签名" in out[0]["text"]


def test_signed_card_action_executes(bridge):
    calls = []
    bridge.serve_fn = lambda path, body: (calls.append(path) or (True, "200"))
    payload = {"kind": "gate", "run_id": "r-1", "gate": "g2", "decision": "approve", "nonce": "n2"}
    sig = policy.sign(bridge._secret, payload)
    out = bridge.handle(_action(bridge, {**payload, "sig": sig}, nonce="n2"))
    assert calls == ["/api/runs/r-1/gate"] and "已提交" in out[0]["text"]


def test_same_nonce_click_is_idempotent(bridge):
    calls = []
    bridge.serve_fn = lambda path, body: (calls.append(path) or (True, "200"))
    payload = {"kind": "gate", "run_id": "r-1", "gate": "g2", "decision": "approve", "nonce": "n3"}
    sig = policy.sign(bridge._secret, payload)
    for i in range(2):
        out = bridge.handle(_action(bridge, {**payload, "sig": sig}, nonce="n3"))
    assert len(calls) == 1 and "已处理" in out[0]["text"]


def test_rate_limit_drops_after_ten_per_minute(bridge):
    outs = []
    for i in range(12):
        outs.append(bridge.handle(_event(bridge, message_id=f"om_r{i}", content="@_user_1 状态")))
    assert all(o for o in outs[:10])
    assert outs[10] == [] and outs[11] == []


def test_run_id_is_validated_before_hitting_serve(bridge):
    calls = []
    bridge.serve_fn = lambda path, body: (calls.append(path) or (True, "200"))
    out = bridge.handle(_event(bridge, message_id="om_bad", content="@_user_1 批 g2 ../../etc/passwd"))
    assert calls == [] and "用法" in out[0]["text"]


def test_daily_chat_budget_stops_waking(bridge):
    bridge.cfg["chat"]["daily_budget_tokens"] = 0
    out = bridge.handle(_event(bridge, message_id="om_budget", content="@_user_1 聊聊这个"))
    assert bridge.woken == [] and "预算" in out[0]["text"]


def test_p2p_reply_targets_the_sender(bridge):
    ev = policy.normalize({"chat_type": "p2p", "sender_id": "ou_me", "message_id": "om_p1",
                           "content": "状态"}, "im.message.receive_v1", "work")
    out = bridge.handle(ev)
    assert out and out[0]["chat_id"] == "" and out[0]["user_id"] == "ou_me"


# ---------------------------------------------------------------------------
# 第二轮自审补的用例


def test_rendered_gate_card_is_signed_verifiable(bridge, tmp_path):
    _state(tmp_path, "r-sig", "closing", gates={"g2": "pending"})
    outs = bridge.tick()
    card = [o for o in outs if o["card"]][0]["card"]
    values = [a["value"] for e in card["elements"] if e["tag"] == "action"
              for a in e["actions"]]
    assert values and all(v.get("sig") for v in values)
    payload = {k: values[0].get(k) for k in ("kind", "run_id", "gate", "decision", "nonce")}
    assert policy.verify(bridge._secret, payload, values[0]["sig"])


def test_idle_timeout_starts_new_session(bridge):
    t0 = 1_000_000.0
    bridge.now = lambda: t0
    bridge.handle(_event(bridge, message_id="om_i1", content="@_user_1 第一句"))
    bridge.now = lambda: t0 + 46 * 60          # 超过 45 分钟空闲
    bridge.handle(_event(bridge, message_id="om_i2", content="@_user_1 还在吗"))
    assert bridge.woken[-1]["resume"] is None


def test_threads_get_separate_sessions(bridge):
    a = policy.normalize({"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me",
                          "message_id": "om_t1", "thread_id": "th1", "content": "@_user_1 甲",
                          "mentions": [{"id": "ou_bot"}]},
                         "im.message.receive_v1", "work")
    b = policy.normalize({"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me",
                          "message_id": "om_t2", "thread_id": "th2", "content": "@_user_1 乙",
                          "mentions": [{"id": "ou_bot"}]},
                         "im.message.receive_v1", "work")
    assert policy.binding_key(a) != policy.binding_key(b)
    bridge.handle(a)
    bridge.handle(b)
    assert bridge.woken[-1]["resume"] is None      # 另一个话题不该续上甲的会话


def test_empty_idea_is_not_written(bridge, tmp_path):
    out = bridge.handle(_event(bridge, message_id="om_e1", content="@_user_1 想法"))
    assert "空的" in out[0]["text"]
    assert not list((tmp_path / "ideas").glob("*.md")) if (tmp_path / "ideas").exists() else True


def test_ticket_brief_asks_for_six_pieces(bridge):
    bridge.handle(_event(bridge, message_id="om_e2", content="@_user_1 票 导出支持 CSV"))
    assert "六件套" in bridge.woken[-1]["brief"]


def test_group_without_chat_whitelist_is_denied(bridge):
    bridge.cfg["allow"]["chats"] = []
    assert bridge.handle(_event(bridge, message_id="om_e3", content="@_user_1 状态")) == []


def test_card_action_flat_schema_is_understood():
    """lark-cli 的真实卡片事件是扁平的：action_value 是 JSON 字符串。"""
    raw = {"chat_id": "oc_1", "operator_id": "ou_me", "message_id": "om_c",
           "event_id": "evt-c1", "token": "tk",
           "action_value": json.dumps({"kind": "gate", "run_id": "r-1", "gate": "g2",
                                       "decision": "approve", "nonce": "n-flat", "sig": "x"})}
    ev = policy.normalize(raw, "card.action.trigger", "work")
    assert ev["action"]["run_id"] == "r-1" and ev["action"]["nonce"] == "n-flat"
    assert ev["dedup_key"] == "card:n-flat"


def test_unauthorized_click_does_not_consume_the_nonce(bridge):
    calls = []
    bridge.serve_fn = lambda path, body: (calls.append(path) or (True, "200"))
    payload = {"kind": "gate", "run_id": "r-1", "gate": "g2", "decision": "approve", "nonce": "n-com"}
    sig = policy.sign(bridge._secret, payload)
    raw = {"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_stranger", "message_id": "om_x",
           "action": {**payload, "sig": sig}}
    assert bridge.handle(policy.normalize(raw, "card.action.trigger", "work")) == []

    ok_raw = {"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me", "message_id": "om_y",
              "action": {**payload, "sig": sig}}
    out = bridge.handle(policy.normalize(ok_raw, "card.action.trigger", "work"))
    assert calls == ["/api/runs/r-1/gate"] and "已提交" in out[0]["text"]


# ---------------------------------------------------------------------------
# 出站队列：先落库、退避重试、死信


@pytest.fixture
def outbox_bridge(tmp_path, monkeypatch):
    """可控时钟 + 可控发送结果：能精确量退避，不用真的等 30 秒。"""
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    cfg = fcfg.load(tmp_path)
    cfg["enabled"] = True
    cfg["allow"] = {"users": ["ou_me"], "chats": ["oc_1"], "dm": True, "require_mention": True}
    cfg["bots"] = [{"name": "work", "profile": "p-work", "chat_id": "oc_1"}]
    sent = []
    state = {"fail": True}

    def sender(out, profile=""):
        if state["fail"]:
            return False, "network down"
        sent.append({"out": out, "profile": profile})
        return True, ""

    clock = {"t": 1_000.0}
    b = fbridge.Bridge(tmp_path, cfg, sender=sender, now=lambda: clock["t"])
    b.sent = sent                        # type: ignore[attr-defined]
    b.state = state                      # type: ignore[attr-defined]
    b.clock = clock                      # type: ignore[attr-defined]
    yield b
    b.ledger.close()


def _out_msg(idem="kaimode:x", **kw):
    out = {"chat_id": "oc_1", "bot": "work", "idem": idem, "text": "hi"}
    out.update(kw)
    return out


def test_backoff_grows_and_caps():
    assert outbox.backoff(1) == 30 and outbox.backoff(2) == 60 and outbox.backoff(5) == 480
    assert outbox.backoff(50) == outbox.RETRY_CAP_S


def test_outbox_keeps_row_when_send_fails(outbox_bridge):
    b = outbox_bridge
    b.enqueue([_out_msg()])
    assert b.flush() == {"sent": 0, "retried": 1, "dead": 0}
    row = b.ledger.outbox_rows()[0]
    assert row["status"] == "pending" and row["attempts"] == 1
    assert row["next_attempt_at"] == pytest.approx(b.clock["t"] + 30)


def test_outbox_waits_for_backoff_then_sends(outbox_bridge):
    b = outbox_bridge
    b.enqueue([_out_msg()])
    b.flush()
    assert b.flush() == {"sent": 0, "retried": 0, "dead": 0}   # 没到点，不发也不记账
    b.state["fail"] = False
    b.clock["t"] += 31
    assert b.flush()["sent"] == 1
    assert b.sent[0]["profile"] == "p-work"                    # 按机器人自己的身份发
    assert b.ledger.outbox_stats().get("sent") == 1
    assert b.ledger.due(b.clock["t"]) == []


def test_outbox_buries_after_max_attempts(outbox_bridge):
    b = outbox_bridge
    b.enqueue([_out_msg()])
    for _ in range(outbox.MAX_ATTEMPTS):
        b.clock["t"] += outbox.RETRY_CAP_S + 1
        stats = b.flush()
    assert stats == {"sent": 0, "retried": 0, "dead": 1}
    assert b.ledger.outbox_stats() == {"dead": 1}
    b.clock["t"] += 10_000
    assert b.flush() == {"sent": 0, "retried": 0, "dead": 0}   # 死信不再重试


def test_revive_dead_letters(outbox_bridge):
    b = outbox_bridge
    b.enqueue([_out_msg()])
    for _ in range(outbox.MAX_ATTEMPTS):
        b.clock["t"] += outbox.RETRY_CAP_S + 1
        b.flush()
    assert b.ledger.revive() == 1
    assert b.ledger.outbox_stats() == {"pending": 1}
    assert b.ledger.outbox_rows()[0]["attempts"] == 0


def test_outbox_dedups_by_idempotency_key(outbox_bridge):
    b = outbox_bridge
    assert b.enqueue([_out_msg("kaimode:dup")]) == 1
    assert b.enqueue([_out_msg("kaimode:dup")]) == 0
    b.state["fail"] = False
    b.flush()
    assert len(b.sent) == 1


def test_outbox_row_without_target_dies_immediately(outbox_bridge):
    b = outbox_bridge
    # 桥自己就不收没落点的消息；这里模拟库里已经有的一条，验证 flush 不会让它无限重试。
    b.ledger.enqueue("kaimode:nowhere", "work", "", json.dumps({"bot": "work", "text": "hi"}))
    assert b.flush() == {"sent": 0, "retried": 0, "dead": 1}
    assert b.sent == []
    assert "没有落点" in b.ledger.outbox_rows()[0]["error"]


def test_bridge_enqueue_skips_messages_without_target(outbox_bridge):
    b = outbox_bridge
    assert b.enqueue([{"bot": "work", "idem": "kaimode:nowhere", "text": "hi"}]) == 0
    assert b.ledger.outbox_stats() == {}


def test_outbox_dm_targets_open_id(outbox_bridge):
    b = outbox_bridge
    b.state["fail"] = False
    b.enqueue([{"user_id": "ou_me", "bot": "work", "idem": "kaimode:dm", "text": "hi"}])
    assert b.flush()["sent"] == 1


def test_publish_persists_card_before_advancing_snapshot(outbox_bridge, tmp_path):
    b = outbox_bridge
    _state(tmp_path, "r-9", "done", tasks=("t1",))
    stats = b.publish()
    assert stats["enqueued"] == 1 and stats["retried"] == 1
    assert b.ledger.outbox_stats() == {"pending": 1}           # 发失败，卡片还在队列里
    assert b.publish()["enqueued"] == 0                        # 指纹已推进，不重复生成
    b.state["fail"] = False
    b.clock["t"] += 31
    assert b.flush()["sent"] == 1
    assert b.sent[0]["out"]["card"]["header"]["title"]["content"] == "完成"


def test_purge_keeps_pending_and_dead(outbox_bridge):
    b = outbox_bridge
    b.state["fail"] = False
    b.enqueue([_out_msg("a")])
    b.flush()
    b.state["fail"] = True
    b.enqueue([_out_msg("b")])
    b.flush()
    b.ledger.enqueue("dead-one", "work", "oc_1", "not-json")
    b.flush()                                                  # 坏 payload 进死信
    assert b.ledger.outbox_stats() == {"sent": 1, "pending": 1, "dead": 1}
    assert b.ledger.purge_outbox(b.clock["t"] + 1) == 1         # 只清已发成功的
    assert sorted(r["idem"] for r in b.ledger.outbox_rows()) == ["b", "dead-one"]


def test_ledger_migrates_old_outbox_schema(tmp_path):
    import sqlite3

    p = tmp_path / "old.sqlite3"
    db = sqlite3.connect(str(p))
    db.executescript(
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, idem TEXT UNIQUE,"
        " bot TEXT, chat_id TEXT, payload TEXT, status TEXT DEFAULT 'pending',"
        " attempts INTEGER DEFAULT 0, created_at REAL, sent_at REAL, error TEXT);")
    db.execute("INSERT INTO outbox(idem, payload) VALUES('old', '{}')")
    db.commit()
    db.close()

    led = fledger.Ledger(p)
    try:
        due = led.due(1e12)
        assert len(due) == 1 and due[0]["next_attempt_at"] == 0
    finally:
        led.close()


def test_outbox_buries_unparseable_payload(outbox_bridge):
    b = outbox_bridge
    b.ledger.enqueue("kaimode:bad", "work", "oc_1", "not-json")
    assert b.flush() == {"sent": 0, "retried": 0, "dead": 1}


def test_wake_over_budget_starts_fresh_session(tmp_path, monkeypatch):
    monkeypatch.setenv("KAI_AGENT_DATA_ROOT", str(tmp_path / "data"))
    cfg = fcfg.load(tmp_path)
    cfg["enabled"] = True
    cfg["allow"] = {"users": ["ou_me"], "chats": ["oc_1"], "dm": True, "require_mention": True}

    def wake(brief, cwd, resume=None):
        return {"text": "ok", "session_id": resume or "s-1", "tokens": 10, "over_budget": True}

    b = fbridge.Bridge(tmp_path, cfg, wake_fn=wake)
    try:
        ev = _event(b, message_id="om_ob", content="@_user_1 聊聊")
        assert b.handle(ev)[0]["text"] == "ok"
        assert b.ledger.session(policy.binding_key(ev)) is None   # 烧穿预算就换会话
    finally:
        b.ledger.close()


def test_concurrent_flush_sends_each_row_once(outbox_bridge):
    """两个 consumer 线程 + 主循环会同时来要活：同一行只能发一次。"""
    import threading

    b = outbox_bridge
    b.state["fail"] = False
    for i in range(10):
        b.enqueue([_out_msg(f"k{i}")])
    threads = [threading.Thread(target=b.flush) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(b.sent) == 10
    assert sorted(r["out"]["idem"] for r in b.sent) == [f"k{i}" for i in range(10)]


def test_publish_defers_until_chat_id_configured(outbox_bridge, tmp_path):
    """没配落点时不推进指纹：配上之后同一张卡还能补发，不被配置缺项吞掉。"""
    b = outbox_bridge
    b.state["fail"] = False
    b.cfg["bots"] = [{"name": "work", "profile": "p-work", "chat_id": ""}]
    _state(tmp_path, "r-7", "done", tasks=("t1",))
    assert b.publish()["enqueued"] == 0
    assert b.ledger.outbox_stats() == {}
    b.cfg["bots"][0]["chat_id"] = "oc_1"
    stats = b.publish()
    assert stats["enqueued"] == 1 and stats["sent"] == 1


def test_retry_policy_constants_are_pinned():
    """规格是「30s 起步、封顶 15 分钟、共 8 次」，别拿实现常量自证。"""
    assert (outbox.RETRY_BASE_S, outbox.RETRY_CAP_S, outbox.MAX_ATTEMPTS) == (30, 900, 8)


def test_flush_survives_deliver_exception(outbox_bridge):
    """lark-cli 超时抛的是异常，不是 returncode：不能让它穿出去，也不能不记账。"""
    b = outbox_bridge

    def boom(out, profile=""):
        raise TimeoutError("lark-cli timed out")

    b.deliver = boom
    b.enqueue([_out_msg("t1")])
    assert b.flush() == {"sent": 0, "retried": 1, "dead": 0}
    row = b.ledger.outbox_rows()[0]
    assert row["status"] == "pending" and row["attempts"] == 1
    assert "Timeout" in row["error"] and row["next_attempt_at"] > b.clock["t"]


def test_publish_does_not_advance_snapshot_when_enqueue_fails(outbox_bridge, tmp_path):
    b = outbox_bridge
    _state(tmp_path, "r-8", "done")

    def boom(outs):
        raise RuntimeError("disk full")

    b.enqueue = boom
    with pytest.raises(RuntimeError):
        b.publish()
    assert notify.load_snapshots(b.dir / "snapshots.json") == {}


def test_snapshot_write_is_atomic(tmp_path):
    p = tmp_path / "snaps.json"
    notify.save_snapshots(p, {"r-1": "abc"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"r-1": "abc"}
    assert not (tmp_path / "snaps.json.tmp").exists()


def test_same_message_from_two_bots_each_gets_a_reply(bridge):
    """多个机器人同在一个群被同时 @：同一条 message_id 各自都要回。"""
    raw = {"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me",
           "message_id": "om_multi", "content": "@_user_1 状态", "mentions": [{"id": "ou_bot"}]}
    a = bridge.handle(policy.normalize(raw, "im.message.receive_v1", "botA"))
    b = bridge.handle(policy.normalize(raw, "im.message.receive_v1", "botB"))
    assert a and b
    assert a[0]["idem"] != b[0]["idem"]


def test_duplicate_click_receipt_has_its_own_idempotency_key(bridge):
    bridge.serve_fn = lambda path, body: (True, "200")
    payload = {"kind": "gate", "run_id": "r-1", "gate": "g2", "decision": "approve", "nonce": "n-dup"}
    sig = policy.sign(bridge._secret, payload)
    raw = {"chat_id": "oc_1", "chat_type": "group", "sender_id": "ou_me", "message_id": "om_d1",
           "action": {**payload, "sig": sig}}
    first = bridge.handle(policy.normalize(raw, "card.action.trigger", "work"))[0]
    second = bridge.handle(policy.normalize({**raw, "message_id": "om_d2"},
                                            "card.action.trigger", "work"))[0]
    assert "已提交" in first["text"] and second["text"] == "已处理。"
    assert first["idem"] != second["idem"]
    assert bridge.enqueue([first, second]) == 2          # 回执不会被队列吞掉


def test_adhoc_idempotency_key_is_written_into_payload(outbox_bridge):
    b = outbox_bridge
    b.state["fail"] = False
    b.enqueue([{"chat_id": "oc_1", "bot": "work", "text": "no idem here"}])
    b.flush()
    assert b.sent[0]["out"]["idem"].startswith("adhoc:")


def test_runner_refuses_when_another_bridge_is_alive(tmp_path, monkeypatch):
    from v2.coding.feishu import consumer as fconsumer, runner as frunner

    pid_path = tmp_path / ".coding" / "feishu" / "bridge.pid"
    fconsumer.write_pid(pid_path, 999_999)
    monkeypatch.setattr(frunner.consumer, "pid_alive", lambda pid: True)
    assert frunner._acquire(tmp_path)[0] is None

    monkeypatch.setattr(frunner.consumer, "pid_alive", lambda pid: False)
    path, other = frunner._acquire(tmp_path)
    assert path is not None and other == 0
    assert path.read_text(encoding="utf-8").strip() == str(os.getpid())
