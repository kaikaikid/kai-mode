---
name: flight-info
status: active
approved_by: human:kaikaikid
approved: 2026-10-24
sources:
  - resource: "项目配置 paths.handoff_dir 下的 60-board 目录"
    note: "看板数据层：跨 agent 卡片；本技能是它的展示层，不持有状态"
  - resource: "GitHub Issues"
    note: "票状态正本；本技能只读，不写"
description: >
  看板展示形态（Flight Information）：一块板 = 一个 SQLite 库 ＋ 一份板配置 ＋ 两个产物。
  采集各源 → 归一化落库 → 判阶段 → 出 board.json（AI 只读，≤25KB）与 index.html（人读）。
  模块化：db / stage / sources / collect / render / config 单向依赖，源按类型插件式增删。
  刷新靠 git 钩子打脏标记 ＋ 30 分钟脚本定时任务（`--max-age` 兜底 GitHub 侧更新）＋ 页面自刷新，
  零 token、跨 agent；任一源失败只降级点名，不整页崩。
  触发：/航班信息、刷新航班信息板、看现在在飞什么、给这个仓装一块板。
version: 1.5.0
updated: 2026-10-27
allowed-tools: Bash(python:*) Bash(git:*) Read Write
compatibility: Requires python3 (stdlib only), git
metadata:
  alias: 航班信息
---

# flight-info —— 看板展示形态

> 「航班信息」是中文口令（`/航班信息`）；本技能正名 `flight-info`（Flight Information）。
> 只依赖 Python 标准库（`sqlite3` 在内），不引第三方。

## 1. 三层里它占哪层

| 层 | 落点 | 谁读 |
|---|---|---|
| 数据层 | `handoff/60-board/`（卡片） | AI 读写，人不看 |
| **展示层（本技能）** | 板库 `<output.root>/<板名>/`：`board.db` ＋ `board.json` ＋ `index.html` | 人读 HTML；AI 只读 `board.json` |
| 触发层 | git 钩子（`post-commit`/`post-merge`）＋ 系统闹钟 | 零 token、跨 agent |

**单向**：展示层只读各源、只写板目录；不改票面、不改日表、不写回卡片。

## 2. 模块地图（依赖只能向下）

| 模块 | 职责 | 不许做 |
|---|---|---|
| `flightinfo/db.py` | **唯一**碰 SQLite：连接、迁移、写入、读取 | 不许解析外部格式 |
| `flightinfo/stage.py` | 解释 `stage_rules`，判阶段 | 不许 IO、不许连库 |
| `flightinfo/sources/*.py` | 一个源一个文件，只读外部世界 → 归一化记录 | 不许连库、不许互相 import |
| `flightinfo/collect.py` | 跑源 → 记账 → 按 uid 合并 → 判阶段 → 落库 | 不许自己拼 SQL |
| `flightinfo/render.py` | 只读库 → `board.json` ＋ `index.html` | 不许采集、不许写库 |
| `flightinfo/config.py` | 板配置加载 / 校验 / 定位落点 | 不许写盘 |
| `schema/*.sql` | 表结构正本（可重复执行） | — |

加一个**航班形态**的源（产出 `flights`/`schedules`）＝在 `sources/` 放一个实现 `collect(cfg, ctx)` 的模块 ＋ 在 `flightinfo/sources/__init__.py` 的 `REGISTRY` 加一行。**其他文件一个字都不用改。**

加一个**非航班形态**的源（如 `handoff-index`，产出 `handoffs` 这类自定义键）要四件事：源模块返回该键 → `collect.run_sources` 汇总该键并调 `db.replace_*` 落库 → `db.py` 加读函数 ＋ `schema/00X-*.sql` 建表 → `render.py` 加段落。`run_sources` 是显式按键名取的（不是自动透传），所以键名要和落库/渲染函数对齐。

## 3. 板配置字段

`board.config.json`（样例见 `templates/board.config.example.json`）：

