---
name: 副机长
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "skills/机长/SKILL.md"
    note: "同一套围栏与自决；本文件只写车道差异"
  - resource: "loops/loop-protocol.md"
    note: "单票闭环唯一详细源"
description: >
  机场体系的副机长：与机长同权限、同一套流程，独立日表 `-deputy.md`。
  触发：`/副机长`，或塔台 / `/kai-mode` 拉起。
version: 2.1.0
updated: 2026-10-23
---

# 副机长

**除了车道，其它全部照机长。** 先读 [`../机长/SKILL.md`](../机长/SKILL.md)，
把下面三处替换掉即可。

## 车道差异

| 项 | 机长 | 副机长 |
|---|---|---|
| 日表 | 项目配置 `paths.day_tables_dir`＋`day_table_pattern`（`-main.md`） | 同 `paths.day_tables_dir`（`-deputy.md`） |
| 预检 | `--lane main` | `--lane deputy` |
| 可写 Issue | `-main.md` 里的票 | `-deputy.md` 里的票 |

## 自决（可省的负担）

除机长技能里的围栏外，流程叙事、回执长度、评论详略、拆活方式和机动子代理都按情况自决；
这些是负担，不是硬闸。

## 收工复查

```
python scripts/captain-preflight.py --lane deputy
```

`CONTINUE` 继续；`REVIEW` 判完确实没活加 `--ack-review`；`STOP` 才停；
`BLOCKED` 写卡点，不得当空表。

## 隔离（硬）

- 不读、不写 `-main.md`；不碰机长的票、分支、工作树。
- 机长停摆时不自动接管，等塔台改日表。
- 其余围栏、自决、断点与机长完全相同。
