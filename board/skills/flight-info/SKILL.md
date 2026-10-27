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
  刷新靠 git 钩子打脏标记 ＋ 有脏才刷，零 token、跨 agent；任一源失败只降级点名，不整页崩。
  触发：/航班信息、刷新航班信息板、看现在在飞什么、给这个仓装一块板。
version: 1.2.0
updated: 2026-10-26
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

加一个**航班形态**的源（产出 `flights`/`schedules`）＝在 `sources/` 放一个实现 `collect(cfg, ctx)` 的模块 ＋ 在 `sources/__init__.py` 的 `REGISTRY` 加一行。**其他文件一个字都不用改。**

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
| `sources[].lanes` | 否 | **书写顺序＝页面上车道块的左右顺序**（如 `["main","deputy","ace"]` ⇒ 主机长在左）。以前按字母排，`deputy` 天然压到 `main` 前面，把"主道优先"读反了 |
| `view.urgent` | 否 | 加急腿（王牌机长）：`{"lanes":["ace"],"label":"ace-queue"}`。两条信号**任一成立**即上「紧急任务」段——① 该车道的日表行；② 开放票带该标签。ace 车道的排班行**不进**「塔台排班」（免得挤占 20 行额度）。协议同刻只许 1 张，超了段头直接报「超编」。空态自带亮起方式，不许一片空白让人以为坏了（D-05） |
| `view.focal_stage` | 否 | 哪一段着赭色，默认 `to_ship`；该段为 0 张时**不亮** |
| `view.font_source` | 否 | `system`（默认，零网络）/ `web`（引 Google Fonts） |
| `view.metrics[]` | 否 | `{key,label}` 次级读数；不写＝航班总数 / 今日收尾 / 今日排班 |
| `view.labels` | 否 | 覆盖界面文案（`flights`/`ticket`/`content`/`stage`/`owner`/`lane`/`schedule`/`note`…） |
| `view.eyebrow` | 否 | 页头小标前缀，缺省只有 `RUN <run_id>` |

**源类型**

| type | 参数 | 读什么 |
|---|---|---|
| `board-cards` | `path`（缺省 `paths.handoff_dir`） | `handoff/60-board/{open,claimed,done}/` 卡片的 frontmatter |
| `tasks-table` | `path`（缺省 `paths.day_tables_dir`）/ `include` / `lanes` | 日表 markdown：列表行 `- [ ] #12 事 \| 备注`，或表格 `\| 序 \| 票号 \| 里程碑 \| 一句话 \| 备注 \|`（两种都认，可混用） |
| `git-worktrees` | `branch_prefix`（默认 `exec/`） | 本地 worktree/分支 → 在飞证据 |
| `github-issues` | `repo` / `state`（`open`\|`closed`\|`none`）/ `limit` / `include_closed`＋`closed_limit` | 票面（`gh` 不可用则降级）。`include_closed: true` 顺带拉已关票——残留 `exec/` 分支只有靠「已关」才能归到已收尾 |
| `handoff-index` | `path`（缺省 `paths.handoff_dir`）/ `slots` / `limit`（默认 8） | 交接日报索引：只读 `handoff/<槽>/<YYYY-MM>/*.md` 的文件名＋首行标题，**不搬正文**；渲染成可点相对链接的「交接日报索引」区 | **文件名日期两种写法都认**：`YYYY-MM-DD-*.md` 与跨角色件常用的 `HANDOFF-YYYYMMDD-*.md`；解析不到日期会沉到月初、被 `limit` 挤掉（2026-10-27 实测：两份 HANDOFF-* 在板上完全隐形）。月/日做合法性校验，`12345678.md` 一类不当日期 |

**`stage_rules.when` 取值**：`state_closed` `label_equals` `comment_contains` `branch_exists` `table_note_contains` `assignee_exists` `no_issue` `else`。
`no_issue`＝有 `exec/` 分支但 GitHub 认不到这张票（`url` 空）⇒ 判「残留分支」。
**判据按顺序取第一条命中**，所以 `no_issue` 必须排在 `branch_exists` **前面**，否则残留分支永远先被 `branch_exists` 判成在飞（2026-10-26 实测踩过）。
`why` 可带占位 `{branch}` `{note}` `{assignee}` `{label}`。

**KPI 名**：`in_flight`（在飞+审查，**不含停滞**）`to_ship` `ready` `queued` `ready_plus_queued` `hold` `stale`（停滞）`unresolved`（残留分支）`closed` `closed_today` `open` `total` `planned`；
外加 `by_stage`（`{阶段key: 张数}`，阶段轨用它，自定义阶段也认）。

## 4. 版式（`index.html`）