| 字段 | 必填 | 语义 |
|---|---|---|
| `name` | 是 | 板名，**会成为目录名**；禁 `\ / : * ? " < > |` |
| `title` / `subtitle` | 否 | 页面标题 / 眉标 |
| `repo` | 否 | `owner/name`；空 ⇒ 从目标仓 `git remote` 解析 |
| `output.root` | **是** | 板库根，**相对项目仓根**；无缺省值，缺了报缺件 |
| `sources[]` | 是 | 每项 `{id, type, ...}`；`type` 见下表 |
| `stages[]` | 是 | 阶段链 `{key,label}`，按顺序 |
| `off_chain_stages[]` | 否 | 链条外阶段（可领 / 挡住） |
| `stage_rules[]` | 是 | 判据，**按顺序取第一条命中，最后必须是 `else`** |
| `next_text` | 否 | `阶段 → 下一步文案` |
| `direction` | 否 | `{template, variants[{when,template}]}`，占位符用 KPI 名 |
| `summary` | 否 | `max_flights` / `max_bytes`（默认 25600）/ `flight_stages[]` / `flight_fields[]` |
| `stale_after` | 否 | **停滞阈值按阶段分档**：`{"flying":3,"review":2,"to_ship":1,"_to":"stale"}`。命中即从该阶段降级成 `_to`（默认 `stale`），并在 `why` 里写明「原在飞 N 天没动」、`prev_stage` 留原阶段。不给某阶段设阈值＝该阶段永不判停滞。理由：待发货压一天就该喊，排队一周不动是常态——一刀切 3 天会把两类混成一锅。 |
| `owner_infer` | 否 | 阶段 → 推断掌机（默认 `{"to_ship":"tower"}`：发货权归塔台独占）。推断出来的掌机在界面上带「推」角标——事实与推断不许长一个样。 |
| `summary.ai_why_chars` | 否 | AI 面判据截断（默认 160）。全文在人面展开行里。 |
| `summary.ai_note_chars` | 否 | AI 面排班备注截断（默认 160）。实测一条备注能到 2 千字，占 board.json 65% 预算、把航班挤到只剩 2 条。 |
| `summary.ai_label_max` | 否 | AI 面每票标签上限（默认 6，超出折成「…共 N 枚」）。 |
| `sources[].lanes` | 否 | **书写顺序＝页面上车道块的左右顺序**（如 `["main","deputy","second","ace"]` ⇒ 主机长在左）。以前按字母排，`deputy` 天然压到 `main` 前面，把"主道优先"读反了 |
| `view.urgent` | 否 | 加急腿（王牌飞行员）：`{"lanes":["ace"],"label":"ace-queue"}`。两条信号**任一成立**即上「紧急任务」段——① 该车道的日表行；② 开放票带该标签。ace 车道的排班行**不进**「塔台排班」（免得挤占排班行数额度，额度见协议 §零）。王牌执行帽口径见协议 §一，按该口径判「超编」（授权并行后以人工核对为准）。空态自带亮起方式，不许一片空白让人以为坏了（D-05） |
| `view.focal_stage` | 否 | 哪一段着赭色，默认 `to_ship`；该段为 0 张时**不亮** |
| `view.font_source` | 否 | `system`（默认，零网络）/ `web`（引 Google Fonts） |
| `view.metrics[]` | 否 | `{key,label}` 次级读数；不写＝航班总数 / 今日收尾 / 今日排班 |
| `view.labels` | 否 | 覆盖界面文案（`flights`/`ticket`/`content`/`stage`/`owner`/`lane`/`schedule`/`note`…） |
| `view.eyebrow` | 否 | 页头小标前缀，缺省只有 `RUN <run_id>` |

**源类型**

