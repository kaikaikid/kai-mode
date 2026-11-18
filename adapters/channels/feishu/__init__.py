"""飞书桥：把飞书当远端收发面（设计正本见 docs/design/2026-11-01-feishu-bridge.md）。

分层：config / ledger / policy / triage / cards 是纯逻辑（可单测）；
lark / consumer / notify / bridge 才碰子进程与网络。
"""

__all__ = ["config", "ledger", "policy", "triage", "cards", "lark", "consumer", "notify", "bridge"]
