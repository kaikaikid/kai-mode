#!/usr/bin/env python
"""把 you-should-know 插件的界面文字与提示词改成中文。

用法：
    python scripts/mod-zh.py            # 应用（幂等）
    python scripts/mod-zh.py --revert   # 还原

插件升级会覆盖 register.tsx，升级后重跑一次。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = "[mod-zh]"
BACKUP_SUFFIX = ".tsx.orig"

REPLACEMENTS = [
    # 界面标签
    ("<Text dimColor>Heads up · </Text>", "<Text dimColor>提醒 · </Text>"),
    ('label="Understood"', 'label="知道了"'),
    ('label="Chat in main session"', 'label="在主会话里处理"'),
    ('label="Dismiss"', 'label="忽略"'),
    # 点「在主会话里处理」时填入的提示
    (
        'text: `About your last heads-up ("${current.headline}"): can you check whether it really applies here and show me the fix?`',
        'text: `关于你上一条提醒（"${current.headline}"）：请确认它在这里是否真的成立，并给我修复方案。`',
    ),
    # 命令与开关文案
    (
        "description: 'Turn the second-agent \"you should know\" notes on or off',",
        "description: '开关第二代理的「你应该知道」提醒',",
    ),
    (
        "return { text: next ? 'You-should-know notes are on.' : 'You-should-know notes are off.' }",
        "return { text: next ? '「你应该知道」提醒已开启。' : '「你应该知道」提醒已关闭。' }",
    ),
    # 审查提示词：输出中文，保留 HEADLINE 标记供解析
    (
        "const REVIEW_PROMPT = `You are a quiet second reviewer watching a coding session. Look at what the assistant just did in its last turn (the work, the changes, its final answer).",
        "const REVIEW_PROMPT = `你是一个安静的复审者，观察一个编码会话。看助手在上一轮做了什么（工作、改动、最终答复）。",
    ),
    (
        "Flag ONE thing the user could easily miss and would want to know: a risky side effect, a subtle bug the change introduces (for example a retry that can double-charge), data loss, a security or privacy problem, a skipped or unverified assumption, or a change that reaches further than the request implied.",
        "指出一件用户容易忽略、但会想知道的事：有风险的副作用、改动引入的隐蔽 bug（例如重试导致重复扣费）、数据丢失、安全或隐私问题、被跳过或未验证的假设，或超出请求范围的改动。",
    ),
    (
        "Rules:\n- Be conservative. If there is nothing genuinely worth interrupting for, reply with exactly: NONE\n- Do not summarize the work, praise it, or restate the answer.\n- Otherwise reply in exactly this shape, plain text, no markdown headers:\nHEADLINE: <one sentence, plain language, what could go wrong>\nTITLE: <a short bold-worthy title>\n- <short bullet>\n- <short bullet>\n- <short bullet, at most 4 bullets in all>`",
        "规则：\n- 保守。如果没有真正值得打断用户的事，只回复：NONE\n- 不要总结工作、不要夸奖、不要复述答复。\n- 否则严格按下面的形状回复，纯文本，不要 markdown 标题，内容用中文：\nHEADLINE: <一句话，大白话，说清可能出什么问题>\nTITLE: <一个短标题>\n- <短要点>\n- <短要点>\n- <短要点，最多 4 条>`",
    ),
]


def claude_cmd() -> list[str]:
    if os.name == "nt":
        for name in ("claude.cmd", "claude.exe"):
            p = shutil.which(name)
            if p:
                return [p]
    return [shutil.which("claude") or "claude"]


def installed_register() -> Path:
    out = subprocess.run(claude_cmd() + ["plugin", "list", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("claude plugin list failed: " + out.stderr.strip())
    for p in json.loads(out.stdout):
        if p.get("id") == "you-should-know@claude-code-mods":
            return Path(p["installPath"]) / "hooks" / "register.tsx"
    raise SystemExit("you-should-know@claude-code-mods is not installed")


def main() -> None:
    target = installed_register()
    if not target.exists():
        raise SystemExit(f"register.tsx not found: {target}")
    backup = target.with_suffix(BACKUP_SUFFIX)

    if "--revert" in sys.argv:
        if not backup.exists():
            raise SystemExit("no backup to revert")
        shutil.copy2(backup, target)
        print(f"reverted {target}")
        return

    text = target.read_text(encoding="utf-8")
    if MARKER in text:
        print("already translated")
        return
    if not backup.exists():
        shutil.copy2(target, backup)

    missing = [old for old, _ in REPLACEMENTS if old not in text]
    if missing:
        raise SystemExit("strings not found (mod version changed):\n- " + "\n- ".join(m[:70] for m in missing))

    for old, new in REPLACEMENTS:
        text = text.replace(old, new, 1)
    text = text.replace("const note = atom(", "// " + MARKER + "\nconst note = atom(", 1)
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"translated {target} (backup: {backup.name})")
    print("restart Claude Code to load the translated mod")


if __name__ == "__main__":
    main()