皮肤＝本仓 Soft UI 设计系统正本（`soft-design-system/tokens/tokens.css`），**不是**外来 editorial 灰纸。
2026-10-26 刀 2 换骨：壳层＋左侧纯导航＋Bento 读数＋折叠段。改皮肤只改 `flightinfo/render.py`
顶部的 `CSS` 常量（`:root` 与暗档块），不动逻辑。

| 件 | 规格 | 撞了算谁的 |
|---|---|---|
| 色 | 全用 `--soft-*` token：页 `--soft-bg` #FFF ／ 壳画布 `--soft-canvas` #F8F8F8 ／ 面板 `--soft-white` ／ 内嵌 `--soft-inset`（由 `--soft-surface` 派生）／ 品牌 `--soft-accent` 暖黄 #F4D06F（暗档翻 #A594C8）／ danger #F25C54。**使用面禁硬编码色值**，要透明度用 `color-mix()` 从 token 派生 | D-03／D-S03 |
| 暗档 | `html[data-theme="dark"]` 整块覆盖，起手跟随 `prefers-color-scheme`；实测暗档 0 字不达 AA（最低 4.94:1） | — |
| 圆角 | 侧栏与主区 R4 24（壳成员档）、段卡 R3 20、行与导航项 R2 16、标签 R1 12、计数与胶囊 pill | D-S08／2.2.64 封顶 |
| 壳几何 | 外留白 8 · 栏间 8 · 栏内衬 16 · 侧栏 216（`--soft-sidebar-width`）· 核心区内容上限 1120 · **成员之间零分割线**（靠 canvas↔white 反差＋留白） | D-S06 |
| 左侧栏 | **纯导航**：品牌行 → 段导航（排班／航班表／里程碑／日报）→ 按阶段筛（全部／在飞／停滞／待发货／卡点／可领／排队／残留）→ 栏底口径折叠。行间隔 `--soft-nav-gap` 6、行档 28、选中＝内嵌灰一档＋计数徽章转暖黄（E5a，全屏只一枚）。**读数、源灯、搜索框不许进侧栏**；侧栏禁独立滚动（D-11） | 用户令 |
| 主区次序 | 页面级标题 h1 24/700 ＋ 一句读数 → 工具排 → Bento → **紧急任务（加急优先，最前）** → **塔台排班（主左副右）** → 航班信息表（居中）→ 里程碑 → 已收尾 → 日报 → 趋势线 | D-S12／用户令 |
| Bento | 4 枚 1×1（待发货／停滞／卡点／在飞，**可点＝套筛选**）＋ 2 枚 2×1（下一轮方向／今日排班）。比例只准 B-01 四档、一卡一任务、内容卡 ≤R3 20 | B-01／B-05 |
| 工具排 | 搜索钮（⌘K 开浮层，不做常驻输入框）· 展开细节 · 外观 · 刷新。**功能件 ≤6、带底件 ≤1 枚**（名额给唯一主行动） | D-S09／D-22 |
| 航班表 | 四列：票号（有 `url` 就出链）／标题·徽章·判据／阶段链＋掌机（推断带「推」）／**距今**。细节全在展开行（`tabindex=0`＋Enter 可达） | D-07 |
| 紧急任务段 | 暖黄左描边（`box-shadow: inset 3px 0 0 --soft-accent`）——加急属"有事做"不属"坏"，**不用红**（D-S03 色语义）；侧栏导航第一项就是它 |
| 告警色 | **小字不许直接染红**：danger #F25C54 对白底只有 3.26:1，够 28px 大数字与图形、不够 12px 正文。停滞的告警交给红点，快照过期交给红下划条 | WCAG AA／D-S11 |
| 状态条 | 底部 28px，源健康灯（`backdrop-filter` 是 D-S01 两枚受控落点之一），只放读数不装按钮 | D-S01 |
| 降级旗 | 任一源非 `ok` ⇒ 方向句下方一条红边横块点名（`role="alert"`）；全绿不占位 | D-06 |
| 窄档 | ≤1080 Bento 两列；≤860 侧栏转横带（只留一条内容前横带）；≤560 导航段走单行横向滚动＋藏条（正本逃生阀） | D-16／D-17／D-20 |
| 零网络 | 默认 `font_source: system`：不外链字体与任何资源，离线可看；`localStorage` 零使用（筛选态走 URL hash） | — |

**实测基线**（2026-10-26，Kai-vass 板）：侧栏 216px 无独立滚动、h1 起始线 24px、工具排 4 件带底 1 枚、
航班 68 行全量、亮档与暗档不达 AA 的字数均为 **0**、使用面硬编码色值 **0**、外链资源 **0**。

