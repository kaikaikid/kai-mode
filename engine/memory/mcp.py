"""记忆 MCP：stdio JSON-RPC 薄适配器，转发到本机 daemon（ADR-0037 D6）。

daemon 是唯一写者；MCP 进程不碰账本，只把工具调用翻译成 `POST /v1/memory/*`，
因此 MCP 客户端和 HTTP 客户端看到同一套权限与审计。

启动：

    python engine/bin/kai memory mcp --url http://127.0.0.1:8788 --token <token>
    # 或 KAI_MEMORY_URL / KAI_MEMORY_TOKEN 环境变量

传输：stdio，一行一条 JSON-RPC 2.0 消息（MCP 的 stdio 约定）。
工具：memory_retrieve / propose / commit / rollback / veto / lineage / dream / export / admin。
只读与 propose 任何 agent 可用；治理工具由 daemon 按 token 角色把关（只认 archivist）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Iterable, TextIO

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kai-memory-mcp"
SERVER_VERSION = "1.0.0"
DEFAULT_URL = "http://127.0.0.1:8788"

# 工具名 → HTTP 路径尾段
TOOL_OPS = {
    "memory_retrieve": "retrieve",
    "memory_propose": "propose",
    "memory_commit": "commit",
    "memory_rollback": "rollback",
    "memory_veto": "veto",
    "memory_lineage": "lineage",
    "memory_dream": "dream",
    "memory_export": "export",
    "memory_admin": "admin",
}


def _schema(properties: dict[str, Any], required: Iterable[str] = ()) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "object", "properties": properties,
                           "additionalProperties": True}
    req = list(required)
    if req:
        out["required"] = req
    return out


EVIDENCE = {"type": "array", "items": {"type": "string"},
            "description": "可核验的证据指针（文件:行号、URL、命令输出）；自述类不算"}
COMMON_WRITE = {
    "namespace": {"type": "string",
                  "description": "user / shared / coordinator-private / project:<id> / task:<id>"},
    "kind": {"type": "string",
             "enum": ["task_fact", "failure_lesson", "preference", "skill", "relationship"]},
    "statement": {"type": "string"},
    "evidence_refs": EVIDENCE,
    "subject": {"type": "string"},
    "source": {"type": "string"},
    "session_id": {"type": "string"},
    "before": {"type": "string"},
    "after": {"type": "string"},
    "conflicts_with": {"type": "array", "items": {"type": "string"}},
    "layer": {"type": "string", "description": "元数据，如 ego"},
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "memory_retrieve",
        "description": "按 namespace（可加 kind/关键词）检索 active 记忆；top-k 与 token 上限。",
        "inputSchema": _schema({
            "namespace": COMMON_WRITE["namespace"],
            "kind": COMMON_WRITE["kind"],
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 5},
            "max_tokens": {"type": "integer", "default": 2000},
        }, ["namespace"]),
    },
    {
        "name": "memory_propose",
        "description": "任何 agent 提候选（不生效）；必须有可核验证据。",
        "inputSchema": _schema(COMMON_WRITE, ["namespace", "kind", "statement"]),
    },
    {
        "name": "memory_commit",
        "description": "archivist 把候选转正或直接写入；可 supersedes 旧条目。",
        "inputSchema": _schema({
            "proposal_id": {"type": "string", "description": "候选 memory_id"},
            **COMMON_WRITE,
            "supersedes": {"type": "string"},
        }),
    },
    {
        "name": "memory_rollback",
        "description": "archivist 追加反向记录；原记录保留，必须写 reason。",
        "inputSchema": _schema({
            "target": {"type": "string"},
            "reason": {"type": "string"},
            "evidence_refs": EVIDENCE,
        }, ["target", "reason"]),
    },
    {
        "name": "memory_veto",
        "description": "archivist 标 tombstone；不删除，必须写 reason。",
        "inputSchema": _schema({
            "target": {"type": "string"},
            "reason": {"type": "string"},
            "evidence_refs": EVIDENCE,
        }, ["target", "reason"]),
    },
    {
        "name": "memory_lineage",
        "description": "列出一条记忆的全部事件（审计）。",
        "inputSchema": _schema({
            "memory_id": {"type": "string"},
        }, ["memory_id"]),
    },
    {
        "name": "memory_dream",
        "description": "archivist 后台整理入口：重建索引、统计状态、报告冲突与审计问题。",
        "inputSchema": _schema({}),
    },
    {
        "name": "memory_export",
        "description": "archivist 导出账本（当前视图或全部事件）。",
        "inputSchema": _schema({
            "events": {"type": "boolean", "default": False},
        }),
    },
    {
        "name": "memory_admin",
        "description": "archivist 运维：check / stats / rebuild_index。",
        "inputSchema": _schema({
            "action": {"type": "string",
                       "enum": ["check", "stats", "rebuild_index"],
                       "default": "stats"},
        }),
    },
]


class DaemonClient:
    def __init__(self, url: str, token: str | None, timeout: float = 10.0):
        self.url = (url or DEFAULT_URL).rstrip("/")
        self.token = token
        self.timeout = timeout
        # 本机回环不走系统代理：代理环境变量会把 127.0.0.1 也劫走
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, op: str, args: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        body = json.dumps(args or {}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/v1/memory/{op}", data=body, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8",
                     "Authorization": f"Bearer {self.token or ''}"})
        try:
            with self._opener.open(request, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8") or "{}"
                return json.loads(raw), None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            message = raw
            try:
                payload = json.loads(raw)
                message = payload.get("error", {}).get("message") or raw
            except ValueError:
                pass
            return None, f"daemon 返回 {exc.code}：{message}"
        except urllib.error.URLError as exc:
            return None, (f"连不上本机记忆 daemon {self.url}：{exc.reason}；"
                          "先 `kai memory serve` 起服务")
        except (OSError, ValueError) as exc:
            return None, f"调用 {self.url} 失败：{exc}"


def _jsonrpc_error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": code, "message": message}}


def _content(payload: Any, is_error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False, default=str)
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class McpServer:
    """无状态 JSON-RPC 处理器；`run()` 读 stdin 写回 stdout。"""

    def __init__(self, client: DaemonClient):
        self.client = client

    def handle(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return _jsonrpc_error(None, -32600, "请求必须是 JSON 对象")
        msg_id = message.get("id")
        method = message.get("method")
        is_notification = "id" not in message
        if not isinstance(method, str) or not method:
            if is_notification:
                return None
            return _jsonrpc_error(msg_id, -32600, "缺少 method")
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return _jsonrpc_error(msg_id, -32602, "params 必须是对象")

        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
            return None if is_notification else {"jsonrpc": "2.0", "id": msg_id,
                                                 "result": result}
        if method in ("notifications/initialized", "notifications/cancelled", "exit"):
            return None
        if method == "shutdown":
            return None if is_notification else {"jsonrpc": "2.0", "id": msg_id,
                                                 "result": None}
        if method == "ping":
            return None if is_notification else {"jsonrpc": "2.0", "id": msg_id,
                                                 "result": {}}
        if method == "tools/list":
            return None if is_notification else {"jsonrpc": "2.0", "id": msg_id,
                                                 "result": {"tools": TOOLS}}
        if method == "tools/call":
            return None if is_notification else self._call_tool(msg_id, params)
        return None if is_notification else _jsonrpc_error(
            msg_id, -32601, f"不认识的方法：{method}")

    def _call_tool(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "")
        op = TOOL_OPS.get(name)
        if op is None:
            return _jsonrpc_error(msg_id, -32602, f"未知工具：{name!r}")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _jsonrpc_error(msg_id, -32602, "arguments 必须是对象")
        if not self.client.token:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "result": _content(
                        "缺少 token：设置 KAI_MEMORY_TOKEN 或 --token；"
                        "`kai memory key new --agent <名字>` 可生成", is_error=True)}
        payload, error = self.client.call(op, arguments)
        if error is not None:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "result": _content(error, is_error=True)}
        return {"jsonrpc": "2.0", "id": msg_id, "result": _content(payload)}

    def run(self, stdin: TextIO, stdout: TextIO) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError as exc:
                response: dict[str, Any] | None = _jsonrpc_error(
                    None, -32700, f"JSON 解析失败：{exc}")
            else:
                response = self.handle(message)
            if response is None:
                continue
            try:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()
            except (BrokenPipeError, OSError):
                return


def build_client(args: argparse.Namespace) -> DaemonClient:
    url = args.url or os.environ.get("KAI_MEMORY_URL") or DEFAULT_URL
    token = args.token if args.token is not None else os.environ.get("KAI_MEMORY_TOKEN")
    return DaemonClient(url, token, timeout=float(args.timeout))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kai memory mcp",
        description="记忆 MCP：stdio JSON-RPC → 本机 daemon")
    p.add_argument("--url", default=None,
                   help=f"daemon 地址（默认 $KAI_MEMORY_URL 或 {DEFAULT_URL}）")
    p.add_argument("--token", default=None,
                   help="agent token（默认 $KAI_MEMORY_TOKEN；治理动作需 archivist token）")
    p.add_argument("--timeout", default=10.0, type=float, help="单次 HTTP 超时秒数")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    server = McpServer(build_client(args))
    try:
        server.run(sys.stdin, sys.stdout)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