| type | 参数 | 读什么 |
|---|---|---|
| `board-cards` | `path`（缺省 `paths.handoff_dir`） | `handoff/60-board/{open,claimed,done}/` 卡片的 frontmatter |
| `tasks-table` | `path`（缺省 `paths.day_tables_dir`）/ `include`（默认 `*-main.md`／`*-deputy.md`／`*-second.md`／`*-ace.md`）/ `lanes`（默认 `main`／`deputy`／`second`／`ace`） | 日表 markdown：列表行 `- [ ] #12 事 \| 备注`，或表格 `\| 序 \| 票号 \| 里程碑 \| 一句话 \| 备注 \|`（两种都认，可混用） |
| `git-worktrees` | `branch_prefixes`（默认 `["exec/","land/"]`；也认单个 `branch_prefix`；`hotfix/` 不在此源，走王牌日表） | 本地 worktree/分支 → 在飞证据 |
| `github-issues` | `repo` / `state`（`open`\|`closed`\|`none`）/ `limit` / `include_closed`＋`closed_limit` | 票面（`gh` 不可用则降级）。`include_closed: true` 顺带拉已关票——残留 `exec/` 分支只有靠「已关」才能归到已收尾 |
| `handoff-index` | `path`（缺省 `paths.handoff_dir`）/ `slots` / `limit`（默认 8） | 交接日报索引：只读 `handoff/<槽>/<YYYY-MM>/*.md` 的文件名＋首行标题，**不搬正文**；渲染成可点相对链接的「交接日报索引」区 | **文件名日期两种写法都认**：`YYYY-MM-DD-*.md` 与跨角色件常用的 `HANDOFF-YYYYMMDD-*.md`；解析不到日期会沉到月初、被 `limit` 挤掉（2026-10-27 实测：两份 HANDOFF-* 在板上完全隐形）。月/日做合法性校验，`12345678.md` 一类不当日期 |
| `ship-queue` | 无（读 `paths.state_dir`） | **塔台待发货队列**：读 `.git/<框架>/ship-queue.json`（正本写者＝塔台 `ship-queue.py sync`），出 pending/hotfix/invalid 计数与逐票行；文件不在 ⇒ `absent`（「塔台还没跑过 sync」），不猜。不产生航班记录，只供「待发货队列」区块 |
| `tower-token` | 无（读 `paths.state_dir`） | **塔台令牌**：读同目录 `tower-token.json`，出持牌人／心跳龄／是否已被判死；只做状态条的一枚灯，不改任何阶段判据 |

**`stage_rules.when` 取值**：`state_closed` `label_equals` `comment_contains` `branch_exists` `table_note_contains` `assignee_exists` `no_issue` `else`。
`no_issue`＝有 `exec/` 分支但 GitHub 认不到这张票（`url` 空）⇒ 判「残留分支」。
**判据按顺序取第一条命中**，所以 `no_issue` 必须排在 `branch_exists` **前面**，否则残留分支永远先被 `branch_exists` 判成在飞（2026-10-26 实测踩过）。
`why` 可带占位 `{branch}` `{note}` `{assignee}` `{label}`。

**KPI 名**：`in_flight`（在飞+审查，**不含停滞**）`to_ship` `ready` `queued` `ready_plus_queued` `hold` `stale`（停滞）`unresolved`（残留分支）`closed` `closed_today` `open` `total` `planned`；
外加 `by_stage`（`{阶段key: 张数}`，阶段轨用它，自定义阶段也认）。

## 4. 版式（`index.html`）

皮肤＝**KWP 看板皮肤**（`anthropics/knowledge-work-plugins`：`data/skills/build-dashboard` 的
KPI 卡／图表／页脚时间戳方法论 ＋ `productivity/skills/dashboard.html` 的暖白陶橙配色与看板列）。
参考副本在框架仓外 `tools/kwp-reference/`（只作比对，不入库）。
2026-10-28 换骨：壳层＋左侧纯导航＋Bento 读数＋**看板列（列＝阶段、卡＝票）**＋列表视图。
改皮肤只改 `flightinfo/render.py` 顶部的 `CSS` 常量（`:root` 与暗档块），不动逻辑。

