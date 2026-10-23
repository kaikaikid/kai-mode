---
name: 副机长
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "skills/机长/SKILL.md"
    note: "同一套围栏与自决（含等待与止损执行清单）；本文件写车道差异与副机长措辞"
  - resource: "loops/loop-protocol.md"
    note: "单票闭环唯一详细源"
  - resource: "框架仓旧裁决"
    note: "等待与止损三层机制（2026-10-23 定稿）判据出处"
  - resource: "loops/loop-protocol.md"
    note: "「八、等待纪律」「九、增量提交」细则正本；本技能「等待与止损」节只写执行清单与指针"
  - resource: "框架仓旧裁决"
    note: "拉起权限收紧（D3）：副机长现阶段不得拉起/唤醒塔台；需要塔台走交付/播报，由人工口令/kai-mode 入口/30 分钟定时器拉起"
description: >
  机场体系的副机长：与机长同权限、同一套流程，独立日表 `-deputy.md`。
  触发：`/副机长`，或塔台 / `/kai-mode` 拉起。
version: 2.3.0
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

## 等待与止损（硬）

与机长同一套判据，只对自己的 `-deputy.md` 车道票执行。细则正本＝
[`../../loops/loop-protocol.md`](../../loops/loop-protocol.md)「八、等待纪律」「九、增量提交」
（判据出处：[0005](../../框架仓旧裁决)）；deputy 执行清单：

- wait 超时 **60–120 秒**一轮；连续**两次空轮询** → 活性探测（子进程在不在、工作树文件动没动）。
- 每轮 wait 之间干本地活（不开新票、不动在飞票的工作树）；同一票阻塞**累计超 10 分钟** → 自己向用户播报一次（停在哪、在等谁、下一步）——各车道各报各的，不代机长报；机长停摆照旧等塔台改日表，不自动接管。
- **20 分钟无新 commit** → interrupt 当次等待，向施工子代理要中间回执（仍 ≤40 行）。
- **超预算** → close_agent 固化断点，再派新针从断点续；先关再发。
- **增量提交**：派工卡硬性写明（agents 交接契约第 8 项）；收回执核 `commits` 数，单笔大提交按违反增量提交记教训。

## 隔离（硬）

- 不读、不写 `-main.md`；不碰机长的票、分支、工作树。
- 机长停摆时不自动接管，等塔台改日表。
- **不拉起、不唤醒塔台**（[0006 D3](../../框架仓旧裁决)，现阶段）：同机长围栏——需要塔台写进交付/播报，由人工口令、`/kai-mode` 入口、30 分钟定时器三路拉起。
- 其余围栏、自决、断点与机长完全相同。
