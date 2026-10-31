---
name: set-kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "../bridge/SKILL.md"
    note: "对外唯一入口；本技能负责把它装到宿主并设为默认"
  - resource: "../../../v2/skills/coding/SKILL.md"
    note: "施工与发货内核；装舰桥时一并装它"
  - resource: "scripts/magpie-sync.py"
    note: "技能正本 → 中央库 → 各家宿主链接的回写口"
  - resource: "scripts/uninstall-v1.py"
    note: "卸载 V1 的机械腿：探测、退役、复核、回执都住脚本"
description: >
  kai-mode 的初始化安装入口（不是日常施工）：先看缺什么、列出推荐清单跟用户确认，再只装缺的。
  覆盖：装舰桥与 V2 内核、把舰桥设为默认入口、worktree 环境自检、项目配置实例生成/校验/迁移、
  开票归属守卫、缺件如实登记。触发：新 agent 接手装配、换宿主、修技能落点、迁旧配置实例、
  问「这套东西都住在哪」。不做日常施工。
version: 6.1.0
updated: 2026-10-31
allowed-tools: Bash(*) Read Write Edit
compatibility: Requires python3, git
---

# Set Kai Mode —— 安装舰桥与 V2 内核

> `/bridge` 是**用**这套框架的入口；`/set-kai-mode` 是**装**这套框架的入口。
> 本技能只做安装与配置，**不做日常施工**：不写产品代码、不开 run、不发货、不关票。
> 本文件只回答三件事：**东西在哪、怎么装、装完跑什么自证**。

## 什么时候进这里

- 新 agent / 新机器第一次接手：从零装到能跑。
- 换宿主或换执行体（Claude Code、Qoder、Codex、opencode 等）。
- 技能改了却没在别家生效（正本与库不一致）。
- 项目配置实例还是 schema 4 或更旧——走迁移腿。
- 撞见「同一条判据两处说法不一样」——配置面漂移，回到这里对表。
- **已装的是旧版、要升到新版** ⇒ 走 `upgrade-kai-mode`。本技能只补缺、不覆盖已就位的东西。

## 一套体系，没有并行档位

机场体系（V1：地勤、塔台、机长、副机长、二副、王牌、日表、车道、60 分钟唤醒定时器）已整体下线。
现在只装一套：

| 层 | 组件 | 干什么 |
|---|---|---|
| 入口 | `bridge` | 用户唯一对话面；判断、开票、开 run、清场、发货、回报 |
| 规划 | `kai-mode` | 需求大、方向未定时由舰桥调用；出规划表与拆票草案 |
| 执行 | `v2`（`coding` 命令） | 一个 issue 一个 run；主会话规划验收，物理子会话施工 |
| 方法 | `methods/kai-*` | TDD、审查、诊断、拆票、术语、写文档、安全专项 |
| 记录 | GitHub Issue ＋ `.coding/runs/` | 票面与 run 状态；不看日表 |
| 展示 | `coding status --html` | 进度看板（可选） |

## 装到别的项目：先问清楚（十问）

装进一个新项目不是拷文件，是**把项目差异问清楚**。一条命令跑完十问：

```bash
python scripts/init-project.py --repo <目标仓>            # 逐题问，每题带默认，回车即默认
python scripts/init-project.py --repo <目标仓> --yes      # 全默认（先看 dry-run 输出）
python scripts/init-project.py --repo <目标仓> --answers a.json   # 机器填
```

> 本命令在 **kai-mode 框架仓根**执行；技能装到项目仓后，用 `<框架仓根>/scripts/init-project.py`，
> **不是**项目仓的 `scripts/`。维护者的门禁脚本同理只住框架仓。

**十问（顺序固定，缺一不装）**：

| # | 问什么 | 默认 | 落到哪 |
|---|---|---|---|
| 1 | 项目名 | 目录名 | `project` |
| 2 | 票源（github / none） | `github` | `issue.platform` |
| 3 | 仓库 slug（owner/name） | 从 `git remote` 猜 | `issue.repo` |
| 4 | 交接目录 | `handoff` | `paths.handoff_dir` |
| 5 | 想法目录 | `ideas` | `paths.ideas_dir` |
| 6 | ADR 目录 | `docs/adr` | `registry.adrs.dir` |
| 7 | 规则目录 | `.ai/rules` | `registry.rules.dir` |
| 8 | 宿主 | 回车＝本机当前宿主（不设默认偏置） | `host.adapter` |
| 9 | 收尾门命令（本项目没有就留空＝null） | 空 | `gates.finish_cmd` |
| 10 | 想法池汇总票号 | 空 | `issue.boom_summary_ticket` |

