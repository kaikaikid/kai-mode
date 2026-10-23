---
name: 航班信息
status: active
approved_by: human:kaikaikid
approved: 2026-10-22
sources:
  - resource: "skills/航班信息/templates/render_board.template.py"
    note: "实现正本：单文件生成器模板（只用标准库）；配置烘焙进去即成一块自包含的板"
  - resource: "skills/航班信息/templates/board.config.example.json"
    note: "板配置样例（机场那块板的真实配置）；照着改即得新板"
  - resource: "框架仓旧裁决"
    note: "模型来源：四角色与断点物（任务表 / 票评论 / 分支），阶段链由这三种证据合判；判据出处：项目仓 框架仓旧裁决（历史），已由本仓 0003 重述接管"
  - resource: "项目配置实例 paths.day_tables_dir"
    note: "日表目录（塔台写）：day_table_pattern 如 YYYY-MM-DD-main.md / -deputy.md，5–10 行；读不到实例 ⇒ rc≠0 报缺件"
  - resource: "GitHub Issues（票面与评论）"
    note: "唯一事实源；阶段判词与断点都在评论里"
description: >
  板工坊：一块板 = 一份板配置 + 一份自包含适配脚本 + 一份归档。
  把当日任务表、Issue 阶段链、里程碑进度、交接日报按配置汇成一块板；
  AI 只读每块板的 board.json 摘要层（≤ 25 KB），人读 HTML。
  任一数据源失败只降级并点名，不整页崩。
  板是静态页、页面里不取数：要更新必须跑生成器；可装系统闹钟（install_refresh_timer.py）
  零 token 定时刷新，跨 agent、不依赖宿主定时口。
  触发：要看机场现在在飞什么、刷新航班信息板、排班后刷新板、给板装定时刷新、要新开一块板。
version: 2.1.0
updated: 2026-10-22
---

# 航班信息 —— 板工坊（配置 → 脚本 → 归档）

> 落地 [0003 四角色机场](../../框架仓旧裁决) 的断点物模型（判据出处：项目仓 框架仓旧裁决，历史）。
> 实现正本：[`templates/render_board.template.py`](templates/render_board.template.py)；脚手架 [`scripts/new_board.py`](scripts/new_board.py)。
> 本技能**只读项目仓、只写板库**；不改票面、不排班、不发货。

## 角色定位

**板工坊**：不是一块写死的板，是一条能反复造板的流水线。

一块板 = 三件物：

| 件 | 是什么 | 谁写 |
|---|---|---|
| 板配置 | 一份 JSON：名字 / 标题 / 信息源 / 阶段链 / 判据 / 方向句 / 视图 / 摘要形状 | 人写（`board.config.json`） |
| 适配脚本 | 模板 + 烘焙进去的配置 ⇒ 单文件、自包含、可单独跑可单独改 | 脚手架生成（`render_<板名>.py`） |
| 归档 | 人读 HTML ＋ 机读摘要 JSON ＋ 全量 JSON ＋ 配置留档 ＋ 生成历史 | 适配脚本每次刷新写 |

一句话：**板是镜子，不是手。**它只读、只写板库；判断与动作归塔台 / 机长 / 地勤。

**分工**：板工坊（本技能）＝造板 / 刷新 / 归档 / 索引；**装配**＝「给某个仓装一块板」走
[`../set-航班信息/SKILL.md`](../set-航班信息/SKILL.md)（一条命令装完并出第一版板）。装配面只 import 复用本技能的脚本，不另写判据。

两个面，读者不同：

| 面 | 文件 | 读者 | 契约 |
|---|---|---|---|
| 人读面 | `<板名>/index.html` | 人 | 自包含（内联 CSS/JS，无 CDN、无运行时请求、**无外链字体**）；页面「刷新」只重读磁盘快照；版面＝**左侧栏（段导航 ＋ 板身份）＋ 主列（工具条 / 页头 / 方向条 / KPI / 逐段可折叠）＋ 状态条** |
| 机读面 | `<板名>/board.json` | AI / 脚本 | AI 侧**唯一**数据面；`schema` = `flight-info/1`；**必须 ≤ 25 KB** |

## 激活方式

