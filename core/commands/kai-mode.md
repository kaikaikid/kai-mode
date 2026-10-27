---
description: kai-mode 统一入口：判断、拷问、定稿、拍板、路由，不执行具体活
argument-hint: "[一句话需求]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/kai-mode/SKILL.md` 全文，按该文件执行。

用户本轮的需求：$ARGUMENTS

- 拷问一次只问一个，每题带推荐默认；最多五问，只问大方向。
- 定稿后只推荐唤醒命令，不自动拉起角色。
