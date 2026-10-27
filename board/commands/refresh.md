---
description: 刷新航班信息看板：采集、落库、出 board.json 与 index.html
argument-hint: "[看板配置路径，可留空]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/flight-info/SKILL.md` 全文，按该文件执行。

用户本轮的补充要求：$ARGUMENTS

- AI 只读 `board.json`，不 grep HTML。
- 任一源失败只降级点名，不让整页崩。