- 人工：`/航班信息`，或用户说「刷新航班信息板」「机场现在在飞什么」「排班后刷新板」「再开一块板」。
- 定时：**本技能自己装** —— `scripts/install_refresh_timer.py` 走**操作系统闹钟**（Windows 任务计划 / POSIX crontab），
  到点直接调该板的刷新壳（纯 Python、确定性）⇒ **零 token、跨 agent**：不依赖宿主的定时口，
  换哪家的 agent 跑、甚至没有任何 agent 在跑，板照样刷。周期可调（默认 30 分钟）。
- 上游：塔台排完班后刷新一次；[`kai-mode`](../kai-mode/SKILL.md) 要全景时拉起本技能。
  （塔台的 30 分钟定时器**不刷板**——它走宿主定时口、每轮要拉起 AI 会话；刷板这活归上面那条系统闹钟。）

## 怎么用（速查）

| 要什么 | 怎么做 |
|---|---|
| 给某个仓装一块板 | `/set-航班信息`，或直接跑 `python skills/set-航班信息/scripts/setup_board.py --repo-root <仓根>`（装完即出第一版板） |
| 日常刷新 | 板目录里的 `refresh_<板名>.bat`（板库根＝板配置 `output.root`，如 `<板库根>\<板名>\`） |
| 装定时刷新（零 token） | `python skills/航班信息/scripts/install_refresh_timer.py --repo-root <仓根> --lib-root <板库根> --all --every 30 --apply` |
| 查 / 停定时 | 同上加 `--list` 查状态；加 `--remove --apply` 停并删 |
| 让页面「刷新」按钮真能刷新 | `install_refresh_timer.py --repo-root <仓根> --lib-root <板库根> --all --register-protocol --apply`（解绑 `--unregister-protocol --apply`） |
| 出索引 | `python skills/航班信息/scripts/build_index.py --repo-root <仓根> --lib-root <板库根>` |
| 板在哪 | `<板库根>\<板名>\`（板库根＝板配置 `output.root`，相对项目仓根） |

- 人读面＝`<板名>\index.html`；机读面＝`<板名>\board.json`（AI 只读这个；`full.json` 是全量层，可重生成、不入库）。
- 装配只管「装」；造板 / 刷新 / 归档 / 索引的判据都在本技能。装配入口见 [`../set-航班信息/SKILL.md`](../set-航班信息/SKILL.md)。

## 刷新通道（四条，只有两条真更新）

板是**静态照片**，不是监控画面：**页面里没有任何取数动作**（无 fetch、无 WebSocket、无自动重载，
自包含＝连 CDN 和外链字体都没有）。要让数据变，必须有人去跑生成器。

| 通道 | 谁按的 | 真更新 | 说明 |
|---|---|---|---|
| 系统闹钟（推荐） | 操作系统 | ✅ | `install_refresh_timer.py --apply` 装；**零 token、跨 agent**；结果落在 `refresh.log` |
| 人工 / agent | 人 或 agent | ✅ | `/航班信息`，或板目录里的 `refresh_<板名>.bat`（要花 token 的只有 agent 跑的那次） |
| 页面「刷新」按钮（**装了协议**） | 人 | ✅ | 注册 `flight-info://` 协议后，按钮会叫**系统真跑一次生成器**，约 4 秒后页面自动重载 |
| 页面「刷新」按钮（没装协议） | 人 | ❌ | 只给网址加个时间戳、重读**磁盘上的旧文件**；静默降级，不报错也不卡页面 |
| 页面 60 秒计时 / `--snapshot` | 自动 | ❌ | 前者只把「数据生成 X 分钟前」这句话重算（≥60 分钟标过时）；后者只另存留档，不入库 |

**查板新不新**：`install_refresh_timer.py --list` 会报每块板的「上次刷新：X 分钟前」＋ 定时在不在册；
调不动系统命令时报「查不了」，**不冒充「未装」**。

**装了协议还要重建一次板**：页面是**烘焙进适配脚本的静态副本**，改了模板或注册了协议，
已生成的板不会自己长出新按钮 —— 用板目录里的 `board.config.json` 重新建一次
（`setup_board.py --repo-root <仓根> --config <板目录>/board.config.json --force`），配置不丢。

### 周期怎么选（--every 填多少）

实测：纯本地源刷一次 **≈2 秒**（启动解释器 ＋ 重写三件产物）；联网源（GitHub issues / 里程碑）要另加网络时间。