| 件 | 规格 | 撞了算谁的 |
|---|---|---|
| 色 | 全用 token：纸底 `--bg-primary` #faf9f5 ／ 次层 `--bg-secondary` #F5F4EF ／ 卡片白 ／ 文字 #141413 / #5c5c5a / #8c8c8a ／ 强调（陶橙）`--accent` #D97757 ／ 线 `--border` #e5e4df ／ 告警 `--negative` #C4553F。**使用面禁硬编码色值** | KWP 皮肤 |
| 暗档 | `html[data-theme="dark"]` 整块覆盖，起手跟随 `prefers-color-scheme` | — |
| 圆角 | 列 12 / 卡 10 / 段卡 10 / 面板 14 / 胶囊 pill | — |
| 壳几何 | 外留白 12 · 栏间 16 · 侧栏 216 · 内容上限 1400 · 卡片各自描边（KWP 用 1px 边框而非阴影分层） | — |
| 左侧栏 | **纯导航**：品牌行 → 段导航 → 按阶段筛 → 栏底口径折叠。读数、源灯、搜索框不许进侧栏 | 用户令 |
| 主区次序 | 页头（眉标＋h1＋快照龄＋未收尾读数）→ 工具排 → 降级旗 → Bento → **紧急任务（最前）** → **塔台排班（三车道，主左副中二副右）** → **待发货队列** → 航班（看板列／列表）→ 里程碑 → 交接日报 → 趋势 | 用户令 |
| 看板列 | 列＝阶段链（排队／在飞／审查／待发货／已收尾）；链外阶段（停滞／卡点／可领／已派／残留）**只有真有票才成列**。列宽 280–340、列内滚动、列头带计数徽章；**卡只读不可拖**（板不改状态） | 用户令 |
| 卡片 | 票号（有 `url` 出链）＋标题＋徽章 → 掌机＋阶段标签＋里程碑＋距今 → 判据一行（截 110 字） | — |
| 视图切换 | 工具排「看板／列表」两档，选择存 `localStorage`；列表档＝旧四列表格（含展开行） | KWP `.view-toggle` |
| 工具排 | 搜索（⌘K）· 看板/列表 · 展开细节 · 外观 · 刷新。**带底件只 1 枚** | — |
| 待发货队列 | 读 `paths.state_dir/ship-queue.json`（塔台写）；每行＝票号／ac／sha／分支／挂起原因。读不到明说读不到，不装空 | 用户令 |
| 状态条 | 底部固定：源健康灯 ＋ **塔台灯**（持牌人＋心跳龄，读 `paths.state_dir/tower-token.json`）＋「只读各源」 | — |
| 告警色 | 小字不直接染红（#C4553F 对白底不足 4.5:1）：停滞交给红点，快照过期交给下划条 | WCAG AA |
| 自刷新 | 三档：① http 下每 60 秒比对 `board.json.generated_at`，变了就重载；② 手动「刷新」按钮重读磁盘；③ 重建由钩子/定时器/`refresh.vbs` 触发。页头常驻「快照 … · N 分钟前」，超 15 分钟加下划条 | 用户令 |
| 零网络 | 默认 `font_source: system`：不外链字体与任何资源，离线可看；筛选态走 URL hash；只有「看板/列表」视图偏好写 `localStorage`（读取失败不影响功能） | — |

## 5. 命令

```bash
# 建一块板（校验 → 建目录 → 留档配置 → 出首版）
python scripts/init_board.py --repo-root <仓根> [--config <json>] [--name <板名>] [--force]

# 刷一块板（采集 → 落库 → 出两个产物）
python scripts/refresh.py --repo-root <仓根> --config <板目录>/board.config.json [--quiet] [--no-network]

# 装有脏才刷的 git 钩子（默认干跑，--apply 才落盘）
python scripts/install_hook.py --repo-root <仓根> [--apply] [--remove --apply]

# 一键接上自动更新（三钩子 ＋ 30 分钟脚本定时任务 ＋ 人工入口；见第 5.5 节）
python scripts/install_auto.py --repo-root <仓根> --config <板配置> [--interval 30] [--apply] [--remove --apply]

# 给闹钟/人工用的幂等刷新（无脏且板龄未超限就跳过）
python scripts/refresh_if_dirty.py --repo-root <仓根> --config <板配置> [--force] [--max-age <分钟>]
```

产物落 `板目录/`：`board.db`（库）｜`board.json`（AI 面，有字节预算）｜`index.html`（人面，未收尾全量不截断）｜`history.jsonl`（每轮一行 KPI，趋势线的正本；同一 `run_id` 幂等，只留一行）。

### 5.5 让板「活」起来（自动更新）

板默认是**手动**刷的。要自动更新，跑 `install_auto.py --apply` 会收齐三层：

1. **git 钩子**（`post-commit` / `post-merge` / `post-checkout`）：写进仓的**有效**
   `core.hooksPath`（本仓是 `.githooks`，不是 `.git/hooks`；两个安装器用同一把尺）。
   钩子只往 `.git/flight-info-dirty` 写时间戳，**不同步刷、不阻塞 git**（退出码恒 0，fail-open）。
2. **人工入口** `refresh.vbs`（复制到板目录）：双击强制重建一次（无视脏标记）。
   页面「刷新」按钮做 `location.reload()` 重读磁盘；真正重建走 vbs 或定时器。
