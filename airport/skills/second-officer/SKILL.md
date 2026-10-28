---
name: second-officer
status: active
approved_by: human:kaikaikid
approved: 2026-10-27
sources:
  - resource: "../pilot/SKILL.md"
    note: "同一套围栏与自决；本文件只写车道差异与二副措辞"
  - resource: "../loop/SKILL.md"
    note: "单票闭环与三份参考的随装入口；本文件只写车道差异"
description: >
  机场体系的二副（第二副机长）：与机长、副机长同权限、同一套流程（滚动消费自己那张日表、
  待发货不占执行名额、取舍题默认派裁决子代理不提问、收场必先落续跑指针），独立日表 `-second.md`。
  触发：`/second-officer`、说「二副」「第二副机长」「二副开工」「跑二副的表」。
version: 1.0.0
updated: 2026-10-27
allowed-tools: Bash(git:*) Bash(gh:*) Bash(python:*) Read Grep
compatibility: Requires git
metadata:
  alias: 二副
dependencies:
  skills:
    - name: loop
      min_version: "6.0.0"
      reason: "second-officer 按 loop 的闭环与三份参考执行"
---

# 二副（第二副机长）

**除了车道，其它全部照机长。** 先读 [`../pilot/SKILL.md`](../pilot/SKILL.md)，
把下面三处替换掉即可。二副是第三条机长道，与副机长并列，不是副机长的替补：
各读各表、各算各的名额、各写各的票。

## 车道差异

| 项 | 机长 | 二副 |
|---|---|---|
| 日表 | 项目配置 `paths.day_tables_dir`＋`day_table_pattern`（`-main.md`） | 同 `paths.day_tables_dir`（`-second.md`） |
| 预检 | `--lane main` | `--lane second` |
| 可写 Issue | `-main.md` 里的票 | `-second.md` 里的票 |

## 自决（可省的负担）

除机长技能里的围栏外，流程叙事、回执长度、评论详略、拆活方式和机动子代理都按情况自决；
这些是负担，不是硬闸。

读票用窄读、判词格式、收尾自检三件均同机长，不另立口径。
**取舍题也不自决硬拍、更不问人**：机长技能「取舍裁决」那一整套照用——默认派裁决子代理；
只有它也判不了的两类题（两份已生效正本互斥／需人眼判观感）才延后＋上报塔台攒批。

## 收工复查

```bash
python <gates.captain_preflight> --lane second
```

四值语义见协议 §七「收工门禁四值契约」。补位前同机长：须先过可死性三件（协议 §一）。

## 验证命令

清单同机长（正本见 [`../pilot/SKILL.md`](../pilot/SKILL.md)「验证命令」），只把车道换成 `second`：

```bash
python <gates.captain_preflight> --lane second
```

## 等待与止损（硬）

**判据正本＝机长技能「等待与止损」那一整套（等待梯＋两态收尾＋续跑指针），不另立口径**；
本道只有一条车道差异：**各车道各报各的**——同一票阻塞超 10 分钟只播自己这张，不代机长或副机长报；
机长停摆照旧等塔台改日表，不自动接管。

## 隔离（硬）

- 不读、不写 `-main.md` / `-deputy.md`；不碰机长、副机长、王牌的票、分支、工作树。
- 机长或副机长停摆时不自动接管，等塔台改日表。
- **不唤醒任何其他角色**：需要塔台写进交付／播报，交人工或定时器处理。
- 其余围栏、自决、断点与机长完全相同。