**脚本顺手铺两个组件**：`handoff/` 八槽 ＋ 规范与模板；`docs/adr/` ＋ `GLOSSARY.md` 骨架。
已存在的一律**不覆盖**。缺件（如票源选 github 但没 slug）脚本直接拒绝，不生成半成品实例。

## 一步配置（装完即可用）

**铁律：先看缺什么，再装。** 进本技能第一件事是跑「第 0 步 · 缺口扫描」（全只读），
把现状列成**缺口清单**——已就位的明确标「跳过，不重复装」，缺的才列成「推荐处理项」。
**先把清单念给用户听，用户点头才执行对应步骤**；不闷头把七步全跑一遍。

| # | 装什么 | 验收 |
|---|---|---|
| 0 | **缺口扫描（只读）** | 出一张缺口清单：每项标「已就位/跳过」或「需处理（原因）」 |
| 1 | 注入方法论与技能（仓库内正本） | 技能文件在位；清单以 `.claude-plugin/marketplace.json` 现场派生为准 |
| 2 | 装技能到宿主（`bridge` ＋ `kai-mode` ＋ `v2/coding` ＋ 方法库） | 宿主技能列表里能看见，内容与正本同哈希 |
| 3 | **把舰桥设为默认入口** | 项目 `CLAUDE.md` / `AGENTS.md` 有默认入口段；无斜杠命令时按舰桥执行 |
| 4 | worktree 环境自检（解释器 / node / 依赖三项） | 三项都有明确读数 |
| 5 | doctor | 项目仓门禁全绿或如实点红 |
| 6 | 开票归属守卫（宿主 PreToolUse 钩子） | 无 `--repo` 的 `gh issue create` 被拒；带 `--repo` 放行 |
| 7 | 缺件登记与安装回执 | 缺件按三格登记，回执含宿主落点核对 |

### 0. 缺口扫描（只读）

| 项 | 只读探法 | 判「已就位（跳过）」 | 判「需处理」 |
|---|---|---|---|
| 1 正本技能 | 按 `.claude-plugin/marketplace.json` 的插件目录派生 `skills/*/SKILL.md` 清单，逐个检查文件与互指 | 清单内都在、互指一致 | 缺文件或互指断裂 |
| 2 宿主同步 | `python <本技能目录>/scripts/magpie-sync.py check` | 漂移表三面全绿 | 有漂移文件（列出具体哪些） |
| 3 默认入口 | 读项目 `CLAUDE.md` / `AGENTS.md` 有没有「默认入口＝舰桥」段 | 有且指向 `bridge` | 缺 → 列进推荐清单 |
| 4 环境三项 | `test -x` 解释器/node、`test -d node_modules` | 三项都有明确读数 | 任一项缺（报绝对路径） |
| 5 门禁 | 项目仓门禁脚本 | 全绿或只基线告警 | 有红（列出哪道门） |
| 6 配置实例 | 读 `<root>/.ai/kai-mode.project.json` 的 `schema` | schema 5 且无 V1 键 | 无实例 → 生成；schema ≤4 → 迁移 |
| 7 宿主技能与命令 | 列宿主技能目录 | `bridge`/`coding` 等方法技能能读到 | 缺落点 → 补，软约束登记 |
| 8 同名技能冲突 | `magpie-sync.py check --json` 看 `conflicts[]` | 无冲突 | 有冲突 → 逐条问用户去留，不静默覆盖 |
| 9 开票归属守卫 | 读宿主 `settings.json` 的 `hooks.PreToolUse` | 钩子已挂且自测 ok | 未挂 → 列进推荐清单 |
| 10 旧 V1 残留 | `python <本技能目录>/scripts/uninstall-v1.py [--repo <项目仓>]`（只读探测） | 七个 V1 技能全为「—」，无待人工项 | 有命中 → 走「卸载 V1」腿，用户点头后 `--apply` |

