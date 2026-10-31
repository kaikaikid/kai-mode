# V2 执行内核 · 宇宙探索剧本

一个 issue 一个 run，主会话规划与验收，物理子会话执行——如舰队远航，各舰独立航行，总指挥只在跃迁门停船。设计正本见
[`docs/design/2026-10-30-v2-execution-kernel.md`](../docs/design/2026-10-30-v2-execution-kernel.md)。

与机场体系（V1）并存，互不影响。命令入口是 `/coding`。

## 安装

在仓库根执行（只装 V2、不碰 V1）：

```bash
# 1. 把 .coding/ 加进 .gitignore（运行期数据不进仓库）
grep -qxF '.coding/' .gitignore 2>/dev/null || echo '.coding/' >> .gitignore

# 2. 把 coding 加到 PATH（可选；也可以直接用 v2/bin/coding）
export PATH="$PWD/v2/bin:$PATH"

# 3. 可选：装 claude-kit 的进度面板，并打 V2 补丁
claude plugin install savvy-progress --marketplace JohnnyVizz/claude-kit -s user -y
python v2/mods/apply.py
```

V1 的安装、定时器、角色技能都不受影响；装 V2 不会卸载或改写 V1。

## 命令

| 命令 | 作用 |
|---|---|
| `coding run <issue> [--urgent] [--base main]` | 开一个 run |
| `coding adopt <issue>` | 晚激活：接管当前未提交改动 |
| `coding plan <run> --file tasks.json` | 写任务图 |
| `coding gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门 |
| `coding next [run]` | 看下一个可派任务 |
| `coding spawn <run> <task> [--adapter claude-cli\|mock]` | 起子会话 |
| `coding report <run> <task>` | 收报告并对账 diff |
| `coding accept\|return\|reopen <run> <task>` | 验收 |
| `coding resume <run>` | 从 state.json 续跑 |
| `coding report <run> <task>` | 等 worker 结束并收报告 |
| `coding review <run> <task> [--apply]` | 门卫子代理独立只读审查 |
| `coding jump <issue> [--tasks f.json]` | 跃迁全自动：自动批门 + 发货 |
| `coding PRI-jump <issue>` | 加急跃迁，走加急预留槽 |
| `coding drive [--run r]` | 无人值守驱动整条流水线 |
| `coding status [--html]` | 看板 |
| `coding doctor` | 状态与 git 对账 |
| `coding gc [--all]` | 清理已收尾资源 |
| `coding stop <run>` | 停一个 run |

## 任务图格式

```json
{"tasks": [
  {"id": "t1", "title": "加导出", "brief": "自包含任务书", "tier": "medium",
   "deps": [], "touchset": ["src/export/**"], "ac": ["测试通过"], "ui": false}
]}
```

## 状态

全部在 `.coding/runs/<run-id>/state.json`，脚本原子写。中断后 `coding resume` 从
`resume.last_accepted` / `next_action` 接着跑。

## 跃迁模式（jump）

`coding jump <issue> [--tasks f.json]`：

- 自动批 G0/G1/G2，门卫子代理（`coding review`）独立只读审查；
- 发货 = 切到 base（默认 `dev`）→ merge → 收尾门 → push → 关票，全脚本化；
- 收尾门在 `.coding/config.json` 配 `{"finish_cmd": "..."}`，留空则跳过；
- issue 文本里的 `#123` 或 GitHub issue URL 会自动关票，识别不到则跳过；
- 并发：普通槽 3 + 加急槽 2，每 run 2 个子代理，全局 10；排队的 run 槽位空出后自动提升。

## 环境变量

| 变量 | 作用 |
|---|---|
| `CODING_MODEL_LIGHT` 等 | tier → 具体模型（留空用宿主默认） |
| `CODING_GENERIC_CMD` | generic 适配器的命令；未设则不启用 |

## 进度面板对接

`savvy-progress` 原版只认 Claude Code 的 in-process subagent；V2 的子会话是物理进程，
原版面板看不到。`v2/mods/apply.py` 给它加一个 2 秒轮询，读 `.coding/runs/*/state.json`
把运行中的任务画成面板行。

插件升级会覆盖 `register.tsx`，升级后重跑一次：

```bash
python v2/mods/apply.py
```

还原：`python v2/mods/apply.py --revert`。