| 周期 | 观感 | 什么时候用 |
|---|---|---|
| 30 分钟 | 慢，赶不上排班发货 | 只当兜底 |
| **5–10 分钟** | 够用，甜点区 | 默认建议 |
| 1 分钟 | 太密：每次要联网拉票，容易撞 GitHub API 限流 | 不推荐，除非 `--no-network` |

### 比定时更快：事件驱动（git 钩子）

定时是「到点就刷」，事件驱动是「**真变了才刷**」——塔台一发货、机长一提交，板立刻跟上。

git 钩子走的是 **git 层**，跟 AI 宿主没关系：它只认「这个仓发生了一次 commit / merge」，
**不认是谁提交的** —— 塔台（AI）、机长（AI）、人手动提交，都一样触发 ⇒ 跨 agent、零 token，
不需要任何 AI 在场。

一条命令挂两枚钩子（`post-commit` ＋ `post-merge`；**不碰**仓里既有的 `pre-commit` / `pre-push`）：

```bash
python skills/航班信息/scripts/install_refresh_timer.py --repo-root <仓根> --install-hook --apply
```

**钩子怎么刷才对（三种做法实测过，只有第一种能用）**：

| 做法 | 结果 |
|---|---|
| `schtasks /Run` 叫醒**已装的定时任务**（本技能采用） | ✅ 异步、不阻塞 commit、真刷新 |
| 同步调刷新壳 | ❌ 联网的板刷一次**几十秒**（本机机场板实测 **55 秒**：73 张票 + 69 份交接），每次 commit 干等 |
| `(cmd ... &)` 丢后台 | ❌ 钩子一退出子进程就被回收，板根本没刷（表现为 `refresh.log` 空的） |

外加两道保险：**60 秒去抖**（连续多次 commit 只刷一次）、**没装定时任务就只提示、不硬刷**（fail-open 到底）。

**铁律**：钩子只当发令员，退出码永远 0，**绝不把 `git commit` 卡住**。
改项目仓 `.githooks/**` 属红线邻面，动前先问；脚本也默认干跑，要 `--apply` 才落盘（LF 行尾 ＋ 执行权限）。

推荐组合：**事件驱动（主）＋ 5–10 分钟定时（兜底）** —— 钩子管秒级跟上，兜底管漏网：
钩子是**本机**生效的，别处提交你 pull 下来靠 `post-merge`，别的漏网情况靠定时。

## 板库落点

**每块板的库都在各自项目仓内**（不跨仓共享）。板库根＝板配置 `output.root`（相对项目仓根；
脚本与模板不带第二份缺省值，缺了按缺件报——框架仓旧裁决），布局如下：

```
<项目仓根>\<板库根>\
    index.html                      ← 索引页：列出所有板（板名/标题/生成时刻/sources/kpi/链接）
    <板名>\
        index.html                  ← 该板的人读面（就地更新）
        board.json                  ← 该板的机读【摘要层】（AI 读这个，目标 ≤ 25 KB）
        full.json                   ← 该板的机读【全量层】（当前 payload 全部；不入库，可重生成）
        board.config.json           ← 板配置留档（人能读能改）
        render_<板名>.py            ← 该板的适配脚本（自包含）
        refresh_<板名>.bat          ← 该板的刷新入口（CRLF）
        history.jsonl               ← 每次生成追加一行（时刻/sources/kpi/文件 sha256）
        snapshots\                  ← 仅 --snapshot 时写带时刻的 HTML 快照（不入库）
```

## 生命周期

### 1. 建板（写配置 → 脚手架）

```bash
python skills/航班信息/scripts/new_board.py --repo-root <项目仓根> --config <板配置.json> \
       [--name 覆盖板名] [--force] [--out-root <覆盖 output.root>]
```

- 脚手架先校验配置（必填项、source type 已知、stage_rules 自洽、板名合法）；**校验不过 ⇒ 非 0 并逐条打印错在哪**。
- 通过则建板目录，写三件：`board.config.json`（留档）、`render_<板名>.py`（模板 + 烘焙配置，自包含）、`refresh_<板名>.bat`（CRLF、参数化）。
- 板目录已存在默认**不覆盖**；要覆盖加 `--force`。
- 样例配置：[`templates/board.config.example.json`](templates/board.config.example.json)（机场那块板的真实配置，照着改即得新板）。

### 2. 刷板（每次刷新）

```bash
python skills/航班信息/scripts/refresh_board.bat <项目仓根> <板名>
```

或直接跑该板自己的脚本（它住在板目录里，自带配置）：

