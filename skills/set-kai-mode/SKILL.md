---
name: set-kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "项目仓 docs/artifacts/adrs/框架仓旧裁决-airport-rebuild-four-roles.md"
    note: "唯一现行裁决：四角色（D1）、并发与隔离（D2）、任务面（D3）、30 分钟轮巡（D5）、清退与新增（D8）"
  - resource: "skills/kai-mode/SKILL.md"
    note: "入口本体；本技能只装它脚下的东西，不改它的流程"
  - resource: "skills/{地勤,塔台,机长,副机长}/SKILL.md"
    note: "四角色技能正本；本技能负责把它们装到宿主"
  - resource: "skills/set-kai-mode/scripts/magpie-sync.py"
    note: "技能正本 → Magpie 中央库 → 各家宿主链接的回写口"
description: >
  kai-mode 的初始化安装入口（不是日常施工）：一步配置——注入方法论与技能、把四角色技能装到宿主
  （Magpie / Qoder 或其它宿主）、装 30 分钟塔台定时器、worktree 环境自检（主树正本解释器绝对路径、
  node、依赖三项）、doctor、缺件如实登记。触发：新 agent 接手装配、换宿主、装/改定时器、修技能落点、
  问「这套东西都住在哪」。不做日常施工。
version: 4.0.0
updated: 2026-10-21
---

# Set Kai Mode —— kai-mode 的初始化安装

> `/kai-mode` 是**用**这套框架的入口；`/set-kai-mode` 是**装**这套框架的入口。
> 本技能只做安装与配置，**不做日常施工**：不写产品代码、不排班、不发货、不关票。
> 判据住在 ADR 与脚本里；本文件只回答三件事：**东西在哪、怎么装、装完跑什么自证**。

## 什么时候进这里

- 新 agent / 新机器第一次接手：从零装到能跑。
- 换宿主或换执行体（Qoder、Codex、opencode、Claude Code 等）。
- 装 / 改 / 停 30 分钟塔台定时器。
- 技能改了却没在别家生效（正本与库不一致）。
- worktree 里跑不动（缺解释器、缺 node、缺依赖）。
- 撞见「同一条判据两处说法不一样」——配置面漂移，回到这里对表。

## 一步配置（装完即可用）

按顺序一次装完六件；每件都要**回读**，缺件写进「缺件登记」。

| # | 装什么 | 验收 |
|---|---|---|
| 1 | 注入方法论与技能（仓库内正本） | 七个技能文件在位，入口/角色/协议互指一致 |
| 2 | 装技能到宿主（四角色 ＋ 入口/安装/协议技能） | 宿主技能列表里能看见，内容与正本同哈希 |
| 3 | 装 30 分钟塔台定时器 | `list` 回读 `enabled=true`、周期 30 分钟 |
| 4 | worktree 环境自检（三项） | 解释器 / node / 依赖三项都有明确读数 |
| 5 | doctor | 项目仓 `ready.py` 与 `env-doctor` 全绿或如实点红 |
| 6 | 缺件登记与交接 | 缺什么、卡在哪、要谁拍，写进日报 |

### 1. 注入方法论与技能

- 正本全部住在仓库里（中立层），任何宿主一进仓库即生效：
  - 入口：`skills/kai-mode/SKILL.md`
  - 安装：`skills/set-kai-mode/SKILL.md`（本文）
  - 四角色：`skills/{地勤,塔台,机长,副机长}/SKILL.md`
  - 单票闭环：`skills/loop/SKILL.md` ＋ `loops/loop-protocol.md`
- 项目仓把它们落在 `.ai/skills/{project-skills/,loop}/`；剧本登记面＝项目仓 `.ai/router.md`；
  新增剧本在那里加一行，**不在本文件或入口里复制判据**。

### 2. 装技能到宿主

> 仓库里的 SKILL.md 是**正本**；宿主真正加载的往往是另一份拷贝（如 Magpie 中央库
> `<...>/magpie/data/library/skills/<名>/`，各家宿主目录只是指向它的链接）。
> **改了正本不回写，只有当下这一家生效**——正本与库是拷贝关系。

```bash
S=skills/set-kai-mode/scripts/magpie-sync.py
python $S --selftest      # 先证这把尺会响
python $S check           # 只读漂移表：内容面（逐文件 SHA-256）＋落点面＋注册面
python $S apply --dry-run # 看将写哪些字节
python $S apply           # 正本 → 库 → 各家链接
```

- 要装/更新的技能：`kai-mode`、`set-kai-mode`、`loop`、`地勤`、`塔台`、`机长`、`副机长`。
- 库位**不写死机器路径**：沿既有链接反查；读不出用环境变量 `KAI_MAGPIE_LIBRARY` 指到 `<...>/library/skills`，
  仍读不出就 rc=2 如实报，不猜一个路径写下去。
- 三条硬规矩：① 写库前**整包备份 ＋ SHA-256 基线**；② 脚本**只新增、只覆盖同路径，绝不删**库里多出来的东西；
  ③ Magpie 进程在跑时可能用内存版覆盖回注册档 ⇒ `apply` 后隔 ≥90 s 再 `check` 一次。
