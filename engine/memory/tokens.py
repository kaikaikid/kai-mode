"""每 agent 一把 token 的本地凭据表（ADR-0037 D6）。

存储只放 **sha256 哈希**，明文 token 只在 `kai memory key new/rotate` 时打印一次。
默认位置跟随账本：`$KAI_MEMORY_TOKENS` → `<账本目录>/tokens.json`。
POSIX 上文件权限 0600；Windows 只做 best-effort（`os.chmod` 语义有限），安全边界靠回环监听。

治理动作（commit/rollback/veto/dream/export/admin）只认 `role=archivist` 的 token；
角色由 token 记录决定，请求体里的 `actor_role` 不参与鉴权。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARCHIVIST = "archivist"
ROLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
TOKEN_PREFIX = "kmt_"
STORE_VERSION = 1


class TokenError(Exception):
    """token 表校验不过（重名、找不到、格式错）。CLI 退出码 2。"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


class TokenStore:
    """`tokens.json` 的读写；一个 agent 名字对应一把 token、一个角色。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    # -- 读 -----------------------------------------------------------------
    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": STORE_VERSION, "tokens": {}}
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            raise TokenError(f"token 表读不了：{self.path}（{exc}）") from exc
        if not isinstance(data, dict) or not isinstance(data.get("tokens"), dict):
            raise TokenError(f"token 表格式不对：{self.path}")
        data.setdefault("version", STORE_VERSION)
        return data

    # -- 写 -----------------------------------------------------------------
    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent),
                                   prefix=".tokens-", suffix=".tmp")
        try:
            if hasattr(os, "fchmod"):
                try:
                    os.fchmod(fd, 0o600)
                except OSError:
                    pass
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    # -- 生命周期 -----------------------------------------------------------
    def create(self, agent: str, role: str | None = None) -> str:
        agent = str(agent or "").strip()
        role = str(role or agent).strip().lower()  # 角色统一小写，archivist 治理判定才稳
        if not ROLE_RE.match(agent):
            raise TokenError(f"agent 名不合规：{agent!r}（字母开头，字母数字 _ -，≤32）")
        if not ROLE_RE.match(role):
            raise TokenError(f"role 不合规：{role!r}（字母开头，字母数字 _ -，≤32）")
        data = self._load()
        if agent in data["tokens"]:
            raise TokenError(f"agent {agent!r} 已有 token；要换用 `key rotate`")
        token = _new_token()
        data["tokens"][agent] = {
            "role": role,
            "hash": hash_token(token),
            "created_at": _now(),
            "rotated_at": None,
        }
        self._save(data)
        return token

    def rotate(self, agent: str) -> str:
        agent = str(agent or "").strip()
        data = self._load()
        rec = data["tokens"].get(agent)
        if rec is None:
            raise TokenError(f"没有 agent {agent!r} 的 token；先用 `key new`")
        token = _new_token()
        rec["hash"] = hash_token(token)
        rec["rotated_at"] = _now()
        self._save(data)
        return token

    def remove(self, agent: str) -> None:
        agent = str(agent or "").strip()
        data = self._load()
        if data["tokens"].pop(agent, None) is None:
            raise TokenError(f"没有 agent {agent!r} 的 token")
        self._save(data)

    def list(self) -> list[dict[str, Any]]:
        data = self._load()
        return [
            {
                "agent": agent,
                "role": rec.get("role"),
                "created_at": rec.get("created_at"),
                "rotated_at": rec.get("rotated_at"),
            }
            for agent, rec in sorted(data["tokens"].items())
        ]

    # -- 鉴权 ---------------------------------------------------------------
    def lookup(self, token: str | None) -> dict[str, Any] | None:
        """按明文 token 找身份；只比较哈希，常数时间。"""
        if not token:
            return None
        digest = hash_token(token)
        data = self._load()
        for agent, rec in data["tokens"].items():
            stored = str(rec.get("hash") or "")
            if stored and hmac.compare_digest(stored, digest):
                return {"agent": agent, "role": rec.get("role")}
        return None
