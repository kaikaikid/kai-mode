---
name: loop
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "loops/loop-protocol.md"
    note: "单票闭环唯一详细源"
description: >
  机长 / 副机长共用的单票闭环（不是用户入口）。判据与本技能冲突时以 `loops/loop-protocol.md` 为准。
  触发：由 `/机长`、`/副机长` 自动带入；「loop」不是口令。
version: 5.1.0
updated: 2026-10-23
---

# loop

本技能只是导航：**怎么做**看 [`loops/loop-protocol.md`](../../loops/loop-protocol.md)，
**什么不能碰、什么自己定**看角色技能。流程叙事、回执长度和机动子代理都是可省的负担；
只有围栏与收工复查是硬约束。

## 一张票

开工评论 → 施工（独立 worktree，先红后绿）→ 施工完成评论 → 新上下文审查
→ `fail` 修 1 次再审 → `pass` 后把判词原样写「待发货」。

## 收工

做完一张票先跑 `python scripts/captain-preflight.py --lane main|deputy`。
`STOP` 才能停；`REVIEW` 加 `--ack-review` 才能停；`CONTINUE` 不许停；`BLOCKED` 写卡点。

## 角色

| 谁 | 日表 | 技能 |
|---|---|---|
| 机长 | `-main.md` | [`../机长/SKILL.md`](../机长/SKILL.md) |
| 副机长 | `-deputy.md` | [`../副机长/SKILL.md`](../副机长/SKILL.md) |