```bash
python "<板库根>/<板名>/render_<板名>.py" --repo-root <项目仓根> [--quiet] [--no-network] [--snapshot]
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--repo-root` | 从脚本所在目录向上自动探测（先认项目配置实例，再退日表/日报目录） | 项目仓根；`git` / `gh` 子进程的 cwd |
| `--out` | 脚本所在板目录 | 输出目录 |
| `--quiet` | 关 | 只打一行汇总（定时器用） |
| `--no-network` | 关 | 一次网络都不发；票面 / 判词 / 里程碑记 `skipped` |
| `--snapshot` | 关 | 另存 `snapshots/<板名>-<YYYYMMDD-HHMMSS>.html` |

源落点（任务表 / 交接日报）不写死：板配置源里没写显式 `path` 时，缺省读项目配置实例
`paths.day_tables_dir` / `paths.handoff_dir`（框架仓旧裁决/D4）；实例或字段读不到 ⇒ **rc≠0 报缺件三格**，
永不猜路径。

### 3. 归档（刷新时自动写）

`index.html`（人读面）＋ `board.json`（摘要层）＋ `full.json`（全量层）＋ `history.jsonl` 追加一行。
`history.jsonl` 每行含：生成时刻、`sources` 映射、`kpi`、三件产物的 sha256。

人读面的版面：**画布优先壳** —— 左侧栏（① 板身份 ② 段导航 ③ 元信息区）＋ 主列（顶部工具条 → 页面级标题 → 方向条 → KPI → 逐段可折叠的内容段），主列底缘一条状态条（数据源灯簇 ＋ 生成时刻 ＋ 刷新说明）。
段顺序与侧栏条目顺序都由 `view.sections[]` 决定 —— 排班表要置顶，就把它排在该数组的第一位。
**壳层几何**取自中央库 `soft-design-system` §06 当前版；**配色是板子自己的暖纸色系**（纸/卡/墨/朱砂焦点色与阶段语义色），**不跟中央库色板**。板是自包含单文件，取值抄进板的 `:root`。**字体未内嵌，用系统字体栈。**

### 4. 索引页

```bash
python skills/航班信息/scripts/build_index.py --repo-root <项目仓根> --lib-root <板库根>
```

扫板库根下每块的 `board.json`，写 `<板库根>/index.html`：板名、标题、生成时刻、sources 状态、kpi 摘要，
并链到该板的 `index.html` / `board.json` / `full.json` / `history.jsonl`。自包含 HTML（内联 CSS，无 CDN）。

### 5. 改板

改 `board.config.json` 不够 —— 脚本里的配置是**烘焙**进去的。改板两条路：

- 改配置后重跑脚手架（`--force`），生成新的适配脚本；或
- 直接改 `render_<板名>.py` 里 `CONFIG` 那一块（它是可读 JSON，改完就能跑）。

## 板配置 schema

`board.config.json`，`schema` 值 `flight-info-board/1`。字段表（照实现）：