3. **定时任务**（`schtasks`，仅登录时运行，默认每 **30** 分钟）：`refresh_task.bat`
   → `wscript //B refresh_tick.vbs` → `refresh_if_dirty.py --max-age <interval>`。
   - **零黑窗**：全链路 wscript（GUI 子系统）＋ `sh.Run cmd, 0, True`；
     不用 `start /min python`（仍会闪控制台）。
   - **零 token**：纯脚本，不起 AI 会话；用当前用户上下文、不写 `/RP`（不存密码）。
   - **`--max-age` 兜底**：GitHub 的评论/标签更新**不产生本地提交**，钩子永远看不见；
     板龄超过 interval 就强制刷一次，治「GitHub 早更新了、板上还是旧的」。

> **本机实测**：部分 Windows 安全策略禁止 `schtasks /Create`（报错 `Access is denied`），
> 此时第 ③ 层建不出——`install_auto.py` 把它降级成告警、不阻断整次安装；
> 钩子与手动刷新仍可用。要周期刷新，在能建任务的环境重跑即可。
>
> 定时任务用系统账号跑时 `gh` 读不到你的 GitHub 登录态（票面源降级）；
> 用当前用户 ＋ 仅登录时 ＝ `gh` 正常、又无 token。
>
> **平台边界（体检 L12）**：第 ②③ 层（`refresh.vbs`／`schtasks`／`wscript`）目前只有 Windows 实现。
> 「跨 agent」指不依赖某个 AI 宿主，**不是跨 OS**——非 Windows 环境用第 ① 层钩子 ＋ 手动
> `python refresh.py`（或自建 cron 调 `refresh_if_dirty.py`），`--max-age` 兜底仍然成立。

## 6. 退出码与降级

| 码 | 含义 |
|---|---|
| `0` | 板已生成（**含降级**） |
| `2` | 配置/参数错（逐条打印错在哪） |
| `3` | 写盘失败 |

- **`0` 只表示「板生成了」，不代表数据全好** —— 判据读 `board.json` 的 `sources`（`ok`/`absent`/`skipped`/`fail`），别拿退出码当绿灯。
- 单源炸 ⇒ 该源记 `fail` 并点名，其余照出板。
- 票源塌 ⇒ 退化成只画日表与卡片里的票。
- 摘要层超 `max_bytes` ⇒ 从尾部丢票并置 `counts.flights_truncated`。**这条只管 AI 面**：人面（`index.html`）走 `all_open`，未收尾全量出、不截断。以前两本账混在一起，人的屏幕被 AI 的上下文预算管着——正本只画 12 行、页脚小字写「余量见 board.json」，而 board.json 里也只有那 12 行。
- 字节预算**按写盘形态量**（`indent=1`）。以前按紧凑 JSON 量、按美化写盘，量少约 20%，实测超预算 2.3 KB 还自认合规。
- git 钩子**只打标记**，退出码恒 0，绝不阻塞 commit。
- 任一源非 `ok` ⇒ 人面页头出**降级旗**（`board.json` 的 `degraded[]` 同步点名），写清哪个源、什么状态、少了什么。静默少票比报错更坏。

## 7. 权限与禁区

**可以**：读日表、卡片、票面、分支；写板目录（库、两个产物、配置留档）；装/卸自己的 git 钩子。

**不可以**：写票面/评论/标签；写日表（塔台唯一写者）；写 `handoff/60-board/` 卡片（改用 `scripts/handoff-board.py`）；
改目标仓源码；把 `index.html` 当数据源解析（AI 只读 `board.json`）。

## 8. 验证命令

```bash
python -m unittest discover -s tests -v          # 单元测试（含端到端；项数以实际收集为准，不写死）
python scripts/init_board.py --repo-root <临时仓>  # 自证：装完能用
python scripts/refresh.py --repo-root <临时仓> --config <板配置> --no-network
```

## 9. 正本

| 件 | 在哪 |
|---|---|
| 表结构 | [`schema/001-init.sql`](schema/001-init.sql) |
| 板配置样例 | [`templates/board.config.example.json`](templates/board.config.example.json) |
| 阶段判据实现 | [`flightinfo/stage.py`](flightinfo/stage.py) |
| 源清单 | [`flightinfo/sources/__init__.py`](flightinfo/sources/__init__.py) |
| 看板卡片格式 | 项目内 `handoff/60-board/README.md` |
