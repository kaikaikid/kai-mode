# -*- coding: utf-8 -*-
"""内核边界：v2/coding 只做状态与调度，不认宿主、不发外部请求、不引第三方。

失败方式（借鉴 agent-autoloop 的 purity test）：
- 有人在核心里写死某个宿主/产品名，换宿主就得改内核；
- 有人偷偷在核心里起外部进程或发 HTTP；
- 有人引入第三方依赖，安装变重。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "coding"
VENDORS = (
    "claude", "anthropic", "codex", "openai", "qoder", "opencode",
    "feishu", "lark", "dingtalk", "slack", "discord",
)


def sources() -> list[Path]:
    return sorted(p for p in ROOT.glob("*.py") if p.name != "__init__.py")


def test_kernel_names_no_vendor():
    for path in sources():
        text = path.read_text(encoding="utf-8").lower()
        for vendor in VENDORS:
            assert vendor not in text, f"{path.name} 出现宿主专有名：{vendor}"


def test_kernel_imports_stdlib_only():
    for path in sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # 相对导入
                    continue
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name:
                    assert name in sys.stdlib_module_names, f"{path.name} 引入非标准库：{name}"


def test_kernel_sends_no_request():
    forbidden = ("import requests", "import httpx", "urllib.request", "http.client", "socket.")
    for path in sources():
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path.name} 出现对外请求：{needle}"