| 字段 | 类型 | 必填 | 默认 | 语义 |
|---|---|---|---|---|
| `schema` | string | 是 | — | 固定 `flight-info-board/1` |
| `name` | string | 是 | — | 板名；目录名与脚本名后缀；禁含 `\ / : * ? " < > |`，禁空，禁尾随 `.` |
| `title` | string | 否 | `name` | 页面主标题（`<h1>`） |
| `subtitle` | string | 否 | 空 | 页面副标题（眉标） |
| `repo` | string | 否 | 空 | GitHub slug；空 ⇒ 从 `--repo-root` 的 git remote 解析；解析不出 ⇒ 本地占位 |
| `output.root` | string | 是 | — | 板库根（相对项目仓根；脚本不带缺省值，缺 ⇒ 建板/索引/定时器一律报缺件） |
| `output.index_html` / `board_json` / `full_json` / `history` / `snapshots_dir` | string | 否 | `index.html` / `board.json` / `full.json` / `history.jsonl` / `snapshots` | 产物文件名 |
| `output.payload_schema` | string | 否 | `flight-info/1` | 写进 JSON 的 `schema` |
| `sources[]` | array | 是 | — | 每条 `{id, type, ...params}`；`id` 唯一，是 `sources` 映射里的键 |
| `sources[].type` | string | 是 | — | `github-issues` / `github-milestones` / `issue-comments` / `tasks-table` / `handoff-dir` / `git-worktrees` / `notes-jsonl` |
| `sources[].repo` | string | 否 | 空 | 该源的仓 slug；空 ⇒ 用顶层 `repo` |
| `sources[].path` / `include` / `days` / `limit` / `last` / `state` / `branch_prefix` / `tickets` / `max_docs` | — | 否 | 见类型 | 各类型的参数（见下表）；`path` 给了用它，没给读项目配置实例对应字段（见下表），都没有 ⇒ rc≠0 报缺件 |
| `stages[]` | array | 是 | — | 阶段链顺序，每条 `{key, label}` |
| `off_chain_stages[]` | array | 否 | `[]` | 链条外的阶段（可领 / 挡住…），每条 `{key, label}` |
| `stage_rules[]` | array | 是 | — | 阶段判据，每条 `{when, value?, stage, why?, ignore_case?}`；最后一条必须是 `{when:"else"}` |
| `next_text` | object | 否 | `{}` | 阶段 → 「下一步」文案 |
| `role_labels` | object | 否 | `{}` | 角色 → 中文名（主机长 / 副机长…） |
| `owner_labels` | object | 否 | `{}` | 阶段 → 掌机文案；`unplanned` 是没排班时的兜底 |
| `badges` | object | 否 | `{}` | 标签显示：`priority`（排序）/ `show`（显示哪些）/ `highlight` / `highlight_class` / `hold_class` |
| `direction` | object | 是 | — | `{template, variants[], min_rows, target_rows, max_ship_list}`，见下 |
| `summary` | object | 否 | `{}` | 摘要层形状：`max_flights` / `max_bytes` / `flight_stages[]` / `flight_fields[]` / `schedule_fields[]` / `max_schedule_rows` |
| `view` | object | 否 | `{}` | 视图：`sections[]`（每条 `{key,title,hint}`）/ `filters[]` / `kpis[]` / `search_placeholder` |
| `view.sidebar` | boolean | 否 | `true` | 是否渲染**左侧垂直栏**（壳层左栏：身份区 ＋ 段导航 ＋ 元信息区） |
| `view.sidebar_identity` | boolean | 否 | `true` | 侧栏身份区（板名 slug ＋ 生成时刻；「我在哪、什么时候生成的」） |
| `view.sidebar_meta` | boolean | 否 | `true` | 侧栏底部元信息区（生成器 / 摘要 / 全量 / 刷新入口等**产物路径**，mono） |
| `view.nav` | boolean | 否 | `true` | **段导航**是否渲染（住侧栏里；旧键沿用，显式 false ⇒ 侧栏只剩身份区与元信息区） |
| `view.collapsible` | boolean | 否 | `true` | 内容段是否**逐段可折叠**（`true`＝原生 `details/summary`；`false`＝退回普通 `h2` 段落，锚点不变） |
| `view.collapsible_default` | string | 否 | `open` | 折叠段的默认状态：`open`＝默认全展开（一眼看全），`closed`＝默认折起 |

**版面（壳层）**

- 人读面＝**画布优先壳**：左侧栏（段导航 ＋ 板身份）＋ 主列（顶部工具条 → 页面级标题 → 方向条 → KPI → 逐段可折叠的内容段），主列底缘贴一条**状态条**（数据源灯簇 ＋ 生成时刻 ＋ 刷新说明）。
- 段顺序与侧栏条目顺序都由 `view.sections[]` 决定；排班表要置顶，就把它排在该数组的第一位。
- 段锚点 id ＝ `sec-<段 key>`，挂在该段的 `<summary>` 上；`summary` 永远可见，所以段折着也定位得到。
- 折叠纯前端表现：`board.json` / `full.json` / `sources` / `kpi` / `history.jsonl` 的形状与语义**一律不变**。
- **壳层几何与配色**：几何实值取自中央库 `soft-design-system`（`references/shell/` 的 §06 口径正本）；**配色是板子自己的暖纸色系**（纸/卡/墨/朱砂焦点色与阶段语义色），**不跟中央库色板**。板是自包含单文件、不能引 CSS，故取值抄进板的 `:root`。**字体未内嵌**（用系统字体栈，不引外链字体）。
- 窄屏：≤768px 侧栏收成**顶部一行**（段导航横排、容器内横滚），≤640px 再收一档；整页不出横向滚动条。

**source type 与参数**

