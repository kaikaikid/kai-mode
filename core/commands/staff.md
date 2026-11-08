---
description: staff 规划方法：拷问、定稿、拆票草案、规划表；由康娜调用，不执行具体活
argument-hint: "[一句话需求]"
---

读取并执行 `${CLAUDE_PLUGIN_ROOT}/skills/staff/SKILL.md` 全文，按该文件执行。

用户本轮的需求：$ARGUMENTS

- 拷问一次只问一个，每题带推荐默认；最多五问，只问大方向。
- 定稿后把结果交回康娜，由康娜开票并决定是否开 run。