**产出与动作**：把清单念给用户；已就位逐项说「跳过」；需处理项附原因。
用户点头后才执行对应步骤。**能只读判定的，绝不做写操作。**

### 1. 注入方法论与技能

- 正本全部住在仓库里（中立层），任何宿主一进仓库即生效：
  - 入口：`core/skills/bridge/SKILL.md`
  - 规划方法：`core/skills/kai-mode/SKILL.md`
  - V2 执行内核：`v2/skills/coding/SKILL.md`（命令 `v2/bin/coding`；安装见 `v2/README.md`）
  - 方法库：`methods/skills/kai-*`
  - 想法池：`intake/skills/kai-boom-idea-log/SKILL.md`
  - 看板（可选）：`board/skills/flight-info/SKILL.md`；V2 进度优先用 `coding status --html`
- 项目仓落点从配置实例读：`registry.skills.project_skills_dir`；
  剧本登记行收进 `registry.playbooks[]`。新增剧本只加登记行，不在入口里复制判据。

### 2. 装技能到宿主

> 仓库里的 SKILL.md 是**正本**；宿主真正加载的往往是另一份拷贝（如中央库
> `<...>/library/skills/<名>/`，各家宿主目录只是指向它的链接）。
> **改了正本不回写，只有当下这一家生效**。

```bash
S=core/skills/set-kai-mode/scripts/magpie-sync.py
python $S --selftest      # 先证这把尺会响
python $S check           # 只读漂移表：内容面（逐文件 SHA-256）＋落点面＋注册面
python $S apply --dry-run --profile core   # 看将写哪些字节
python $S apply --profile core             # 正本 → 库 → 各家链接；写前自动备份
```

- **安装档位**：`manifests/install-profiles.json` 定两档——`core`（舰桥 ＋ 内核 ＋ 安装/升级 ＋ 交接）、
  `full`（全部自动件）。`apply/check --profile core|full`。
- **安装回执**：库根 `.kai-mode-source.json` 记来源根、HEAD、档位、技能清单与每技能哈希。
  写库前整包备份到 `<库根>/.backups/`（保留 5 份），失败自动还原。
- **旧 V1 技能下线**：标准路径走 `scripts/uninstall-v1.py`（见「卸载 V1」节）；它内部调 `magpie-sync.py` 的退役函数，
  把指定技能移到 `<库根>/.retired/<时间>/` 并摘掉宿主链接。只摘符号链接，实体目录只报告不动。写前整包备份。
- 手动件（如 `harness-audit`）不进档位；需要时单独 `install:manual` 装。
- **安装面与开发件分开**：只装技能运行件；`tests/`、`__pycache__`、`.pytest_cache`、`*.pyc` 不装。
- 加技能＝三步：① 放目录 `<插件>/skills/<名>/`；② 新剧本才在 marketplace 加插件；
  ③ 跑 `python scripts/plugin-check.py`。
- 库位**不写死机器路径**：沿既有链接反查；读不出用 `KAI_MAGPIE_LIBRARY`，
  仍读不出就 rc=2 如实报，不猜路径。
- 三条硬规矩：① 写库前**整包备份 ＋ SHA-256 基线**；② 脚本只新增、只覆盖同路径，绝不删库里多出来的东西
  （唯一例外＝安装面排除的开发件与缓存）；③ 中央库进程在跑时可能用内存版覆盖回注册档 ⇒ `apply` 后隔 ≥90 s 再 `check`。

### 3. 把舰桥设为默认入口

用户要求「忘了触发也默认舰桥」。这一步只写项目级指令，不动宿主全局配置。

在项目 `CLAUDE.md` 或 `AGENTS.md` 末尾加一段（已存在则跳过）：

```markdown
## 默认入口

用户没有显式点名其它技能、也没打斜杠命令时，一律按舰桥执行：
先读安装到宿主的 `bridge` 技能（`core/skills/bridge/SKILL.md`）全文，再按其流程处理。
```

- 只写项目级，不写全局；不同项目可以有不同的默认入口。
- 宿主支持 `UserPromptSubmit` 钩子时，可另装一条只读提示钩子，把上面这句作为附加上下文；
  钩子只提示、不改用户输入。宿主没有钩子口 ⇒ 只靠指令文件，登记为软约束。