| type | 参数 | 取到的数据 | 状态取值 |
|---|---|---|---|
| `github-issues` | `repo` / `state`（`open`｜`closed`｜`none`）/ `limit` / `closed_limit` / `closed_days` | 票面（含最近 closed） | `ok` / `skipped` / `fail` |
| `github-milestones` | `repo` / `limit` | 开放里程碑与进度 | `ok` / `skipped` / `fail` |
| `issue-comments` | `repo` / `tickets`（`auto`＝任务表 ∪ 在飞票，或写死列表）/ `last` | 每票最后 N 条评论**原文** | `ok` / `skipped` / `fail` |
| `tasks-table` | `path`（缺省＝配置实例 `paths.day_tables_dir`）/ `include`（通配数组，如 `["*-main.md","*-deputy.md"]`）/ `roles` | 当日任务表两张（文件名按实例 `day_table_pattern` 拼，如 `YYYY-MM-DD-{lane}.md`） | `ok` / `absent` |
| `handoff-dir` | `path`（缺省＝配置实例 `paths.handoff_dir`）/ `days` / `max_docs` | 近 N 天交接日报 | `ok` / `absent` |
| `git-worktrees` | `branch_prefix` | `exec/<票号>-*` ⇒ 在飞证据 | `ok` / `fail` |
| `notes-jsonl` | `path` / `limit` | 钩子提醒 | `ok` / `absent` / `fail` |

**stage_rules 的 `when` 取值**

| when | 命中条件 | 备注 |
|---|---|---|
| `state_closed` | 票已关 | 永远排第一 |
| `label_equals` | 票带某 label（`value`） | |
| `comment_contains` | 最新一条评论命中正则（`value`）；`ignore_case` 开关大小写 | 规则在配置里的先后＝同一条评论内多个关键词的优先级 |
| `branch_exists` | 有 `exec/<票号>-*` 分支 | `why` 可用 `{branch}` |
| `table_note_contains` | 日表备注命中正则（`value`） | `why` 可用 `{note}` |
| `assignee_exists` | 票有指派 | `why` 可用 `{assignee}` |
| `else` | 兜底 | 必须有，否则校验不过 |

**direction 的占位符**

`{to_ship}`（待发货票号，顿号分隔，最多 `max_ship_list` 个）/ `{to_ship_count}` / `{main_rows}` / `{deputy_rows}` / `{n_tables}` / `{min_rows}` / `{target_rows}`。
`direction.variants[]` 按 `when`（`to_ship` / `no_to_ship_low_tables` / `no_to_ship`）选句；`direction.template` 是兜底句。

**摘要层（`summary`）怎么裁**

- `flight_stages[]`：只收这些阶段的票（空＝全收）；`max_flights`：最多收几条；
- `flight_fields[]`：每条票只留这些字段；
- `max_bytes`（默认 25600 = 25 KB）：**硬上限**；超了自动从尾部丢票并把 `counts.flights_truncated` 置 true。

## 读契约

- **AI 侧读机读摘要层**：`board.json`。判据顺序固定：**先看 `sources`，再看 `kpi` / `counts`，再下钻单张票**。
- **AI 侧代码 / agent 整读人读 HTML 即红**：`index.html` 是人读面，不是 agent 面；整读 HTML 属违规。
- **禁止把 HTML 当数据源解析**：不 grep、不正则、不从页面里抠票号或阶段。
- **`full.json` 是全量层**：可重生成、不入库；AI 需要全量明细时按需读它，但**不得把它当常驻数据面**。
- 阶段由「票状态 ＋ 分支 ＋ 日表备注 ＋ 最后几条评论」合判（判据在配置的 `stage_rules` 里）；判不出来如实标 `未定`，不许猜。

机读层字段（摘要层）：

| 字段 | 含义 |
|---|---|
| `schema` / `kind` | `flight-info/1` / `summary` |
| `name` / `title` / `subtitle` | 板的身份（索引页用） |
| `generated_at` / `generated_ts` | 生成时刻 |
| `repo` | `owner/name`；远端解析不出时是本地占位 |
| `stage_chain` | 阶段链：排队 → 在飞 → 审查 → 待发货 → 收尾 |
| `direction` | 本轮方向一句话 |
| `kpi` | 在飞 / 待发货 / 可领 / 排队 / 挡住 / 今日收尾计数 |
| `milestones` | 里程碑进度 + 下一班该动的票（只有 `number/title/progress/next`） |
| `flights` | 按 `summary` 收录的少量票（字段已裁剪） |
| `schedules` | 两张日表骨架（票号 / 一句话 / 备注） |
| `sources` | 每个数据源的状态：`ok` / `skipped` / `absent` / `fail` |
| `counts` | `flights_total` / `flights_included` / `flights_truncated` |