- 存证同批归零：`python scripts/skill-attest.py attest --by human:<批准人> && python scripts/skill-attest.py verify`（rc=0；脚本在项目仓）。
- 其它宿主没有中央库时：按宿主的技能目录**拷贝同一份正本**，拷完逐文件比哈希；不做「只在聊天里贴一遍」。

### 3. 装 30 分钟塔台定时器

**目标形状**：塔台每 30 分钟醒一次，先排班、后发货；也可人工 `/塔台` 立即跑。
**手段按宿主选**（框架仓旧裁决／D5）：Qoder 推荐 `qoder_cron`；其它宿主探测能力后按同一契约装配。

**四步：探测 → 建 → 复读 → 缺件登记**

1. **探测**（结果一律现测，不抄旧读数）：

   ```bash
   command -v qodercli qoder codex opencode 2>/dev/null   # 谁有 shell 入口（Windows 漏报时用 Get-Command）
   git config core.hooksPath                              # 钩子指到哪
   python -V && node -v                                   # 运行时
   ```

   三问：宿主有没有**定时会话口**（有＝能装定时器）？有没有**会话创建口**（能否宿主内拉起角色）？
   项目仓 `.githooks/` 是否与正本同源（项目仓 `python scripts/env-doctor.py --hooks`）？

2. **建**：一枚塔台任务即可，**不要四枚并存**。
   - 周期：`*/30 * * * *`（默认 30 分钟；周期可调，改这里一处）。
   - 工作目录：主树绝对路径。
   - 执行模式：独立会话（Qoder `outputMode=independent`）。
   - prompt 只放**薄壳**：`读取并执行 skills/塔台/SKILL.md 全文；任务名 cron-tower-<日期>-<时分>`。
     长规则只住技能正本，任务配置里不存第二份。
   - Qoder 建任务时统一 `executionAuthorization=true`（Full Access，与既有定时任务同档）。
   - 旧的四枚定时任务：**停用或删除**，不得与 30 分钟塔台并存（框架仓旧裁决）。
     顺序：先 `disable` → 等 `runningAt` 为空或确认已停 → 再 `remove`；**别对正在跑的直接 remove**。

3. **复读**（建完不算完，用之前再读一次）：
   `qoder_cron list` 或宿主的定时口，回读 `enabled` / `nextRunAt`（换算成人话几点）/ `lastRunAt` 有没有动。
   **`enable` 返回成功不等于它一直开着**；看到 `pauseReason=manual` ＝ 有人手动停，**别自动重开**，
   报状态时把「建过、现在是停的」两句都写出来。建完写一条 jobId 到本机配置（不入 tracked 模板）。

4. **缺件如实登记**：宿主没有定时口 ⇒ 写「缺定时口，塔台只能人工 `/塔台`」，**不许写成已实现**；
   进日报「要你拍」或平台私有清单，附缺的是什么口、什么权限。

**其它宿主：先探测，再把可用档位给用户选**（一次一问，推荐项排第一）：

| 档 | 宿主有什么 | 怎么装 |
|---|---|---|
| 直接定时 | 角色会话自带调度器的 run 工具 | 直接建 30 分钟塔台任务 |
| 会话创建 | 有 `create_chat_session` 类工具 | 定时任务开薄壳子会话，由子会话按铃叫塔台 |
| shell 启动 | 有 `opencode run` / `codex exec` 等入口 | 定时任务调 shell 起角色（付费档须显式授权） |
| 都没有 | — | 人工 `/塔台`，缺件如实登记 |

塔台之外的角色：宿主有会话创建口就由塔台 / kai-mode 拉起；没有就人工喊角色口令。
选完把档位写进本机配置并**做一次自证**（到点真的跑一轮、目标真的起来），未实测的 flag 不写进正本。

### 4. worktree 环境自检（三项，缺一报错不静默）

工作树里**没有** `runtimes/` 与 `node_modules`（二者不入库）。所以每棵工作树开工前先量三项：

| 项 | 标准 | 缺了怎么办 |
|---|---|---|
| 后端解释器 | 主树正本解释器的**绝对路径**（项目配置 `runtime` 段指定，如 `<主树>/kai-vass-v2/runtimes/python/Scripts/python.exe`），写进 `KAI_BACKEND_PYTHON` | 报「缺解释器」并给绝对路径；**不许退化成随便一个 `python`** |
| node | 主树正本 node 的绝对路径（如 `<主树>/kai-vass-v2/runtimes/node/node.exe`） | 报「缺 node」并点名路径 |
| 依赖 | 树内 `pnpm install --offline` 后才有前端定向测例环境 | 报「缺依赖」并给安装命令；**绝不 junction 主树 `node_modules` 后跑 pnpm**（会改写主树链接） |

```bash
test -x "$KAI_BACKEND_PYTHON" && "$KAI_BACKEND_PYTHON" -V
test -x "<主树>/kai-vass-v2/runtimes/node/node.exe" && "<主树>/kai-vass-v2/runtimes/node/node.exe" -v
test -d <前端目录>/node_modules || echo "缺依赖：树内 pnpm install --offline"
```

