# V2 执行内核 · 宇宙探索剧本

一个 issue 一个 run，主会话规划与验收，物理子会话执行——如舰队远航，各舰独立航行，总指挥只在跃迁门停船。设计正本见
[`docs/design/2026-10-30-v2-execution-kernel.md`](../docs/design/2026-10-30-v2-execution-kernel.md)。

与机场体系（V1）并存，互不影响。命令入口是 `travel`（兼容 `coding` 别名一版）。

## 安装

在仓库根执行（只装 V2、不碰 V1）：

```bash
# 1. 把 .coding/ 加进 .gitignore（运行期数据不进仓库）
grep -qxF '.coding/' .gitignore 2>/dev/null || echo '.coding/' >> .gitignore

# 2. 把 travel 加到 PATH（可选；也可以直接用 v2/bin/travel）
export PATH="$PWD/v2/bin:$PATH"

# 3. 可选：装 claude-kit 的进度面板，并打 V2 补丁
claude plugin install savvy-progress --marketplace JohnnyVizz/claude-kit -s user -y
python v2/mods/apply.py
```

V1 的安装、定时器、角色技能都不受影响；装 V2 不会卸载或改写 V1。

## 命令

| 命令 | 作用 |
|---|---|
| `travel run <issue> [--fleet id] [--ships 1-3] [--crew 1-5] [--urgent] [--base main]` | 开一个 run（舰队） |
| `travel adopt <issue>` | 晚激活：接管当前未提交改动 |
| `travel plan <run> --file tasks.json` | 写任务图 |
| `travel gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门 |
| `travel next [run]` | 看下一个可派任务 |
| `travel spawn <run> <task> [--adapter claude-cli\|mock]` | 起子会话 |
| `travel report <run> <task>` | 收报告并对账 diff |
| `travel accept\|return\|reopen <run> <task>` | 验收 |
| `travel resume <run>` | 从 state.json 续跑 |
| `travel report <run> <task>` | 等 worker 结束并收报告 |
| `travel review <run> <task> [--apply]` | 门卫子代理独立只读审查 |
| `travel warp <issue> [--ships 1-3] [--tasks f.json]` | 曲速全自动：自动批门 + 施工，**不发货**（停在 closing） |
| `travel jump <issue> [--ships 1-3]` | 跃迁全自动：加急 + 自动发货，唯一有发货权的全自动入口 |
| `travel drive [--run r]` | 无人值守驱动整条流水线 |
| `travel serve [--port 8765] [--board-dir …]` | 本地监工服务：只读 API + 受控 gate/stop/drive |
| `travel status [--html]` | 看板 |
| `travel doctor` | 状态与 git 对账 |
| `travel gc [--all]` | 清理已收尾资源 |
| `travel stop <run>` | 停一个 run |

## 任务图格式

```json
{"tasks": [
  {"id": "t1", "title": "加导出", "brief": "自包含任务书", "tier": "medium",
   "deps": [], "touchset": ["src/export/**"], "ac": ["测试通过"], "ui": false}
]}
```

## 状态

全部在 `.coding/runs/<run-id>/state.json`，脚本原子写。中断后 `travel resume` 从
`resume.last_accepted` / `next_action` 接着跑。

## 本地监工服务（travel serve）

```bash
travel serve --port 8765 --board-dir .design/flight-board
```

- 只读 API：`/api/health`、`/api/runs`、`/api/runs/<id>`、`/board.json`；
- 受控动作：`POST /api/runs/<id>/gate`、`/api/runs/<id>/stop`、`/api/drive`；
- 默认只绑 `127.0.0.1`；写端点可加 `--token` 要求 `X-Travel-Token`；
- 所有写操作调用 `travel`，不直接改 `state.json`；
- **Windows 静默**：子进程用 `CREATE_NO_WINDOW`，定时任务用 `wscript //B` + `.vbs`，
  不弹任何黑窗；后台启动用 `pythonw` 或计划任务。

## 曲速模式（warp）

`travel warp <issue> [--tasks f.json]`：

- 自动批 G0/G1/G2，门卫子代理（`travel review`）独立只读审查；
- 发货 = 切到 base（默认 `dev`）→ merge → 收尾门 → push → 关票，全脚本化；
- 收尾门在 `.coding/config.json` 配 `{"finish_cmd": "..."}`，留空则跳过；
- issue 文本里的 `#123` 或 GitHub issue URL 会自动关票，识别不到则跳过；
- 并发：普通槽 2 + 加急槽 1，每 run 1 个子代理，全局 3；排队的 run 槽位空出后自动提升。

## 舰队 / 舰船 / 船员

```
舰队 (fleet, fleet_id = TRAVEL_HOST 或 git config 推断)
├── 舰船 1 (ship) — 独立 worktree + 分支 travel/<run-id>
│   └── 子代理槽
├── 舰船 2 (ship)
│   └── 子代理槽
└── 舰船 3 (ship, 上限)
    └── 子代理槽
```

| 层级 | 默认 | 范围 | 参数 |
|---|---|---|---|
| 舰船数（每次拉起的 run 数） | 2（`run` 命令为 1） | 1–3 | `--ships` |
| 船员数（子代理并发，跨舰船共享） | 5 | 1–5 | `--crew` |

槽位按舰队独立计数：不同舰桥 / agent 框架互不抢占；touchset 冲突检测仍全局生效。
`--ships N` 会一次创建 N 艘舰船（各自 worktree + 分支），共享同一个 `fleet_id`；
混搭曲速/跃迁时用 `--fleet <同一ID>` 把它们并入同一舰队（总数受 `--ships` 限制）。
用户大白话（「曲速 2 船」「晚上用 3 船」）由舰桥解析成 `--ships`。

## 环境变量

| 变量 | 作用 |
|---|---|
| `TRAVEL_HOST` | 舰队 ID 前缀（宿主标识）；缺省从 git config user.name 推断。ID 形如 `<host>-<时间戳><后缀>` |
| `TRAVEL_MODEL_LIGHT` 等 | tier → 具体模型（留空用宿主默认；`CODING_*` 兼容一版） |
| `TRAVEL_GENERIC_CMD` | generic 适配器的命令；未设则不启用（`CODING_*` 兼容一版） |

## 进度面板对接

`savvy-progress` 原版只认 Claude Code 的 in-process subagent；V2 的子会话是物理进程，
原版面板看不到。`v2/mods/apply.py` 给它加一个 2 秒轮询，读 `.coding/runs/*/state.json`
把运行中的任务画成面板行。

插件升级会覆盖 `register.tsx`，升级后重跑一次：

```bash
python v2/mods/apply.py
```

还原：`python v2/mods/apply.py --revert`。