## 权限与禁区

**可以**

- 读日表、Issue、分支、日报、钩子文件。
- 写板库里的文件（配置留档、适配脚本、刷新 bat、四件产物、历史、快照、索引页）。

**不可以**

- 写票面、评论、标签、里程碑（地勤 / 机长 / 塔台的权）。
- 写日表（塔台唯一写者）；不排班、不发货、不关票。
- 改项目仓任何源码；不引第三方依赖（生成器只用标准库）。
- 把 HTML 当数据源；把退出码当数据质量判据。
- 改 `skills/set-kai-mode/**`、框架仓 README / MIGRATION（另有归属）。

## 失败与降级

- **脚手架**：配置校验不过 ⇒ **非 0**（2）并逐条打印错在哪；写不出 ⇒ 非 0（3）。**校验失败必须看见，不许默默建半块板。**
- **板生成**：板生成成功（含降级）**恒 0**；配置坏 / 采集炸 ⇒ 2；写不出 ⇒ 3。
- 任一数据源失败 ⇒ **该段降级并点名**（写进 `sources` 映射），**不整页崩**。板是只读增强，不是门。
- **退出码 0 只表示「板已生成」，不代表数据全好** ⇒ 判据读 `sources` 字段，**别拿退出码当绿**。
- `gh` 不可用 / 未登录 ⇒ `issues` / `milestones` / `comments` 记 `fail` 或 `skipped`，其余源照常出板。
- 票源塌了 ⇒ 退化成「只画任务表里的票」，`flights[].why` 标「仅任务表（票源不可用）」。
- 摘要层超 `max_bytes` ⇒ 自动丢票并标 `counts.flights_truncated`（不静默超限）。
- 降级一律**如实报**，不静默、不假装干净。

## 入库口径

| 件 | 入库？ | 为什么 |
|---|---|---|
| `<板名>/index.html`（人读面） | ✅ | 板本体，可直接给人看 |
| `<板名>/board.config.json` | ✅ | 配置是正本留档；改板从它开始 |
| `<板名>/render_<板名>.py` | ✅ | 适配脚本，正本；带上它这块板就能在别的机器上重生成 |
| `<板名>/refresh_<板名>.bat` | ✅ | 刷新入口 |
| `<板名>/history.jsonl` | ✅ | 生成历史（时刻 / sources / kpi / sha256），可追责 |
| 板库根 `index.html` | ✅ | 索引页 |
| `<板名>/full.json` | ❌ | 全量层，可重生成，别进版本库 |
| `<板名>/snapshots/**` | ❌ | 快照，随时能再生成 |

## 验证命令

```bash
python -m pytest skills/航班信息/scripts/tests/ -q
python skills/航班信息/scripts/new_board.py --repo-root <项目仓根> --config <板配置.json>
python skills/航班信息/scripts/build_index.py --repo-root <项目仓根> --lib-root <板库根>
```

## 正本

- 模板：[`skills/航班信息/templates/render_board.template.py`](templates/render_board.template.py) —— 实现正本。
- 板配置样例：[`skills/航班信息/templates/board.config.example.json`](templates/board.config.example.json)。
- 脚手架：[`skills/航班信息/scripts/new_board.py`](scripts/new_board.py)；索引：[`skills/航班信息/scripts/build_index.py`](scripts/build_index.py)。
- [0003 四角色机场](../../框架仓旧裁决) —— 模型来源（判据出处：项目仓 框架仓旧裁决，历史）。
- 日表：项目配置实例 `paths.day_tables_dir` ＋ `day_table_pattern`（如 `YYYY-MM-DD-main.md` / `-deputy.md`；塔台写，本技能只读；读不到实例 ⇒ rc≠0 报缺件）。
- GitHub Issue 正文与评论（唯一事实源）。
- [`skills/kai-mode/SKILL.md`](../kai-mode/SKILL.md) · [`skills/set-kai-mode/SKILL.md`](../set-kai-mode/SKILL.md) · [`loops/loop-protocol.md`](../../loops/loop-protocol.md)
