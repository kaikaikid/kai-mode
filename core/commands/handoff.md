---
description: 写交接：把当前会话压成一份可续接的交接文档
argument-hint: "[下一棒要做什么，可留空]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/kai-handoff/SKILL.md` 全文，按该文件执行。

用户本轮的补充要求：$ARGUMENTS

- 只给路径与指针，不复制 issue／ADR／diff 正文。
- 不写机器绝对路径。