- 验收：新开一个会话，直接说「现在到哪了」，不再打任何斜杠命令，应能读到 `coding status` 并按舰桥回报。

### 4. worktree 环境自检（三项，缺一报错不静默）

工作树里**没有**主树运行时与依赖目录（检查目录由配置实例 `runtime` 段声明，均不入库）。

| 项 | 标准 | 缺了怎么办 |
|---|---|---|
| 后端解释器 | 主树正本解释器的**绝对路径**（`runtime.backend_python`；装机写入 env `KAI_BACKEND_PYTHON`） | 报「缺解释器」并给绝对路径；不许退化成随便一个 `python` |
| node | 主树正本 node 的绝对路径（`runtime.node`） | 报「缺 node」并点名路径 |
| 依赖 | 树内用**项目自己的包管理器**离线装后才有前端定向测例环境 | 报「缺依赖」并点名判定结果；绝不 junction/软链主树 `node_modules` |

```bash
test -x "$KAI_BACKEND_PYTHON" && "$KAI_BACKEND_PYTHON" -V
node_bin="<主树>/<runtime.node 主树相对路径>"; test -x "$node_bin" && "$node_bin" -v
test -d <前端目录>/node_modules || echo "缺依赖：树内用项目自己的包管理器离线装"
```

- 全量前端腿不在工作树跑：由门卫/舰桥在主树合并后跑。
- 工作树里的环境假红先回主树复核再定性，别开产品票。

### 5. doctor

```bash
python scripts/ready.py                  # 快检三合一（脚本在项目仓）
python scripts/env-doctor.py --hooks     # 钩子与正本同源
python scripts/framework-gate.py --selftest
```

读数**只能出自门**；红就报红，不静默吞错。长期红的门只走基线文件，不在本技能里改判据。

### 6. 开票归属守卫（缺 `--repo` 即拒）

> 治的病：在项目仓里跑 `gh` 会按 cwd 落仓，随手 `gh issue create` 就把框架问题开到项目仓。
> 判据住脚本、不住正文：`scripts/issue-guard.py`；**本技能是唯一安装口**。

1. **先探**：读宿主 `settings.json` 的 `hooks.PreToolUse`，找 `issue-guard.py`。已挂 → 只跑 `--self-test`。
2. **再装**（用户点头才写；写前备份 `settings.json`）：钩子形状见宿主适配说明，本文件不复述宿主字段。
   宿主没有钩子口 ⇒ 三格登记 `no-hook-surface`，不许谎报已拦截。
3. **验收**：项目仓里 `gh issue create --title probe` → 被拒且提示实例 `issue.repo`；
   加 `--repo <实例里的仓>` → 放行。
4. **不碰**：不自动改用户其它 hook，不替项目仓写 `.githooks/`，只拦开票/开 PR 两类。

### 7. 缺件登记与交接

- 缺件登记判据见 `../principle-report-missing-parts/SKILL.md`；本步管交接。
- 装完交一张「安装回执」：装了哪几件技能、默认入口落在哪个文件、三项环境读数、doctor 结果、缺件清单、宿主落点核对。
- **宿主落点核对**：① `bridge` 与 `coding` 在宿主技能目录；② 新上下文口可用（子代理／独立进程／新会话至少一条），
  不可用就登记 `no-new-context`；③ 旧 V1 链接已摘或已列清单。
- 不把状态写进本地台账：票状态只看 GitHub；run 状态只看 `.coding/runs/`。

## 卸载 V1（下线腿）

> 机场体系已整体下线（裁决记在框架仓 ADR 目录）；本腿把宿主安装面上的 V1 残留清干净。
> 判据住脚本、不住正文：`scripts/uninstall-v1.py`；本节只写流程位与验收。

**什么时候走**：缺口扫描第 10 项探到 V1 残留；或用户明确说「卸载 V1 / 机场体系下线」。

**四步（探 → 退 → 核 → 回执）**：

```bash
S=core/skills/set-kai-mode/scripts/uninstall-v1.py
python $S --repo <项目仓>          # ① 只读探测：七个 V1 技能 × 库/注册档/宿主链接/实体目录，外加定时任务与项目实例残留
python $S --apply                  # ② 退役（用户点头后才跑）：写前整包备份 → 库目录移 .retired → 摘宿主链接 → 清注册档
python $S --repo <项目仓>          # ③ 复核：应为全「—」；有残留按缺件三格登记
python $S --json                   # ④ 机器读（探测或 --apply 的回执）
```

