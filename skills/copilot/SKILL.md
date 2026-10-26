---
name: copilot
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "skills/pilot/SKILL.md"
    note: "同一套围栏与自决（含等待与止损执行清单）；本文件写车道差异与副机长措辞"
  - resource: "skills/loop/SKILL.md"
    note: "单票闭环、等待与止损的随装入口；本文件只写车道差异与副机长措辞"
description: >
  机场体系的副机长：与机长同权限、同一套流程（滚动消费自己那张日表、待发货不占位、跃迁窗口内取舍派裁决子代理不提问），独立日表 `-deputy.md`。
  触发：`/副机长`（人工唤醒）；塔台只写日表/播报，kai-mode 只推荐命令，不自动起角色。
version: 2.6.0
updated: 2026-10-26
allowed-tools: Bash(git:*) Bash(gh:*) Bash(python:*) Read Grep
compatibility: Requires git
metadata:
  alias: 副机长
dependencies:
  skills:
    - name: loop
      min_version: "1.0.0"
      reason: "copilot 按 loop 的闭环执行"
---

# 副机长

**除了车道，其它全部照机长。** 先读 [`../pilot/SKILL.md`](../pilot/SKILL.md)，
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

读票用窄读、判词格式、收尾自检三件均同机长，不另立口径。
**取舍题也不自决硬拍、更不问人**：机长技能「跃迁窗口」那一整套照用（窗外写卡点交塔台攒批）。

## 收工复查

```bash
python <gates.captain_preflight> --lane deputy
```

`CONTINUE` 继续补下一张（表的判据只算未完工票，已 `pass` 进待发货的不占你名额）；
`REVIEW` 判完确实没活加 `--ack-review`；`STOP` 才停；`BLOCKED` 写卡点，不得当空表。

## 验证命令

清单同机长（正本见 [`../pilot/SKILL.md`](../pilot/SKILL.md)「验证命令」），只把车道换成 `deputy`：

```bash
python <gates.captain_preflight> --lane deputy
```

## 等待与止损（硬）

与机长同一套判据，只对自己的 `-deputy.md` 车道票执行。细则正本＝
兄弟技能 `loop` 的协议正文「八、等待纪律」「九、增量提交」
；deputy 执行清单：

- wait 超时 **60–120 秒**一轮；连续**两次空轮询** → 活性探测（子进程在不在、工作树文件动没动）。
- 每轮 wait 之间干本地活（不开新票、不动在飞票的工作树）；同一票阻塞**累计超 10 分钟** → 自己向用户播报一次（停在哪、在等谁、下一步）——各车道各报各的，不代机长报；机长停摆照旧等塔台改日表，不自动接管。
- **20 分钟无新 commit** → interrupt 当次等待，向施工子代理要中间回执（仍按兄弟技能 `loop` 的等待上限）。
- **超预算** → close_agent 固化断点，再派新针从断点续；先关再发。
- **增量提交**：派工卡硬性写明（agents 交接契约第 8 项）；收回执核 `commits` 数，单笔大提交按违反增量提交记教训。

## 隔离（硬）

- 不读、不写 `-main.md`；不碰机长的票、分支、工作树。
- 机长停摆时不自动接管，等塔台改日表。
- **不唤醒任何其他角色**（含塔台、继任机长）：同机长围栏——需要塔台写进交付/播报，交人工或唤醒定时器处理。
- 其余围栏、自决、断点与机长完全相同。
