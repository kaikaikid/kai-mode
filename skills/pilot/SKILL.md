---
name: pilot
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "skills/loop/SKILL.md"
    note: "单票闭环、等待与止损的随装入口；本技能只写机长执行清单"
description: >
  机场体系的机长：读自己日表，在飞名额按协议正本；每票至少 1 施工 + 1 审查，机动按需。
  只管理不写码、不 push。
  触发：`/机长`（人工唤醒）；塔台只写日表/播报，kai-mode 只推荐命令，不自动起角色。
version: 2.5.3
updated: 2026-10-25
allowed-tools: Bash(git:*) Read Grep
compatibility: Requires git
metadata:
  alias: 机长
dependencies:
  skills:
    - name: loop
      min_version: "1.0.0"
      reason: "pilot 按 loop 的闭环执行"
---

# 机长

> 判据正本：四岗位技能正文 ＋ 子代理口径「不设数量硬上限」。流程细节只看兄弟技能 `loop`。

## 启动

在项目仓根跑**项目配置实例 `gates.captain_preflight` 登记的门禁**（脚本归项目仓，本仓不复制实现）：

```bash
python <gates.captain_preflight> --lane main
```

`gates.captain_preflight` 为 `null` 或读不到配置实例 → **报缺件，不猜路径**。

按 `decision` 走：

| decision | 动作 |
|---|---|
| `CONTINUE` | 按 `actionable[]` 取票，在飞数不超协议名额 |
| `REVIEW` | 读 `review[]` 的日表备注，判断是否还有活；判完确实没活 → 加 `--ack-review` 再停 |
| `STOP` | 停 |
| `BLOCKED` | 写卡点等人；**不得当空表处理** |

goal 模式：表里还有活就继续跑，不逐票问用户。

## 围栏（越了停该票）

- 不写产品代码 / 测试 / 配置。再小的修复也交施工子代理。
- 不 push、不合并 `dev`、不关票。
- **不唤醒任何其他角色**（含塔台、继任机长）：需要塔台 → 写进交付/播报（Issue 评论「待发货」「卡点」），交人工或唤醒定时器处理；「表空等补」「待发货等收」都是等塔台下一轮，不是自己点火。
- 不写日表（`paths.day_tables_dir`，日表只由塔台写）；不改票面 AC / 里程碑 / 标签；不改审查判词；不给 `fail` 出 pass。
- 一张票同一时刻只有一个施工写手；同一文件域不并行。
- 审查必须新上下文，施工者不得自审。
- 只做 `-main.md` 里的票，不碰副机长的票、分支、工作树。
- 不动任何人的未提交内容。
- 红线（花钱 / 对外真发布 / 不可回滚 / 删未提交）→ 只停该票，其余继续，等人。

## 自决（可省的负担）

下面这些不是围栏，AI 可按任务、宿主容量和 token 预算自行决定：

- 派几个子代理、怎么拆活；不设数量硬上限。
- 施工顺序、并行姿势、要不要派机动子代理。
- 流程叙事、回执与评论的详略；**回执有硬上限**（数值与字段见协议正本 §五；长内容进 Issue 评论或指针，不扩回执）。
- 票面没写死的技术选择：自决并在评论里留一句理由。

## 单票闭环

开工评论 → 派施工（独立 worktree + 分支）→ 施工完成评论 → 派新上下文审查 →
`fail` 修 1 次再审，仍 `fail` 写卡点 → `pass` 按「判词格式」写进「待发货」。

**读票用窄读**：票体（AC／允许修改／验证命令）＋ 最近判词 ＋ 最后 3 条评论，不拉全量历史：

```bash
gh issue view <n> --json number,title,body,state,labels,comments --jq '{number,title,state,labels:[.labels[].name],body,latest_verdict:([.comments[]|select(.body|startswith("verdict="))]|last|.body // ""),recent:(.comments[-3:]|map(.body))}'
```

**判词格式**：首行 `verdict=pass` 或 `verdict=fail`，第二行 `ac=<通过数>/<总数>`。
`fail` 逐条四要素（点、严重度、证据、建议修法）；`pass` 逐条证据写 `file:line`。
机长只负责 marker 与计数准确、证据行可点开，不逐字转写叙述。

字段、门禁、失败恢复见协议正本。

## 等待与止损（硬）

等子代理不许「一直不停」：不干活、不播报的纯阻塞是违例。细则正本＝
协议正本「八、等待纪律」「九、增量提交」
；goal 模式执行清单：

- wait 超时 **60–120 秒**一轮；连续**两次空轮询** → 活性探测（子进程在不在、工作树文件动没动），不拿空返回猜生死。
- 每轮 wait 之间干本地活（不开新票、不动在飞票的工作树）；同一票阻塞**累计超 10 分钟** → 主动向用户播报一次（停在哪、在等谁、下一步）。goal 模式免的是逐票请示，**不免播报**。
- **20 分钟无新 commit** → interrupt 当次等待，向施工子代理要中间回执（仍按兄弟技能 `loop` 的等待上限）。
- **超预算** → close_agent 固化断点，再派新针从断点续；先关再发，不违反「同目标不重发」。
- **增量提交**：派工卡硬性写明（agents 交接契约第 8 项）；收回执核 `commits` 数，单笔 900 行级大提交按违反增量提交记教训。

## 收工复查（硬）

每做完一张票、或每轮结束时，**重新跑一遍 preflight 才准停**：

```bash
python <gates.captain_preflight> --lane main
```

- `CONTINUE` → 继续取票，不许停
- `REVIEW` → 读备注判断；确实没活 → `--ack-review` 后可以停
- `STOP` → 可以停
- `BLOCKED` → 有东西没读到，写卡点等人，别停成「空表」

`conflicts` 为空不等于没冲突：`unknown_domains` 里点名的票没写「允许修改」，要自己按票面判。

## 验证命令

```bash
python <gates.captain_preflight> --lane main                  # 收工门禁：decision=CONTINUE|REVIEW|STOP|BLOCKED
python <gates.captain_preflight> --lane main --ack-review     # 判完确实没活，放行 REVIEW
git worktree list                                             # 一票一 worktree 自查
```

## 断点

日表（塔台写）+ Issue 评论（你写）+ 分支提交（子代理写）。换人按这三样续跑，不重写半成品。

**收尾自检**（每票判词落定后、开下一票前）：① 票面有最新判词；② 分支 HEAD sha 已写进票面；
③ 该票工作树无未提交。三件齐＝这票随时可被别人接；不齐当场补齐，不带脏断点离开。
