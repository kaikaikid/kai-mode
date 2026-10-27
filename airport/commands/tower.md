---
description: 机场体系·塔台：先发货、最后排班；独占 push 与关票
argument-hint: "[口令，可留空]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/tower/SKILL.md` 全文，按该文件执行。

用户本轮的补充要求：$ARGUMENTS

- 起手先抢令牌；他人持牌且心跳未过期就退位。
- 先发加急批，再发普通批；排班放本轮最后。
- 不写产品代码、不替审查下结论、不自动拉起任何角色。
