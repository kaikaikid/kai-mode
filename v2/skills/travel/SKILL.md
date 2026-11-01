---
name: travel
status: active
approved_by: human:kaikaikid
approved: 2026-10-31
sources: []
description: >
  V2 执行内核的唯一入口：一个 issue 一个 run（舰船），主会话规划与验收，物理子会话执行；
  舰队（fleet）= 同一宿主拉起的 run 集合，舰船数 1–3（默认 2）、船员数（并发子代理）1–5（默认 5）按舰队独立计数；
  一次触发连续跑到门点才停。用 `travel` 控制平面推进（`coding` 兼容别名一版），不直接改 state.json。
  与机场体系（V1）并存，不调用其角色。
  触发：`/warp <任务>`、`/jump <任务>`（斜杠入口）；控制面命令 `travel <子命令>`（`coding` 兼容一版）；中文「用 V2 做」「开个 run」也认。
  本地监工服务：`travel serve`（只读 API + 受控 gate/stop/drive，默认只绑 127.0.0.1，Windows 静默）。
version: 0.3.0
updated: 2026-11-01
allowed-tools: Read Grep Bash
compatibility: Host-agnostic
---

# Travel —— V2 执行内核入口（星际穿越剧本）

> 设计正本：`docs/design/2026-10-30-v2-execution-kernel.md`
> 实现：`v2/coding/`，命令 `v2/bin/travel`（`v2/bin/coding` 兼容别名一版）
> 安装：`v2/README.md`

## 这是什么

`/warp` `/jump`（或舰桥）是 V2 的交互入口。**你只跟主会话说话**；子会话是物理进程，
不直接找你。一次激活管一个 run 的规划、派工、验收、发货全程。

与创作体系（`/producer` `/writer` `/artist`）和机场体系（`/pilot` `/tower` `/ace`）
严格分开：V2 只做代码开发，不调用它们的角色，也不共用状态。

## 铁律

1. **能脚本就脚本**：状态推进、槽位、worktree、touchset、预算、续跑全走
   `travel` 命令；**绝不手改 `.coding/runs/*/state.json`**。
2. **只在门点停**：手动挡在 G0/G1/G2 停；`/warp` 自动挡由门卫子代理自动批门，只在红线/异常时停。
3. **验收读 diff**：子会话报告是 claim，不是事实；`travel review` 的门卫子代理读实际 diff 再裁决。
4. **子会话不发货**：worker 与 reviewer 都不 push/merge；发货只由主会话在门点后执行。

## 流程

```
/warp <任务>
  → travel run "<任务>"            # 开 run（并发满则 queued）
  → 拆任务图 → travel plan        # 每任务：brief / tier / deps / touchset / ac / ui
  → G0：把任务图给用户看 → travel gate <run> g0 approve
  → （有 UI）G1：设计规格 → travel gate <run> g1 approve
  → 循环：
      travel next                 # 取 ready 任务
      travel spawn <run> <task>   # 起 worker 子会话
      travel report <run> <task>  # 收报告 + diff 对账
      travel review <run> <task>  # 门卫子代理独立只读审查（新上下文）
      读裁决 → travel accept 或 travel return --defects "..."
  → 全部 accepted → G2：travel gate <run> g2 approve   # merge → 收尾门 → push → 关票
```

## 命令速查

