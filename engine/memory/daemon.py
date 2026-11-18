"""记忆 daemon：本机回环 HTTP JSON 服务（ADR-0037 D6/D7）。

- 只监听回环地址（默认 `127.0.0.1:8788`），单实例锁；
- 鉴权：`Authorization: Bearer <token>`，token 表见 `tokens.py`；
- 治理动作 commit/rollback/veto/dream/export/admin 只认 `archivist` token；
- daemon 是唯一写者：请求进一把进程内锁，写操作再由账本 `BEGIN IMMEDIATE` 串行化；
- 只用标准库（`http.server` + `threading`），不引入第三方依赖。

HTTP 面（除 `/health` 外都要 token）：

    GET  /health
    POST /v1/memory/retrieve   {namespace, kind?, query?, top_k?, max_tokens?}
    POST /v1/memory/propose    {namespace, kind, statement, evidence_refs, ...}
    POST /v1/memory/commit     {proposal_id} 或完整字段；可带 supersedes
    POST /v1/memory/rollback   {target, reason, evidence_refs?}
    POST /v1/memory/veto       {target, reason, evidence_refs?}
    POST /v1/memory/lineage    {memory_id}
    POST /v1/memory/dream      {}                      archivist
    POST /v1/memory/export     {events?}               archivist
    POST /v1/memory/admin      {action?}               archivist
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .engine import build_engine
from .ledger import (
    ACTIVE_STATUS,
    ARCHIVIST,
    ConflictError,
    Ledger,
    MemoryError,
    NotFound,
    PermissionDenied,
)
from .tokens import TokenError, TokenStore

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
DEFAULT_DB_NAME = "ledger.db"
DEFAULT_TOKENS_NAME = "tokens.json"
MAX_BODY = 1 << 20  # 1 MiB

GOVERNANCE_OPS = frozenset({"commit", "rollback", "veto", "dream", "export", "admin"})
ALL_OPS = frozenset(GOVERNANCE_OPS | {"retrieve", "propose", "lineage"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


class AlreadyRunning(MemoryError):
    """同一账本已有 daemon 在跑（单实例锁没拿到）。"""


class InstanceLock:
    """跨进程单实例锁：POSIX `flock`，Windows `msvcrt.locking`；进程内另有一张表。"""

    _held: set[str] = set()
    _guard = threading.Lock()

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._fh = None

    def acquire(self) -> None:
        key = str(self.path.resolve())
        with InstanceLock._guard:
            if key in InstanceLock._held:
                raise AlreadyRunning(f"已有 daemon 持有锁：{self.path}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(self.path, "a+b")
            try:
                self._lock_fh(fh)
            except OSError as exc:
                fh.close()
                raise AlreadyRunning(
                    f"已有 daemon 持有锁：{self.path}（{exc}）") from exc
            fh.seek(0)
            fh.truncate()
            fh.write((json.dumps({"pid": os.getpid()}) + "\n").encode("utf-8"))
            fh.flush()
            InstanceLock._held.add(key)
            self._fh = fh

    @staticmethod
    def _lock_fh(fh) -> None:
        if os.name == "nt":
            import msvcrt
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock_fh(fh) -> None:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        with InstanceLock._guard:
            try:
                InstanceLock._held.discard(str(self.path.resolve()))
            finally:
                try:
                    self._unlock_fh(fh)
                except OSError:
                    pass
                fh.close()

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def ensure_loopback(host: str) -> str:
    host = str(host or "").strip()
    if host not in LOOPBACK_HOSTS:
        raise MemoryError(
            f"只允许监听回环地址（127.0.0.1/localhost），收到 {host!r}；"
            "记忆 daemon 不监听公网（ADR-0037 D6）")
    return host


def _evidence(args: dict[str, Any]) -> list[str]:
    """`evidence_refs` 是正式字段；`evidence` 作 CLI 风格的别名。"""
    return _as_list(args.get("evidence_refs") or args.get("evidence"))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(x) for x in value if str(x).strip()]


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("status") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


class MemoryService:
    """HTTP 与 MCP 共用的操作面；把 token 身份落成账本的 `actor_role`。"""

    def __init__(self, db: str | Path, tokens: TokenStore | str | Path,
                 engine: str = "fts5"):
        self.db = Path(db)
        self.tokens = tokens if isinstance(tokens, TokenStore) else TokenStore(tokens)
        self.engine_name = engine or "fts5"
        self._lock = threading.RLock()
        self._inflight = 0
        self._inflight_guard = threading.Lock()

    def _open(self) -> Ledger:
        return Ledger(self.db, engine=build_engine(self.engine_name, self.db))

    def authenticate(self, token: str | None) -> dict[str, Any] | None:
        return self.tokens.lookup(token)

    def call(self, op: str, args: dict[str, Any] | None,
             identity: dict[str, Any]) -> dict[str, Any]:
        op = str(op or "").strip()
        if op not in ALL_OPS:
            raise NotFound(f"未知记忆操作：{op!r}")
        role = str((identity or {}).get("role") or "")
        if op in GOVERNANCE_OPS and role != ARCHIVIST:
            raise PermissionDenied(
                f"拒绝 {op}：治理动作只认 archivist token，当前角色 `{role}`"
                "（ADR-0037 D4/D6）")
        body = dict(args or {})
        with self._inflight_guard:
            self._inflight += 1
        try:
            with self._lock:
                with self._open() as ledger:
                    return self._dispatch(ledger, op, body, role)
        finally:
            with self._inflight_guard:
                self._inflight -= 1

    def _dispatch(self, ledger: Ledger, op: str, args: dict[str, Any],
                  role: str) -> dict[str, Any]:
        if op == "retrieve":
            rows = ledger.retrieve(
                namespace=str(args.get("namespace") or ""),
                kind=args.get("kind") or None,
                query=args.get("query") or None,
                top_k=int(args.get("top_k") or 5),
                max_tokens=int(args.get("max_tokens") or 2000),
            )
            return {"count": len(rows), "items": rows}

        if op == "propose":
            row = ledger.propose(
                actor_role=role,
                namespace=str(args.get("namespace") or ""),
                kind=str(args.get("kind") or ""),
                statement=str(args.get("statement") or ""),
                evidence_refs=_evidence(args),
                subject=args.get("subject") or None,
                source=args.get("source") or None,
                session_id=args.get("session_id") or None,
                before=str(args.get("before") or ""),
                after=str(args.get("after") or ""),
                conflicts_with=_as_list(args.get("conflicts_with")),
                layer=args.get("layer") or None,
            )
            return {"created": bool(row.get("created")), "memory": row}

        if op == "commit":
            row = ledger.commit(
                actor_role=role,
                proposal_id=args.get("proposal_id") or args.get("memory_id") or None,
                namespace=args.get("namespace") or None,
                kind=args.get("kind") or None,
                statement=args.get("statement") or None,
                evidence_refs=_evidence(args) or None,
                subject=args.get("subject") or None,
                source=args.get("source") or None,
                session_id=args.get("session_id") or None,
                before=str(args.get("before") or ""),
                after=str(args.get("after") or ""),
                conflicts_with=_as_list(args.get("conflicts_with")),
                layer=args.get("layer") or None,
                supersedes=args.get("supersedes") or None,
            )
            return {"created": bool(row.get("created")), "memory": row}

        if op in ("rollback", "veto"):
            target = str(args.get("target") or args.get("memory_id")
                         or args.get("id") or "").strip()
            if not target:
                raise MemoryError(f"{op} 需要 target（记忆 id）")
            reason = str(args.get("reason") or "")
            fn = ledger.rollback if op == "rollback" else ledger.veto
            row = fn(actor_role=role, target=target, reason=reason,
                     evidence_refs=_evidence(args) or None)
            return {"created": bool(row.get("created")), "memory": row}

        if op == "lineage":
            memory_id = str(args.get("memory_id") or args.get("id") or "").strip()
            if not memory_id:
                raise MemoryError("lineage 需要 memory_id")
            return {"events": ledger.lineage(memory_id)}

        if op == "dream":
            reindexed = len(ledger.current_rows(status=ACTIVE_STATUS))
            ledger.rebuild_index()
            rows = ledger.current_rows(status=None)
            isolated = [r["memory_id"] for r in ledger.current_rows()
                        if ledger.is_isolated(r)]
            return {
                "reindexed": reindexed,
                "events": ledger.count_events(),
                "status": _status_counts(rows),
                "isolated": isolated,
                "problems": ledger.check(),
                "index_errors": list(ledger.index_errors),
            }

        if op == "export":
            events = bool(args.get("events"))
            items = ledger.events() if events else ledger.current_rows(status=None)
            return {"events": events, "count": len(items), "items": items}

        if op == "admin":
            action = str(args.get("action") or "stats").strip().lower()
            if action in ("check", "audit"):
                problems = ledger.check()
                return {"ok": not problems, "problems": problems}
            if action in ("stats", "status"):
                rows = ledger.current_rows(status=None)
                by_namespace: dict[str, int] = {}
                by_kind: dict[str, int] = {}
                for row in rows:
                    by_namespace[row["namespace"]] = by_namespace.get(row["namespace"], 0) + 1
                    by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
                return {
                    "events": ledger.count_events(),
                    "current": len(rows),
                    "status": _status_counts(rows),
                    "namespace": by_namespace,
                    "kind": by_kind,
                    "index_errors": list(ledger.index_errors),
                }
            if action in ("rebuild_index", "rebuild-index", "rebuild"):
                reindexed = len(ledger.current_rows(status=ACTIVE_STATUS))
                ledger.rebuild_index()
                return {"reindexed": reindexed}
            raise MemoryError(
                f"未知 admin action：{action!r}（check/stats/rebuild_index）")

        raise NotFound(f"未知记忆操作：{op!r}")

    def health(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": True,
            "service": "kai-memory-daemon",
            "version": "1",
            "pid": os.getpid(),
            "ledger": str(self.db),
            "engine": self.engine_name,
            "queue": {"inflight": self._inflight, "mode": "single-lock"},
        }
        try:
            with self._lock:
                with self._open() as ledger:
                    payload["events"] = ledger.count_events()
                    payload["active"] = len(ledger.current_rows())
                    payload["index_errors"] = list(ledger.index_errors)
        except Exception as exc:  # 健康检查本身不能把 daemon 打挂
            payload["ok"] = False
            payload["ledger_error"] = f"{exc}"
        return payload


def _error_payload(kind: str, message: str) -> dict[str, Any]:
    return {"error": {"type": kind, "message": message}}


class _MemoryHandler(BaseHTTPRequestHandler):
    server_version = "KaiMemory/1"
    protocol_version = "HTTP/1.0"  # 每请求一连接：鉴权失败时不必再排水请求体

    def log_message(self, fmt: str, *args) -> None:  # 默认往 stderr 刷每行，静音
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    # -- 输出 ---------------------------------------------------------------
    def _send(self, status: int, payload: Any, extra: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise MemoryError("Content-Length 不是整数")
        if length > MAX_BODY:
            raise MemoryError(f"请求体过大（>{MAX_BODY} 字节）")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise MemoryError(f"请求体不是 JSON：{exc}") from exc
        if not isinstance(body, dict):
            raise MemoryError("请求体必须是 JSON 对象")
        return body

    def _authenticate(self) -> dict[str, Any] | None:
        header = self.headers.get("Authorization") or ""
        if not header.lower().startswith("bearer "):
            return None
        token = header[7:].strip()
        try:
            return self.server.service.authenticate(token)
        except TokenError:  # token 表损坏：一律当未授权，不泄漏内部细节
            return None

    # -- 路由 ---------------------------------------------------------------
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/health":
            self._send(200, self.server.service.health())
            return
        self._send(404, _error_payload("not_found", f"没有这个路径：{path}"))

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if not path.startswith("/v1/memory/"):
            self._send(404, _error_payload("not_found", f"没有这个路径：{path}"))
            return
        op = path[len("/v1/memory/"):].strip("/")
        identity = self._authenticate()
        if identity is None:
            self._send(401, _error_payload("unauthorized", "缺少或无效的 Bearer token"),
                       {"WWW-Authenticate": 'Bearer realm="kai-memory"'})
            return
        try:
            body = self._read_body()
            result = self.server.service.call(op, body, identity)
        except PermissionDenied as exc:
            self._send(403, _error_payload("forbidden", str(exc)))
        except NotFound as exc:
            self._send(404, _error_payload("not_found", str(exc)))
        except ConflictError as exc:
            self._send(409, _error_payload("conflict", str(exc)))
        except MemoryError as exc:
            self._send(400, _error_payload("bad_request", str(exc)))
        except (ValueError, TypeError) as exc:
            self._send(400, _error_payload("bad_request", str(exc)))
        except Exception as exc:  # 不把堆栈吐给客户端
            self._send(500, _error_payload("internal", f"{type(exc).__name__}: {exc}"))
        else:
            self._send(200, result)


class MemoryHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], service: MemoryService,
                 verbose: bool = False):
        self.service = service
        self.verbose = verbose
        super().__init__(address, _MemoryHandler)


class MemoryDaemon:
    """把器、锁、服务装在一起；测试可 `start_background()` 用临时端口。"""

    def __init__(self, db: str | Path, tokens: str | Path,
                 host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 engine: str = "fts5", lock_path: str | Path | None = None,
                 verbose: bool = False):
        self.db = Path(db)
        self.tokens = Path(tokens)
        self.host = ensure_loopback(host)
        self.requested_port = int(port)
        self.engine = engine or "fts5"
        self.lock_path = Path(lock_path) if lock_path else self.db.with_name(
            self.db.name + ".lock")
        self.verbose = verbose
        self.lock: InstanceLock | None = None
        self.httpd: MemoryHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self.httpd is None:
            return self.requested_port
        return int(self.httpd.server_address[1])

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def bind(self) -> None:
        if self.httpd is not None:
            return
        lock = InstanceLock(self.lock_path)
        lock.acquire()
        service = MemoryService(self.db, self.tokens, self.engine)
        try:
            httpd = MemoryHTTPServer((self.host, self.requested_port), service,
                                     verbose=self.verbose)
        except OSError:
            lock.release()
            raise
        self.lock = lock
        self.httpd = httpd

    def serve_forever(self) -> None:
        self.bind()
        try:
            self.httpd.serve_forever()
        finally:
            self.close()

    def start_background(self) -> tuple[str, int]:
        self.bind()
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        name="kai-memory-daemon", daemon=True)
        self._thread.start()
        return self.host, self.port

    def close(self) -> None:
        httpd, self.httpd = self.httpd, None
        if httpd is not None:
            try:
                httpd.server_close()
            except OSError:
                pass
        lock, self.lock = self.lock, None
        if lock is not None:
            lock.release()

    def stop(self) -> None:
        httpd = self.httpd
        if httpd is not None and self._thread is not None:
            httpd.shutdown()  # 只有 serve_forever 在别的线程跑时才能安全调用
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self.close()

    def __enter__(self) -> "MemoryDaemon":
        self.bind()
        return self

    def __exit__(self, *exc) -> None:
        self.close()
