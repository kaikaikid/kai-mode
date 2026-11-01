# 0029 V2 监工面：看板优先，服务按需

## Status

**accepted** —— 2026-11-01 用户拍板「新开分支 v3 来做；任务一步步来细化，逐步推进。
每完成一个阶段，你自己做一个审查。通过了再继续往下拓展」。
执行分支：`v3`（从 `dev` 切出）。

## Context

- **V2 看不见**：`travel status` 只有终端表；`travel status --html` 只有三列 run 卡片，
  没有任务下钻、gate、session、健康。run 一多，用户只能回终端逐条查。
- **flight-info 已经成熟**：一板一库（SQLite）＋ `board.json`（AI 面）＋ `index.html`（人面）＋
  源注册表 ＋ 阶段规则 ＋ git 钩子/定时任务/页面自刷新三层刷新；单源失败只降级，不整页崩。
- **DeepSeek 的 service/Panel 不能直接缝合**：`dsh-superagent` 是 DSH bundle，绑定
  Cordis 插件、TypeScript/pnpm、React SPA、SQLite、`tmux`/`fcntl`；搬到 kai-mode 等于
  把整个 DSH 搬进来，且 Windows 不兼容。能借的是信息架构，不是代码。
- **V2 控制面已经具备被服务化的条件**：`state.json` 原子写（`v2/coding/state.py` `_atomic_write`）、
  跨进程文件锁（`lock()`）、worker 以 pid/heartbeat 落盘（`v2/coding/adapters.py`）、
  `travel drive` 已是无人值守循环。缺的只是展示层。

## Decision

### D1 分支与节奏

- 在 `v3` 分支实施，不直接改 `dev`。
- 按阶段推进：每阶段完成 → 自审（测试、doctor、人工复核）→ 通过才进入下一阶段。
- 阶段顺序：Phase 0 契约 → Phase 1 `coding-runs` 源 → Phase 2 人读面 → Phase 3 轻服务（按需）。

### D2 看板优先：给 flight-info 加 `coding-runs` 源

- 新增 `board/skills/flight-info/flightinfo/sources/coding_runs.py`，只读
  `<repo_root>/.coding/runs/*/state.json`，一个 run → 一条 flight 记录（`uid = run:<run_id>`）。
- 不 import `v2`（板是独立安装件，项目里可能没有 `v2` 包）；容错解析，坏 JSON 只让该源降级。
- 阶段映射用标签 `v2:queued|flying|review|to_ship|hold|closed`，板配置把对应规则排在
  `no_issue`／`branch_exists` 之前，避免 V2 run 被误判成残留分支。
- `uid` 用 run id 而不是 issue 号：同一 issue 可能开多个 run（重跑、拆分、加急），
  issue 做 uid 会互相覆盖。同一件事在板上可能两行（issue 源 + coding 源），
  Phase 2 在渲染层按 ticket 合并显示。

### D3 人读面：三问式监工面

`board.json` 增加 `coding` 段（fleet 用量、needs_person、runs 摘要、counts），
`index.html` 增加「需要人 / 健康 / run 详情」三段；打开板先回答：

1. 现在需要我做什么？（blocked、gate pending 超时、failed session、发货失败）
2. 系统健康吗？（源状态、控制面状态、worker 存活、看板新鲜度）
3. 这件事的来龙去脉？（issue、任务图、gate、session、report、ship）

`board.json` 保持字节预算：`coding.runs` 最多 20 条，`needs_person` 最多 8 条，完整任务图
只走服务 API 或 `state.json`，不塞进 AI 面。

### D4 轻服务按需：不搬 DSH

- 只在需要事件驱动接活、无人值守长跑或"点按钮"执行 gate/drive/stop 时才做。
- 形态：`v2/coding/service.py` + `travel serve`，只用 Python 标准库
  （`http.server` + `threading` + `subprocess`）；绑 `127.0.0.1`，默认端口 `8765`；
  单实例 pid 锁；写端点一律调用 `travel` 命令，不直接改 `state.json`。
- 不引入 FastAPI/React/WebSocket/多用户/远程访问；60 秒轮询足够。
- Windows 用 `pythonw`/计划任务，POSIX 用 `nohup`/systemd；不依赖 `tmux`/`fcntl`。

### D5 Windows 静默执行：不许弹黑窗

用户 2026-11-01 明令：**任何命令行黑窗都不许弹出来，必须静默执行。**

- 服务/看板/定时任务在 Windows 上起的每一个子进程，都必须走 GUI 子系统或隐藏窗口：
  - Python 子进程：`subprocess.run(..., creationflags=subprocess.CREATE_NO_WINDOW)`
    （Python 3.7+；Windows 专用；POSIX 忽略）。
  - 定时任务：沿用 flight-info 已有的 `wscript //B` + `.vbs` 方案，
    `install_auto.py` 的 `refresh_task.bat → refresh_tick.vbs` 是正本；
    不用 `start /min python`，不用可见的 `cmd /c`。
  - 人工入口：`refresh.vbs`（双击/按钮）同样走 `wscript`。
- 测试与自审必须覆盖：Windows 上启动服务、刷新看板、调用 `travel` 时，
  任务栏/桌面不出现新的控制台窗口。
- 例外：用户在终端里自己敲 `travel` 命令时，输出留在那个终端里，不另开窗口。

### D6 只借设计，不搬代码

可借：Panel 三问、Ticket 阶段表、HealthBoard（一项一个写者）、Outbox（有序重试、
drop 留痕）、Effects（持久队列、并发上限）、Policy 版本（变更影响在飞 Ticket）。
不借：Cordis/DSH 插件、React SPA、SQLite 作真相源、Feishu、Source/Eval/Mandate 全套。

## Consequences

- **好**：V2 立刻可见；不改控制面；复用 flight-info 的库/渲染/刷新；服务可后置；
  不把 kai-mode 绑到 DSH；Windows 兼容。
- **代价**：`coding-runs` 与 `github-issues` 可能对同一件事各出一行，Phase 2 才合并；
  `board.json` 需要新的字节预算与截断标记；服务多一个进程要管（Phase 3 才有）。
- **不做**：不移植 DSH/Cordis/React；不把 SQLite 当真相源；不做多用户/远程/WebSocket；
  不删除 `travel status --html`（无 flight-info 项目的兜底）。

## 验收

每阶段自审至少包含：

1. 该阶段新增/修改的测试全绿（`pytest board/skills/flight-info/tests`）。
2. `python scripts/doctor.py` 无新增红项。
3. `python scripts/plugin-check.py` 无内容摘要漂移（必要时 `--bump`）。
4. 人工复核：板上能看到 V2 run，阶段映射与 `travel status` 一致，坏 `state.json` 只降级该源。
