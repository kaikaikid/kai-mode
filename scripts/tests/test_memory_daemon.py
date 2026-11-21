"""记忆 daemon + MCP 测例（Issue #29；ADR-0037 D6/D7）。

断的是可观测行为：
- token：每 agent 一把、文件只存 sha256、`key new/rotate/remove` 可用；
- daemon：只监听回环、单实例锁、`/health` 公开、其余路由必须 token；
- 权限：任何角色可 retrieve/propose；commit/rollback/veto/dream/export/admin 只认 shaman；
- HTTP 回读：propose → shaman commit → retrieve/lineage；
- MCP：stdio 握手、tools/list、工具调用转发到 daemon、无 token 报错。

所有测例用临时库/临时 token 表/临时端口，不碰真实数据根。
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from memory.daemon import (  # noqa: E402
    AlreadyRunning,
    InstanceLock,
    MemoryDaemon,
    ensure_loopback,
)
from memory.ledger import MemoryError  # noqa: E402
from memory.mcp import TOOL_OPS  # noqa: E402
from memory.tokens import TokenError, TokenStore, hash_token  # noqa: E402

ENTRY = ENGINE_DIR / "memory" / "_entry.py"
MCP = ENGINE_DIR / "memory" / "mcp.py"


# ── fixtures ────────────────────────────────────────────────────────────────
class Env:
    def __init__(self, tmp_path: Path):
        self.db = tmp_path / "ledger.db"
        self.tokens = tmp_path / "tokens.json"
        self.store = TokenStore(self.tokens)
        self.arch = self.store.create("shaman", "shaman")
        self.eng = self.store.create("engineer", "engineer")


@pytest.fixture()
def env(tmp_path) -> Env:
    return Env(tmp_path)


@pytest.fixture()
def daemon(env):
    svc = MemoryDaemon(env.db, env.tokens, port=0)
    svc.start_background()
    try:
        yield svc
    finally:
        svc.stop()


def call(base: str, path: str, token: str | None = None,
         body: dict | None = None, method: str = "POST"):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=data, headers=headers,
                                     method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, json.loads(raw)


def run_kai(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ENTRY), "memory", *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(REPO))


# ── token 表 ────────────────────────────────────────────────────────────────
def test_token_file_stores_only_hashes_and_is_private(tmp_path):
    path = tmp_path / "tokens.json"
    store = TokenStore(path)
    token = store.create("engineer", "engineer")
    assert token.startswith("kmt_")
    raw = path.read_text(encoding="utf-8")
    assert token not in raw, "明文 token 不许落盘"
    assert hash_token(token) in raw
    data = json.loads(raw)
    assert data["version"] == 1
    assert data["tokens"]["engineer"]["role"] == "engineer"
    assert store.lookup(token) == {"agent": "engineer", "role": "engineer"}
    assert store.lookup("kmt_wrong") is None
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_token_create_rotate_remove_lifecycle(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    first = store.create("shaman", "shaman")
    with pytest.raises(TokenError, match="已有 token"):
        store.create("shaman", "shaman")
    with pytest.raises(TokenError, match="agent 名不合规"):
        store.create("-bad", "shaman")

    second = store.rotate("shaman")
    assert second != first
    assert store.lookup(first) is None, "轮换后旧 token 立即失效"
    assert store.lookup(second)["role"] == "shaman"

    store.remove("shaman")
    assert store.lookup(second) is None
    with pytest.raises(TokenError, match="没有 agent"):
        store.remove("shaman")
    assert store.list() == []


def test_key_cli_new_rotate_remove_and_list(tmp_path):
    tokens = str(tmp_path / "tokens.json")
    p = run_kai("--tokens", tokens, "key", "new", "--agent", "reviewer", "--json")
    assert p.returncode == 0, p.stderr
    created = json.loads(p.stdout)
    assert created["agent"] == "reviewer" and created["role"] == "reviewer"
    first = created["token"]
    assert first not in Path(tokens).read_text(encoding="utf-8")

    p = run_kai("--tokens", tokens, "key", "new", "--agent", "reviewer")
    assert p.returncode == 2 and "已有 token" in p.stderr

    p = run_kai("--tokens", tokens, "key", "rotate", "--agent", "reviewer", "--json")
    assert p.returncode == 0, p.stderr
    second = json.loads(p.stdout)["token"]
    assert second != first
    assert TokenStore(tokens).lookup(first) is None

    p = run_kai("--tokens", tokens, "key", "list", "--json")
    listed = json.loads(p.stdout)
    assert len(listed) == 1
    assert listed[0]["agent"] == "reviewer" and listed[0]["role"] == "reviewer"
    assert "hash" not in listed[0] and "token" not in listed[0]

    p = run_kai("--tokens", tokens, "key", "remove", "--agent", "reviewer", "--json")
    assert p.returncode == 0, p.stderr
    assert TokenStore(tokens).lookup(second) is None


# ── daemon 基础 ─────────────────────────────────────────────────────────────
def test_only_loopback_hosts_and_single_instance(env):
    with pytest.raises(MemoryError, match="回环"):
        MemoryDaemon(env.db, env.tokens, host="0.0.0.0")
    with pytest.raises(MemoryError, match="回环"):
        ensure_loopback("example.com")

    first = MemoryDaemon(env.db, env.tokens, port=0)
    first.bind()
    try:
        second = MemoryDaemon(env.db, env.tokens, port=0)
        with pytest.raises(AlreadyRunning):
            second.bind()
    finally:
        first.close()

    third = MemoryDaemon(env.db, env.tokens, port=0)
    third.bind()
    third.close()

    lock = InstanceLock(env.db.with_name("other.lock"))
    lock.acquire()
    try:
        with pytest.raises(AlreadyRunning):
            InstanceLock(env.db.with_name("other.lock")).acquire()
    finally:
        lock.release()


def test_health_is_public_but_routes_require_token(daemon):
    base = daemon.url
    status, payload = call(base, "/health", method="GET")
    assert status == 200
    assert payload["ok"] is True
    assert payload["service"] == "kai-memory-daemon"
    assert payload["engine"] == "fts5"
    assert "events" in payload

    status, payload = call(base, "/v1/memory/retrieve", body={"namespace": "shared"})
    assert status == 401
    assert payload["error"]["type"] == "unauthorized"

    status, _ = call(base, "/v1/memory/retrieve", token="not-a-valid-token",
                     body={"namespace": "shared"})
    assert status == 401

    status, _ = call(base, "/v1/memory/nope", method="GET")
    assert status == 404


def test_http_propose_commit_retrieve_lineage_and_governance(daemon, env):
    base = daemon.url

    status, payload = call(base, "/v1/memory/propose", token=env.eng, body={
        "namespace": "project:demo", "kind": "failure_lesson",
        "statement": "并发写要 BEGIN IMMEDIATE", "evidence_refs": ["docs/x.md:9"]})
    assert status == 200, payload
    assert payload["created"] is True
    proposal = payload["memory"]
    assert proposal["status"] == "proposed"
    assert proposal["actor_role"] == "engineer"

    status, payload = call(base, "/v1/memory/retrieve", token=env.eng, body={
        "namespace": "project:demo", "query": "并发"})
    assert status == 200 and payload["count"] == 0, "proposed 不注入"

    status, payload = call(base, "/v1/memory/commit", token=env.eng,
                           body={"proposal_id": proposal["memory_id"]})
    assert status == 403
    assert "shaman" in payload["error"]["message"]

    status, payload = call(base, "/v1/memory/commit", token=env.arch,
                           body={"proposal_id": proposal["memory_id"]})
    assert status == 200, payload
    committed = payload["memory"]
    assert committed["status"] == "active"
    assert committed["committed_by"] == "shaman"

    status, payload = call(base, "/v1/memory/retrieve", token=env.eng, body={
        "namespace": "project:demo", "query": "并发"})
    assert status == 200
    assert [r["memory_id"] for r in payload["items"]] == [proposal["memory_id"]]

    status, payload = call(base, "/v1/memory/lineage", token=env.eng,
                           body={"memory_id": proposal["memory_id"]})
    assert status == 200
    assert [e["event_type"] for e in payload["events"]] == ["propose", "commit"]

    # 治理动作：engineer 全拒
    for op, body in (
        ("rollback", {"target": proposal["memory_id"], "reason": "x"}),
        ("veto", {"target": proposal["memory_id"], "reason": "x"}),
        ("dream", {}),
        ("export", {}),
        ("admin", {"action": "stats"}),
    ):
        status, payload = call(base, f"/v1/memory/{op}", token=env.eng, body=body)
        assert status == 403, (op, payload)
        assert "shaman" in payload["error"]["message"]

    status, payload = call(base, "/v1/memory/dream", token=env.arch, body={})
    assert status == 200, payload
    assert payload["status"]["active"] == 1
    assert payload["problems"] == []

    status, payload = call(base, "/v1/memory/export", token=env.arch,
                           body={"events": True})
    assert status == 200 and payload["count"] == 2

    status, payload = call(base, "/v1/memory/admin", token=env.arch,
                           body={"action": "check"})
    assert status == 200 and payload["ok"] is True
    status, payload = call(base, "/v1/memory/admin", token=env.arch,
                           body={"action": "stats"})
    assert status == 200 and payload["events"] == 2
    status, payload = call(base, "/v1/memory/admin", token=env.arch,
                           body={"action": "rebuild_index"})
    assert status == 200 and payload["reindexed"] == 1

    status, payload = call(base, "/v1/memory/rollback", token=env.arch,
                           body={"target": proposal["memory_id"],
                                 "reason": "证据不支持"})
    assert status == 200 and payload["memory"]["status"] == "rolled_back"
    status, payload = call(base, "/v1/memory/retrieve", token=env.eng,
                           body={"namespace": "project:demo"})
    assert payload["count"] == 0


def test_daemon_restart_keeps_committed_events(env):
    first = MemoryDaemon(env.db, env.tokens, port=0)
    first.start_background()
    try:
        base = first.url
        status, payload = call(base, "/v1/memory/propose", token=env.eng, body={
            "namespace": "shared", "kind": "task_fact",
            "statement": "重启不丢", "evidence_refs": ["tests:x:1"]})
        assert status == 200
        proposal_id = payload["memory"]["memory_id"]
        status, payload = call(base, "/v1/memory/commit", token=env.arch,
                               body={"proposal_id": proposal_id})
        assert status == 200 and payload["memory"]["status"] == "active"
    finally:
        first.stop()

    second = MemoryDaemon(env.db, env.tokens, port=0)
    second.start_background()
    try:
        status, payload = call(second.url, "/v1/memory/retrieve", token=env.eng,
                               body={"namespace": "shared"})
        assert status == 200
        assert [r["memory_id"] for r in payload["items"]] == [proposal_id]
        status, payload = call(second.url, "/health", method="GET")
        assert payload["events"] == 2 and payload["active"] == 1
    finally:
        second.stop()


def test_http_write_requires_evidence_and_token_role_beats_body(daemon, env):
    base = daemon.url
    status, payload = call(base, "/v1/memory/propose", token=env.eng, body={
        "namespace": "shared", "kind": "task_fact", "statement": "无证据"})
    assert status == 400
    assert "证据" in payload["error"]["message"]

    status, payload = call(base, "/v1/memory/propose", token=env.eng, body={
        "namespace": "shared", "kind": "task_fact", "statement": "冒名",
        "evidence_refs": ["tests:x:1"], "actor_role": "shaman"})
    assert status == 200
    mid = payload["memory"]["memory_id"]
    status, payload = call(base, "/v1/memory/lineage", token=env.arch,
                           body={"memory_id": mid})
    assert payload["events"][0]["actor_role"] == "engineer", "角色由 token 决定，不看请求体"

    status, payload = call(base, "/v1/memory/admin", token=env.arch,
                           body={"action": "nonsense"})
    assert status == 400


# ── MCP stdio ───────────────────────────────────────────────────────────────
class McpSession:
    def __init__(self, url: str, token: str | None):
        child_env = dict(os.environ)
        child_env.pop("KAI_MEMORY_TOKEN", None)
        child_env.pop("KAI_MEMORY_URL", None)
        child_env["PYTHONIOENCODING"] = "utf-8"
        if token:
            child_env["KAI_MEMORY_TOKEN"] = token
        self.proc = subprocess.Popen(
            [sys.executable, str(MCP), "--url", url],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            env=child_env)
        self._id = 0

    def send(self, message: dict) -> None:
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        self.send(payload)
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.poll() is not None else ""
            pytest.fail(f"MCP 没有响应 {method}；stderr={stderr}")
        return json.loads(line)

    def close(self) -> None:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)


def test_mcp_handshake_tools_list_and_governance(daemon, env):
    base = daemon.url
    status, payload = call(base, "/v1/memory/propose", token=env.eng, body={
        "namespace": "shared", "kind": "task_fact",
        "statement": "MCP 待转正", "evidence_refs": ["tests:x:1"]})
    assert status == 200, payload
    proposal_id = payload["memory"]["memory_id"]

    session = McpSession(base, env.eng)
    try:
        init = session.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}})
        assert init["result"]["protocolVersion"] == "2024-11-05"
        assert init["result"]["serverInfo"]["name"] == "kai-memory-mcp"
        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        listed = session.request("tools/list")
        names = [t["name"] for t in listed["result"]["tools"]]
        assert names == list(TOOL_OPS), "MCP 工具与 HTTP 面对齐"

        result = session.request("tools/call", {
            "name": "memory_retrieve",
            "arguments": {"namespace": "shared"}})
        assert result["result"]["isError"] is False
        assert json.loads(result["result"]["content"][0]["text"])["count"] == 0

        result = session.request("tools/call", {
            "name": "memory_commit", "arguments": {"proposal_id": proposal_id}})
        assert result["result"]["isError"] is True
        assert "shaman" in result["result"]["content"][0]["text"]

        result = session.request("tools/call", {
            "name": "memory_nope", "arguments": {}})
        assert result["error"]["code"] == -32602

        session.proc.stdin.write("not json\n")
        session.proc.stdin.flush()
        broken = json.loads(session.proc.stdout.readline())
        assert broken["error"]["code"] == -32700
    finally:
        session.close()

    session = McpSession(base, env.arch)
    try:
        result = session.request("tools/call", {
            "name": "memory_commit", "arguments": {"proposal_id": proposal_id}})
        assert result["result"]["isError"] is False
        committed = json.loads(result["result"]["content"][0]["text"])
        assert committed["memory"]["status"] == "active"

        result = session.request("tools/call", {
            "name": "memory_admin", "arguments": {"action": "stats"}})
        assert result["result"]["isError"] is False
    finally:
        session.close()


def test_mcp_without_token_reports_error_and_missing_daemon(daemon, env):
    session = McpSession(daemon.url, None)
    try:
        session.request("initialize", {})
        result = session.request("tools/call", {
            "name": "memory_retrieve", "arguments": {"namespace": "shared"}})
        assert result["result"]["isError"] is True
        assert "token" in result["result"]["content"][0]["text"]
    finally:
        session.close()

    session = McpSession("http://127.0.0.1:9", env.eng)
    try:
        session.request("initialize", {})
        result = session.request("tools/call", {
            "name": "memory_retrieve", "arguments": {"namespace": "shared"}})
        assert result["result"]["isError"] is True
        assert "daemon" in result["result"]["content"][0]["text"]
    finally:
        session.close()
