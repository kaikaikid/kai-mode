---
name: flight-info
status: active
approved_by: human:kaikaikid
approved: 2026-10-24
sources:
  - resource: "框架仓旧裁决"
    note: "阶段链与断点物模型（四角色 / 日表 / 在飞证据）"
  - resource: "handoff/60-board/"
    note: "看板数据层：跨 agent 卡片；本技能是它的展示层，不持有状态"
  - resource: "GitHub Issues"
    note: "票状态正本；本技能只读，不写"
description: >
  看板展示形态（Flight Information）：一块板 = 一个 SQLite 库 ＋ 一份板配置 ＋ 两个产物。
  采集各源 → 归一化落库 → 判阶段 → 出 board.json（AI 只读，≤25KB）与 index.html（人读）。
  模块化：db / stage / sources / collect / render / config 单向依赖，源按类型插件式增删。
  刷新靠 git 钩子打脏标记 ＋ 有脏才刷，零 token、跨 agent；任一源失败只降级点名，不整页崩。
  触发：/航班信息、刷新航班信息板、看现在在飞什么、给这个仓装一块板。
version: 1.1.0
updated: 2026-10-24
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

加一个源＝在 `sources/` 放一个实现 `collect(cfg, ctx)` 的模块 ＋ 在 `sources/__init__.py` 的 `REGISTRY` 加一行。**其他文件一个字都不用改。**

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
| `view.focal_stage` | 否 | 哪一段着赭色，默认 `to_ship`；该段为 0 张时**不亮** |
| `view.font_source` | 否 | `system`（默认，零网络）/ `web`（引 Google Fonts） |
| `view.metrics[]` | 否 | `{key,label}` 次级读数；不写＝航班总数 / 今日收尾 / 今日排班 |
| `view.labels` | 否 | 覆盖界面文案（`flights`/`ticket`/`content`/`stage`/`owner`/`lane`/`schedule`/`note`…） |
| `view.eyebrow` | 否 | 页头小标前缀，缺省只有 `RUN <run_id>` |

**源类型**

| type | 参数 | 读什么 |
|---|---|---|
| `board-cards` | `path`（缺省 `paths.handoff_dir`） | `handoff/60-board/{open,claimed,done}/` 卡片的 frontmatter |
| `tasks-table` | `path`（缺省 `paths.day_tables_dir`）/ `include` / `lanes` | 日表 markdown，`- [ ] #12 事 | 备注` |
| `git-worktrees` | `branch_prefix`（默认 `exec/`） | 本地 worktree/分支 → 在飞证据 |
| `github-issues` | `repo` / `state`（`open`\|`closed`\|`none`）/ `limit` | 票面（`gh` 不可用则降级） |

**`stage_rules.when` 取值**：`state_closed` `label_equals` `comment_contains` `branch_exists` `table_note_contains` `assignee_exists` `else`。
`why` 可带占位 `{branch}` `{note}` `{assignee}` `{label}`。

**KPI 名**：`in_flight`（在飞+审查）`to_ship` `ready` `queued` `ready_plus_queued` `hold` `closed` `closed_today` `open` `total` `planned`；
外加 `by_stage`（`{阶段key: 张数}`，阶段轨用它，自定义阶段也认）。

## 4. 版式（`index.html`）

按 Diagram Design 的 editorial 皮肤做，规则是「删到不能再删」：

| 件 | 规格 |
|---|---|
| 色 | 纸 `#f5f5f5` / 墨 `#2d3142` / 次字 `#4f5d75` / 弱 `#5a6580` / 赭 `#bf4520`（暗色另有整套，跟 `prefers-color-scheme`） |
| 字体 | 标题衬线、正文无衬线、票号与读数等宽；**缺省本地字体栈**（零网络），`view.font_source: web` 才引 Google Fonts |
| 赭色预算 | **2 处**：方向句的红线、待发货段（含其阶段签）。源失败时赭点点亮——同一个语义：**有活要干** |
| 分隔 | 一律 1px 发丝线，**零阴影**、圆角 ≤ 8px、间距 4 的倍数 |
| 阶段轨 | 一条带子（发丝线分隔），不是五张卡；链外阶段（可领/挡住）挂在虚线右侧 |
| 阶段签 | 方角（`rx=2`），不画药丸；在飞＝白底墨边，审查＝灰底，待发货＝赭，挡住＝虚线，已收尾＝无边框 |

改皮肤只改 `flightinfo/render.py` 顶部的 `CSS` 常量（`:root` 里的 tokens），不动逻辑。

## 5. 命令

```bash
# 建一块板（校验 → 建目录 → 留档配置 → 出首版）
python scripts/init_board.py --repo-root <仓根> [--config <json>] [--name <板名>] [--force]

# 刷一块板（采集 → 落库 → 出两个产物）
python scripts/refresh.py --repo-root <仓根> --config <板目录>/board.config.json [--quiet] [--no-network]

# 装有脏才刷的 git 钩子（默认干跑，--apply 才落盘）
python scripts/install_hook.py --repo-root <仓根> [--apply] [--remove --apply]

# 给闹钟/人工用的幂等刷新（无脏直接跳过）
python scripts/refresh_if_dirty.py --repo-root <仓根> --config <板配置> [--force]
```

产物落 `板目录/`：`board.db`（库）｜`board.json`（AI 面）｜`index.html`（人面）。

## 6. 退出码与降级

| 码 | 含义 |
|---|---|
| `0` | 板已生成（**含降级**） |
| `2` | 配置/参数错（逐条打印错在哪） |
| `3` | 写盘失败 |

- **`0` 只表示「板生成了」，不代表数据全好** —— 判据读 `board.json` 的 `sources`（`ok`/`absent`/`skipped`/`fail`），别拿退出码当绿灯。
- 单源炸 ⇒ 该源记 `fail` 并点名，其余照出板。
- 票源塌 ⇒ 退化成只画日表与卡片里的票。
- 摘要层超 `max_bytes` ⇒ 从尾部丢票并置 `counts.flights_truncated`。
- git 钩子**只打标记**，退出码恒 0，绝不阻塞 commit。

## 7. 权限与禁区

**可以**：读日表、卡片、票面、分支；写板目录（库、两个产物、配置留档）；装/卸自己的 git 钩子。

**不可以**：写票面/评论/标签；写日表（塔台唯一写者）；写 `handoff/60-board/` 卡片（改用 `scripts/handoff-board.py`）；
改目标仓源码；把 `index.html` 当数据源解析（AI 只读 `board.json`）。

## 8. 验证命令

```bash
python -m unittest discover -s tests -v          # 24 项单元测试（含端到端）
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
| 看板卡片格式 | [`handoff/60-board/README.md`](../../handoff/60-board/README.md) |
| 阶段模型来源 | [`框架仓旧裁决`](../../框架仓旧裁决) |