| 命令 | 作用 |
|---|---|
| `travel run <issue> [--fleet id] [--ships 1-3] [--crew 1-5] [--urgent] [--base main] [--depends r-x]` | 开 run（舰队） |
| `travel adopt <issue>` | 晚激活：接管当前未提交改动为 baseline |
| `travel plan <run> --file tasks.json` | 写任务图 |
| `travel gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门；reject 有回流 |
| `travel next [run]` | 下一个可派任务（含 touchset / 槽位判断） |
| `travel spawn <run> <task> [--adapter ...]` | 起子会话 |
| `travel report <run> <task> [--timeout]` | 等 worker 结束，收报告，校验 files_changed ⊆ git diff |
| `travel review <run> <task> [--apply] [--adapter]` | 门卫子代理独立只读审查，产出 accept/return |
| `travel accept\|return\|reopen <run> <task>` | 验收 / 打回 / 撤销 |
| `travel resume <run>` | 从 state.json 续跑 |
| `travel status [--html]` | 看板（在做 / 在等 / 已完成） |
| `travel doctor` | 状态与 git 对账 |
| `travel gc [--all]` | 清理已收尾 worktree 与分支 |
| `travel stop <run>` | 停 run，保留状态 |
| `travel warp <issue> [--ships 1-3] [--tasks f.json]` | 曲速全自动：自动批门 + 施工，**不发货**（停在 closing） |
| `travel jump <issue> [--ships 1-3]` | 跃迁全自动：加急 + 自动发货，唯一有发货权的全自动入口 |
| `travel assimilate <branch> --approve` | 吞并外部分支（必须显式 `--approve`） |
| `travel drive [--run r] [--adapter a] [--review-adapter b]` | 脚本无人值守跑完整条流水线 |
| `travel serve [--port 8765] [--board-dir …] [--token …] [--drive]` | 本地监工服务：只读 API + 受控 gate/stop/drive；默认只绑 127.0.0.1，Windows 静默 |
| `travel harness [check\|list\|verify <名>\|trust <名>]` | 宿主适配器：看现状 / 清单 / 真跑用例验收 / 登记信任（换宿主时自举用） |
| `travel feishu [status\|doctor\|triage <文本>\|board\|send-test\|run]` | 飞书桥：配置现状 / 自检 / 分诊预览（不产生副作用）/ 看板 JSON / 发测试消息 / 起桥 |

## 本地监工服务

`travel serve` 起一个只用标准库的本地 HTTP 服务：

- `GET /api/health`、`/api/runs`、`/api/runs/<id>`、`/board.json`；
- `POST /api/runs/<id>/gate`、`/api/runs/<id>/stop`、`/api/drive`；
- 写端点走 `travel` 命令，不直接改 `state.json`；
- 默认只绑 `127.0.0.1`；要防本机其他进程可加 `--token`；
- **Windows 不许弹黑窗**：子进程用 `CREATE_NO_WINDOW`，后台用 `pythonw` / 计划任务
  （`wscript //B` + `.vbs`），不用 `start /min python`。

## 宿主自举（换宿主时）

worker 是**物理子进程**，由「宿主适配器」启动。内建三个：`claude-cli`（参考实现）、
`mock`（测试）、`generic`（stdin/stdout 兜底，需 `TRAVEL_GENERIC_CMD`）。

换到一个还没有适配器的宿主时，**由当前 AI 自己写**，内核不用为新宿主打补丁：

| 步 | 命令 | 判据 |
|---|---|---|
| 1 | `travel harness check` | 看当前会选谁、适配器目录在哪 |
| 2 | 按契约写 `<项目根>/.coding/adapters/<宿主>.py` | 实现 probe/spawn/wait/read/kill，能力如实申报 |
| 3 | `travel harness verify <宿主>` | 用例全过：能写、能报、能读（只给目录）、只读时工作目录零改动 |
| 4 | `travel harness trust <宿主>` | 登记文件 sha256；**没登记的文件不会被 import** |
| 5 | `.coding/config.json` 写 `{"adapter": "<宿主>"}` | `check` 里的 selected 变成它 |

契约正本：[host-adapter.md](host-adapter.md)（本技能目录）。申报 `supportsTools=false` 的适配器，
`travel spawn` 会打警告——那种适配器只适合只读审查，不要拿来跑发货链路。
显式点名（`--adapter`／`TRAVEL_ADAPTER`／配置）的适配器起不来会直接报错，不会偷偷换回别的宿主。

## 飞书桥

`travel feishu run` 起一个常驻桥：飞书消息 → 分诊（确定性动作脚本直做；需要判断的醒一次 AI）→
回话；run 状态变化自动发卡；卡片按钮走 `travel serve` 的受控端点，**不直写 state.json**。