**脚本做**：备份中央库；把 `ace`/`copilot`/`ground-crew`/`loop`/`pilot`/`second-officer`/`tower` 的
库目录移进 `<库根>/.retired/<时间>/`、摘掉各宿主指向它们的符号链接、从 `library.json` 的
`skills[]` 与 `applied[*].skills` 删条目；产出回执 JSON。

**脚本不做（要人拍，回执里逐条列）**：

- 宿主落点里的**实体目录**（非符号链接的拷贝，如 `.codex/skills`）——只报告；要清就整目录移进备份位，不删。
- 宿主定时任务 / automation（如 Codex `automations/*` 里的塔台轮巡）——只报告；停用或移走由用户执行。
- 项目配置实例的 V1 键（`ship_mode`、`day_tables*`、`lanes`、`tower_cron`、三键门禁）——只报告；
  迁移走本文件「配置实例」节的 schema 迁移腿，逐键 diff，不静默删字段。

**验收**：① 复核全「—」；② 回执里有 `retired` 清单与备份路径；③ 残留项（实体目录 / 定时任务 / 实例键）
逐条写进缺件登记，不许写成「已清零」。

## 配置实例（schema 5）

schema 5 删掉了 V1 的日表、车道、塔台定时器与三键门禁；保留而且**只有活读者**的键：

| 段 | 键 | 读者 |
|---|---|---|
| `project` | 项目名 | 安装器、脚本 |
| `host` | `adapter` | 安装器选宿主适配 |
| `registry` | `playbooks[]`、`adrs.dir`、`rules.dir`、`skills.project_skills_dir` | 入口与安装器 |
| `paths` | `handoff_dir`、`ideas_dir`、`audit_dir`、`module_cards`、`dashboard`、`state_dir` | 接交、想法池、看板、运行态 |
| `runtime` | `backend_python`、`node`、`deps.check_dir_rel` | worktree 自检 |
| `gates` | `finish_cmd` | V2 发货收尾门 |
| `issue` | `platform`、`repo`、`boom_summary_ticket` | 开票、关票、想法池 |

**已删除（schema 4 → 5）**：`ship_mode`、`paths.day_tables_dir`、`paths.day_table_pattern`、`paths.lanes`、
`tower_cron`、`issue.verdict_marker`、`registry.skills.loop_dir`、`gates.captain_preflight`、
`gates.scope_check`、`gates.close_gate`。
迁移时逐字段 diff 留档；多出来的键逐条列给用户，点头才删。

## 改配置的四条规矩

1. **一次一项**，改完当场跑验收，读数写进对应票面。**没读数＝没改完**。
2. **一个语义只许一个家**：判据细则见 `../principle-one-semantics-one-home/SKILL.md`。
3. **机制类改动先设计后落地**：先出图与代价进 ADR；用户拍板后才动执行面。
4. **宿主中立**：依赖某家专有能力必须同时有 ①能力探测 ②降级腿 ③缺件如实登记。

## 红线与冻结面

- 红线照旧先问：**花钱** / **对外真发布** / **不可回滚或改写历史**的 git 动作 / **删任何未提交内容**。
- 不碰项目仓 `.githooks/**`；确需改先问。钩子只当发令员：只写标记、fail-open，不派工。
- 付费档宿主：起它必须显式授权；没授权就只用免费档或人工。
- 写中央库前必须整包备份＋哈希基线；库内凭据只报字段名与位置，严禁抄值。
- 本技能不施工、不发货、不关票、不写产品代码。

## 与相邻文件的关系

| 你要的 | 去哪 |
|---|---|
| 用户入口、清场、发货 | `../bridge/SKILL.md` |
| 规划与拷问方法 | `../kai-mode/SKILL.md` |
| 施工与发货命令 | `../../../v2/skills/coding/SKILL.md` |
| 方法库 | `../../../methods/skills/` |
| 想法池 | `../../../intake/skills/kai-boom-idea-log/SKILL.md` |
| 看板（可选） | `../../../board/skills/flight-info/SKILL.md` |
| 改了技能正本怎么让各家吃到 | 本技能「2. 装技能到宿主」 |