## 5. 命令

```bash
# 建一块板（校验 → 建目录 → 留档配置 → 出首版）
python scripts/init_board.py --repo-root <仓根> [--config <json>] [--name <板名>] [--force]

# 刷一块板（采集 → 落库 → 出两个产物）
python scripts/refresh.py --repo-root <仓根> --config <板目录>/board.config.json [--quiet] [--no-network]

# 装有脏才刷的 git 钩子（默认干跑，--apply 才落盘）
python scripts/install_hook.py --repo-root <仓根> [--apply] [--remove --apply]

# 一键接上自动更新（钩子 ＋ 定时任务 ＋ 人工入口；见第 5.5 节）
python scripts/install_auto.py --repo-root <仓根> --config <板配置> [--interval 15] [--apply] [--remove --apply]

# 给闹钟/人工用的幂等刷新（无脏直接跳过）
python scripts/refresh_if_dirty.py --repo-root <仓根> --config <板配置> [--force]
```

产物落 `板目录/`：`board.db`（库）｜`board.json`（AI 面，有字节预算）｜`index.html`（人面，未收尾全量不截断）｜`history.jsonl`（每轮一行 KPI，趋势线的正本；同一 `run_id` 幂等，只留一行）。

### 5.5 让板「活」起来（自动更新）

板默认是**手动**刷的。要自动更新，跑 `install_auto.py --apply` 会收齐三层：

1. **git 钩子**（`post-commit` / `post-merge`）：写进仓的**有效** `core.hooksPath`
   （本仓是 `.githooks`，不是 `.git/hooks`）。钩子只往 `.git/flight-info-dirty` 写时间戳，
   **不同步刷、不阻塞 git**（退出码恒 0，fail-open）。
2. **人工入口** `refresh.vbs`（复制到板目录）：页面右上角「刷新」按钮指向它，双击也能跑。
   `start "" /min` 隐藏窗口，无黑窗；它强制重生成一次（无视脏标记）。
   ⚠️ 页面是静态 `file://` HTML，浏览器**不能**从按钮直接执行本地 vbs；按钮目前做
   `location.reload()` 重读磁盘上的最新页面。真·重建点按钮后会滞后一轮定时/钩子，
   想立刻重建就用双击 `refresh.vbs`。
3. **定时任务**（`schtasks`，仅登录时运行、隐藏窗口，每 `interval` 分钟）：消费脏标记、调
   `refresh_if_dirty`。**无 token**：用当前用户上下文、`/RP` 不写（不存密码）；
   代价＝登出/关机时不刷。

> **本机实测**：部分 Windows 安全策略禁止 `schtasks /Create`（报错 `Access is denied`），
> 此时第 ③ 层建不出——`install_auto.py` 把它降级成告警、不阻断整次安装；
> 钩子与手动刷新仍可用。要周期刷新，在能建任务的环境重跑即可。
>
> 另外：定时任务用系统账号跑时 `gh` 读不到你的 GitHub 登录态（票面源降级）；
> 用当前用户 ＋ 仅登录时 ＝ `gh` 正常、又无 token。两全。
>
> **⚠ 2026-10-27 口径更正（同日两拍，以后一拍为准）**
> 本文件一度记成"用户拍板：不建闹钟、长期手动刷"——**那一版作废**。用户随后确认：
> **自动重建是需要的**，此事已作为加急任务由王牌飞行员热修中：
> 票 `H-20261027-1`「航班信息板提交后不自动更新：钩子只打脏标记、无人消费」，
> 分支 `hotfix/ace-20261027-1-board-autorebuild`，口径＝用户对王牌会话当面指令「你直接热修」。
> ⇒ **不要再拿"已拍板接受手动刷"答复后续会话**；实现方案以那张热修票的落地为准，落定后回写本行。
>
> 仍然成立的两条事实与一条判否（热修方案请一并读）：
> · 本机实测 `schtasks /Create` 直接 `Access is denied`（普通用户权限建不了，非脚本 bug）——
>   这是热修必须绕过的硬约束，不是"算了不修"的理由。
> · 钩子只打标记、页面「刷新」只重读磁盘、双击 `refresh.vbs` 才立刻重建——现状三腿都还在，
>   页头带快照时间与"距今 N 分钟"，过期看得见、不骗人。
> · **判否**：把板子挂到本仓已有的 15 分钟产品运维轮询（`KaiVass-OpsPoll15` / `ops/ops-poll.py`）
>   上顺手消费——那是产品运维面的腿，治理看板塞进去＝混职责，且要改别的票地盘的文件。

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
python -m unittest discover -s tests -v          # 33 项单元测试（含端到端）
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