- 配置：`<数据根>/kai-mode/feishu.json`（机器级）；项目级 `.coding/feishu.json` 可选覆盖
- 默认全拒：`allow.users` / `allow.chats` 空 = 谁都不认
- 对话模式默认开：同一条飞书会话续同一个宿主会话；空闲 45 分钟 / 20 轮 / 6 万 token 任一触发即换新
- 自助排查：`travel feishu status`、`travel feishu triage <一句话>`

## 任务图

```json
{"tasks": [
  {"id": "t1", "title": "短名", "brief": "自包含任务书", "tier": "light|medium|careful|heavy|fable",
   "deps": ["t0"], "touchset": ["src/x/**"], "ac": ["可核的完成定义"], "ui": false}
]}
```

- `touchset` 重叠的任务不会并发；跨 run 重叠也排队。
- `ui: true` 才会触发 G1。
- `deps` 未 accepted/abandoned 时任务不 ready。

## 失败处理

| 现象 | 动作 |
|---|---|
| 子会话超时/崩溃 | `travel spawn --retry` 重试一次；再失败转 blocked |
| 报告解析失败 | 读 diff 自判，不重试 |
| 报告与 diff 不符 | 视为 partial，必须读 diff |
| 连续 return 3 轮 | 转 blocked，叫醒人 |
| merge 冲突 | 脚本自动 rebase 一次；仍冲突 → blocked |
| 发货失败（收尾门红 / push 被拒） | run 转 blocked，产出保留 |

## 曲速模式（/warp）

`/warp <任务> [--tasks tasks.json]` = 全自动挡：施工全程 AI 自推，门卫代理批 G0/G1/G2，只在红线/异常时停。
- `--tasks` 可在开 run 时直接写任务图；并发满时 run 排队，槽位空出后自动提升（`promote_queued`）。
- 舰队节制：舰船数（run）1–3（`--ships`，warp/jump 默认 2、`run` 默认 1）、船员数（并发子代理）1–5（`--crew`，默认 5），按舰队独立计数；
  不同舰桥 / agent 框架互不抢占，touchset 冲突检测仍全局。
- `--ships N` 一次创建 N 艘舰船（各自 worktree + 分支），共享 `fleet_id`（`<宿主>-<时间戳><后缀>`）；
  混搭曲速/跃迁时给两条命令传同一个 `--fleet <ID>`。
- return 上限 3 轮，failed 重试 2 次，merge 冲突自动 rebase 一次。
- 发货权只归加急：普通 `/warp` 停在 closing（next_action 注明等发货），由舰桥或人工 `gate g2 approve` 发货；
  `/jump` 才自动发货 = merge → 收尾门 → push → 关票，全脚本化。
- push 目标默认 `dev`；仓里没有 dev（如本仓已并入 main）则用当前分支。
- issue 引用自动识别：任务文本里的 `#123` 或 GitHub issue URL 会自动关票；识别不到则跳过，不阻塞发货。
- 吞并他人成果：`travel assimilate <branch> --approve`，必须用户同意后才执行。
- `travel drive` 是零干预驱动：脚本循环 spawn → report → review → accept，槽位空出自动提升排队 run，直到全部终态或 blocked。
- `travel drive --review-adapter mock` 可让审查走更便宜的适配器（生产默认与 worker 相同）。

## 跃迁触发（/jump）

`/jump <任务>` = 跃迁（加急）：走加急预留槽，不抢占普通 run，touchset 重叠时排队到该任务验收。
未显式触发时一律问用户是否用 `/jump`（跃迁）。

## 触发策略

未显式指定命令时，一律先问用户：「是否用 `/jump` 跃迁？」
用户确认后再执行；不自行决定。

## 与其他体系

- V1 机场体系：并存，命令与状态都不共享。装 V2 不动 V1。
- 创作体系：V2 只管代码；作品交付走 `/producer` 等。
- 看板：`travel status` / `travel status --html`；不接 V1 航班信息。
