"""`kai memory` 命令面：retrieve / propose / commit / rollback / veto / lineage / export。

真相在 `engine/memory/ledger.py` 的 SQLite 账本；这里只做参数解析与输出。
治理动作（commit/rollback/veto）只收 `archivist`；其它角色只能 propose。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .engine import build_engine
from .ledger import (
    ALL_KINDS,
    ARCHIVIST,
    Ledger,
    MemoryError,
    NotFound,
    PermissionDenied,
)
from .tokens import TokenError, TokenStore


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_db() -> Path:
    explicit = os.environ.get("KAI_MEMORY_DB")
    if explicit:
        return Path(explicit)
    data_root = os.environ.get("KAI_AGENT_DATA_ROOT")
    if data_root:
        return Path(data_root) / "kai-mode" / "memory" / "ledger.db"
    return repo_root() / ".coding" / "memory" / "ledger.db"


def default_tokens() -> Path:
    explicit = os.environ.get("KAI_MEMORY_TOKENS")
    if explicit:
        return Path(explicit)
    return default_db().parent / "tokens.json"


def _open(args: argparse.Namespace) -> Ledger:
    db = Path(args.db) if args.db else default_db()
    engine_name = args.engine or os.environ.get("KAI_MEMORY_ENGINE") or "fts5"
    engine = build_engine(engine_name, db)
    return Ledger(db, engine=engine)


def _emit(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_propose(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rec = ledger.propose(
            actor_role=a.actor_role, namespace=a.namespace, kind=a.kind,
            statement=a.statement, evidence_refs=a.evidence,
            subject=a.subject, source=a.source, session_id=a.session_id,
            before=a.before or "", after=a.after or "",
            conflicts_with=a.conflicts_with or [], layer=a.layer)
    _emit(rec)
    return 0


def cmd_commit(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rec = ledger.commit(
            actor_role=a.actor_role, proposal_id=a.proposal_id,
            namespace=a.namespace, kind=a.kind, statement=a.statement,
            evidence_refs=a.evidence, subject=a.subject, source=a.source,
            session_id=a.session_id, before=a.before or "", after=a.after or "",
            conflicts_with=a.conflicts_with or [], layer=a.layer,
            supersedes=a.supersedes)
    _emit(rec)
    return 0


def cmd_rollback(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rec = ledger.rollback(actor_role=a.actor_role, target=a.target,
                              reason=a.reason, evidence_refs=a.evidence)
    _emit(rec)
    return 0


def cmd_veto(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rec = ledger.veto(actor_role=a.actor_role, target=a.target,
                          reason=a.reason, evidence_refs=a.evidence)
    _emit(rec)
    return 0


def cmd_retrieve(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rows = ledger.retrieve(namespace=a.namespace, kind=a.kind, query=a.query,
                               top_k=a.top_k, max_tokens=a.max_tokens)
    if a.json:
        _emit(rows)
    else:
        for r in rows:
            print(f"{r['memory_id']} [{r['kind']}] {r['statement']}")
            print(f"    证据：{'; '.join(r.get('evidence_refs') or [])}")
    return 0


def cmd_lineage(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rows = ledger.lineage(a.id)
    if a.json:
        _emit(rows)
    else:
        for r in rows:
            print(f"#{r['seq']} {r['event_type']:<9} {r['status']:<12} "
                  f"{r['ts']} {r['actor_role']}  {r['statement']}")
            if r.get("reason"):
                print(f"    理由：{r['reason']}")
    return 0


def cmd_serve(a: argparse.Namespace) -> int:
    from .daemon import MemoryDaemon
    db = Path(a.db) if a.db else default_db()
    tokens = Path(a.tokens) if a.tokens else default_tokens()
    engine = a.engine or os.environ.get("KAI_MEMORY_ENGINE") or "fts5"
    daemon = MemoryDaemon(db, tokens, host=a.host, port=a.port, engine=engine)
    daemon.bind()
    print(f"kai memory daemon 监听 {daemon.url}；账本 {db}；token 表 {tokens}", flush=True)
    try:
        with daemon:
            daemon.httpd.serve_forever()
    except KeyboardInterrupt:
        print("收到中断，daemon 退出", file=sys.stderr)
    return 0


def cmd_mcp(a: argparse.Namespace) -> int:
    from . import mcp
    argv: list[str] = []
    if a.url:
        argv += ["--url", a.url]
    if a.token:
        argv += ["--token", a.token]
    return mcp.main(argv)


def _token_store(a: argparse.Namespace) -> TokenStore:
    return TokenStore(Path(a.tokens) if a.tokens else default_tokens())


def cmd_key_new(a: argparse.Namespace) -> int:
    store = _token_store(a)
    token = store.create(a.agent, a.role)
    role = (a.role or a.agent).strip().lower()
    if a.json:
        _emit({"agent": a.agent, "role": role, "token": token,
               "tokens": str(store.path)})
    else:
        print(token)
        print(f"已创建 agent={a.agent} role={role}；token 只显示这一次，"
              f"{store.path} 只存 sha256", file=sys.stderr)
    return 0


def cmd_key_rotate(a: argparse.Namespace) -> int:
    store = _token_store(a)
    token = store.rotate(a.agent)
    if a.json:
        _emit({"agent": a.agent, "token": token, "tokens": str(store.path)})
    else:
        print(token)
        print(f"已轮换 agent={a.agent}；旧 token 立即失效", file=sys.stderr)
    return 0


def cmd_key_remove(a: argparse.Namespace) -> int:
    store = _token_store(a)
    store.remove(a.agent)
    _emit({"removed": a.agent, "tokens": str(store.path)})
    return 0


def cmd_key_list(a: argparse.Namespace) -> int:
    rows = _token_store(a).list()
    if a.json:
        _emit(rows)
    else:
        for row in rows:
            print(f"{row['agent']}\t{row['role']}\t{row['created_at']}\t"
                  f"{row['rotated_at'] or '-'}")
    return 0


def cmd_export(a: argparse.Namespace) -> int:
    with _open(a) as ledger:
        rows = ledger.events() if a.events else ledger.current_rows(status=None)
    if a.out:
        path = Path(a.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        print(f"导出 {len(rows)} 条 → {path}")
    else:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kai memory",
        description="记忆账本：append-only SQLite + FTS5；治理动作只收 archivist")
    p.add_argument("--db", default=None,
                   help=f"账本路径（默认 {default_db()}；也可用 KAI_MEMORY_DB）")
    p.add_argument("--engine", default=None,
                   help="检索引擎：fts5（默认）；qdrant/openviking 仅为接口桩")
    p.add_argument("--tokens", default=None,
                   help=f"token 表路径（默认 {default_tokens()}；也可用 KAI_MEMORY_TOKENS）")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--json", action="store_true", help="机器可读输出")

    sp = sub.add_parser("propose", help="任何角色提候选（不生效）")
    sp.add_argument("--actor-role", required=True)
    sp.add_argument("--namespace", required=True)
    sp.add_argument("--kind", required=True, choices=ALL_KINDS)
    sp.add_argument("--statement", required=True)
    sp.add_argument("--evidence", action="append", default=[])
    sp.add_argument("--subject", default=None)
    sp.add_argument("--source", default=None)
    sp.add_argument("--session-id", default=None)
    sp.add_argument("--before", default="")
    sp.add_argument("--after", default="")
    sp.add_argument("--conflicts-with", action="append", default=[])
    sp.add_argument("--layer", default=None)
    common(sp)
    sp.set_defaults(func=cmd_propose)

    sp = sub.add_parser("commit", help="archivist 把候选转正（或直接写入）")
    sp.add_argument("--actor-role", required=True)
    sp.add_argument("--proposal-id", default=None)
    sp.add_argument("--namespace", default=None)
    sp.add_argument("--kind", default=None, choices=ALL_KINDS)
    sp.add_argument("--statement", default=None)
    sp.add_argument("--evidence", action="append", default=[])
    sp.add_argument("--subject", default=None)
    sp.add_argument("--source", default=None)
    sp.add_argument("--session-id", default=None)
    sp.add_argument("--before", default="")
    sp.add_argument("--after", default="")
    sp.add_argument("--conflicts-with", action="append", default=[])
    sp.add_argument("--layer", default=None)
    sp.add_argument("--supersedes", default=None,
                    help="把旧条目置为 superseded（旧行保留）")
    common(sp)
    sp.set_defaults(func=cmd_commit)

    sp = sub.add_parser("rollback", help="archivist 追加反向记录；原记录保留")
    sp.add_argument("--actor-role", required=True)
    sp.add_argument("--target", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--evidence", action="append", default=[])
    common(sp)
    sp.set_defaults(func=cmd_rollback)

    sp = sub.add_parser("veto", help="archivist 标 tombstone；不删除")
    sp.add_argument("--actor-role", required=True)
    sp.add_argument("--target", required=True)
    sp.add_argument("--reason", required=True)
    sp.add_argument("--evidence", action="append", default=[])
    common(sp)
    sp.set_defaults(func=cmd_veto)

    sp = sub.add_parser("retrieve", help="按 namespace+kind+active 检索（top-k/token 上限）")
    sp.add_argument("--namespace", required=True)
    sp.add_argument("--kind", default=None, choices=ALL_KINDS)
    sp.add_argument("--query", default=None)
    sp.add_argument("--top-k", type=int, default=5)
    sp.add_argument("--max-tokens", type=int, default=2000)
    common(sp)
    sp.set_defaults(func=cmd_retrieve)

    sp = sub.add_parser("lineage", help="看一条记忆的全部事件（审计）")
    sp.add_argument("--id", required=True)
    common(sp)
    sp.set_defaults(func=cmd_lineage)

    sp = sub.add_parser("export", help="导出账本（默认当前视图）")
    sp.add_argument("--out", default=None)
    sp.add_argument("--events", action="store_true", help="导出全部事件而非当前视图")
    common(sp)
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("serve", help="起本机 daemon（默认 127.0.0.1:8788）")
    sp.add_argument("--host", default="127.0.0.1",
                    help="只允许回环地址：127.0.0.1 / localhost")
    sp.add_argument("--port", type=int, default=8788)
    sp.set_defaults(func=cmd_serve)

    sp = sub.add_parser("mcp", help="MCP stdio 适配器（转发到本机 daemon）")
    sp.add_argument("--url", default=None,
                    help="daemon 地址（默认 $KAI_MEMORY_URL 或 http://127.0.0.1:8788）")
    sp.add_argument("--token", default=None,
                    help="agent token（默认 $KAI_MEMORY_TOKEN）")
    sp.set_defaults(func=cmd_mcp)

    sp = sub.add_parser("key", help="每 agent 一把 token（只存 sha256）")
    ksub = sp.add_subparsers(dest="key_cmd", required=True)
    k = ksub.add_parser("new", help="给 agent 新建 token（明文只显示这一次）")
    k.add_argument("--agent", required=True)
    k.add_argument("--role", default=None,
                   help="权限角色，默认等于 agent；治理动作要 archivist")
    common(k)
    k.set_defaults(func=cmd_key_new)
    k = ksub.add_parser("rotate", help="轮换 token；旧 token 立即失效")
    k.add_argument("--agent", required=True)
    common(k)
    k.set_defaults(func=cmd_key_rotate)
    k = ksub.add_parser("remove", help="删除 agent 的 token")
    k.add_argument("--agent", required=True)
    common(k)
    k.set_defaults(func=cmd_key_remove)
    k = ksub.add_parser("list", help="列出 agent 与角色（不显示 token）")
    common(k)
    k.set_defaults(func=cmd_key_list)
    return p


def _take_option(argv: list[str], flag: str) -> tuple[str | None, list[str]]:
    """把 `--db/--engine` 从任意位置摘出来，放前放后都能用。"""
    value: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(argv):
        item = argv[i]
        if item == flag and i + 1 < len(argv):
            value = argv[i + 1]
            i += 2
            continue
        if item.startswith(flag + "="):
            value = item.split("=", 1)[1]
            i += 1
            continue
        rest.append(item)
        i += 1
    return value, rest


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `kai memory ...`：去掉 launcher 带进来的 memory 子词，直连时也可省略。
    if argv and argv[0] == "memory":
        argv = argv[1:]
    db_opt, argv = _take_option(argv, "--db")
    engine_opt, argv = _take_option(argv, "--engine")
    tokens_opt, argv = _take_option(argv, "--tokens")
    parser = build_parser()
    a = parser.parse_args(argv)
    if db_opt is not None:
        a.db = db_opt
    if engine_opt is not None:
        a.engine = engine_opt
    if tokens_opt is not None:
        a.tokens = tokens_opt
    try:
        return int(a.func(a))
    except PermissionDenied as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (MemoryError, NotFound, TokenError, OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