- 全量前端腿**不在工作树跑**：由审查/塔台在主树合并后跑。
- 工作树里的环境假红（`?url` 收集失败等）先回主树复核再定性，别开产品票。

### 5. doctor

```bash
python scripts/ready.py                  # 快检三合一（HOOKS / READY_RED 等；脚本在项目仓）
python scripts/env-doctor.py --hooks     # 钩子与正本同源（比 sha256，不只看在不在）
python scripts/framework-gate.py --selftest   # 推前框架门自证
```

读数**只能出自门**；红就报红，不静默吞错后返回成功。长期红的门只走基线文件，不在本技能里改判据。

### 6. 缺件登记与交接

- 缺件写三格：**缺什么口 / 卡在哪一步 / 要谁拍**；进 `handoff/` 当日日报「要你拍」段。
- 装完交一张「安装回执」：装了哪几件技能、定时器 jobId 与周期、三项环境读数、doctor 结果、缺件清单。
- **不把状态写进本地台账**：票状态只看 GitHub；日表只写排班视图。

## 配置面总表（唯一对照表）

| 可调项 | 正本住在哪 | 改完跑什么 |
|---|---|---|
| 四角色职责与权限 | 框架仓旧裁决 **D1** | `grep -rn "地勤\|塔台" skills/` 逐处认，出现第二本定义即返工 |
| 并发、名额与隔离 | 框架仓旧裁决 **D2** | 机长/副机长技能里的「2 张」与 ADR 一致 |
| 任务表格式与领取方式 | 框架仓旧裁决 **D3** ＋ `.ai/tasks/` | 日表 5–10 行、只由塔台写 |
| 一轮流程（排班→施工→审查→发货） | 框架仓旧裁决 **D4** | 用一张真票走通全链路 |
| 发货与 push 边界 | 框架仓旧裁决 **D5** ＋ 塔台技能 | 塔台独占 push；机长/子代理不 push |
| 失败恢复与断点 | 框架仓旧裁决 **D6** | 断点三件套（日表＋Issue 评论＋分支提交）齐 |
| 技能注入（正本 → 宿主） | 本技能「2. 装技能到宿主」＋ `magpie-sync.py` | `magpie-sync.py check` 三面全绿 ＋ `skill-attest verify` rc=0 |
| 塔台定时器周期 | 本技能「3.」＋ 塔台技能 | `list` 回读周期与 `enabled`；人工 `/塔台` 也能跑 |
| worktree 环境三项 | 本技能「4.」＋ 本机 `agents.local.md`（不入库） | 三项各有读数；缺件报错不静默 |
| 剧本登记面 | 项目仓 `.ai/router.md` | 新增剧本只此一行，入口与技能不复述 |

## 改配置的四条规矩

1. **一次一项**，改完当场跑「改完跑什么」那一列，读数写进对应票面。**没读数＝没改完**。
2. **一个语义只许一个家**：ADR/脚本是正本，技能与 router 是指针；想在第二处写第二条判据，先问「第一条住哪」。
3. **机制类改动先设计后落地**：先出图与代价进 ADR；写进 ADR 不算落地，用户拍板后才动执行面。
4. **宿主中立**：依赖某家专有能力（会话口 / 定时口 / 子代理类型）必须同时有 ①能力探测 ②降级腿
   ③缺件如实登记，否则只能进「平台私有」清单，**不得写进流程正本**。

## 红线与冻结面（进这里也照样有效）

- 红线照旧先问：**花钱** / **对外真发布** / **不可回滚或改写历史**的 git 动作 / **删任何未提交内容**。
- 不碰项目仓 `.githooks/**`；确需改先问（红线邻面）。钩子只当发令员：只写标记、fail-open，不派工。
- Codex 是付费档：起它必须显式 `KAI_WATCHDOG_ALLOW_PAID=1`；没授权就只用免费档或人工。
- 写 Magpie 中央库前必须整包备份＋哈希基线；库内凭据**只报字段名与位置，严禁抄值**。
- 本技能不排班、不发货、不关票、不写产品代码——那些是塔台/机长/地勤的活。

## 与相邻文件的关系

| 你要的 | 去哪 |
|---|---|
| 怎么提需求、拷问、定稿、路由 | [`skills/kai-mode/SKILL.md`](../kai-mode/SKILL.md) |
| 四角色各自怎么干 | [`skills/{地勤,塔台,机长,副机长}/SKILL.md`](../) |
| 单票闭环怎么跑 | [`skills/loop/SKILL.md`](../loop/SKILL.md) ＋ [`loops/loop-protocol.md`](../../loops/loop-protocol.md) |
| 为什么这么设计 | 项目仓 `docs/artifacts/adrs/框架仓旧裁决-airport-rebuild-four-roles.md` |
| 本机环境事实（解释器、node、坑） | 本机 `agents.local.md`（不入库，每台一份） |
| 改了技能正本怎么让各家吃到 | 本技能「2. 装技能到宿主」＋ `magpie-sync.py` |
