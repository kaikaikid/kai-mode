---
name: set-kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "../kai-mode/SKILL.md"
    note: "入口本体；本技能只装它脚下的东西，不改它的流程"
  - resource: "../../../airport/skills/{ground-crew,tower,pilot,copilot,ace}/SKILL.md"
    note: "五岗位技能正本；本技能负责把它们装到宿主"
  - resource: "scripts/magpie-sync.py"
    note: "技能正本 → Magpie 中央库 → 各家宿主链接的回写口"
description: >
  kai-mode 的初始化安装入口（不是日常施工）：**先看缺什么、列出推荐清单跟用户确认，再只装缺的**，
  避免重复安装。覆盖：注入方法论与技能、把岗位技能装到宿主（Magpie / Qoder 或其它宿主）、
  装 60 分钟唤醒定时器（只唤醒塔台）、worktree 环境自检（主树正本解释器绝对路径、node、依赖三项）、
  项目配置实例生成/校验/迁移（schema 2→3→4）与装机回执「模型核对」格、按项目生成技能骨架（首例验收/验证）、
  doctor、缺件如实登记。触发：新 agent 接手装配、换宿主、装/改定时器、修技能落点、
  给项目出技能骨架、迁旧配置实例、问「这套东西都住在哪」。
  不做日常施工。
version: 5.0.0
updated: 2026-10-25
allowed-tools: Bash(*) Read Write Edit
compatibility: Requires python3, git
---

# Set Kai Mode —— kai-mode 的初始化安装

> `/kai-mode` 是**用**这套框架的入口；`/set-kai-mode` 是**装**这套框架的入口。
> 本技能只做安装与配置，**不做日常施工**：不写产品代码、不排班、不发货、不关票。
> 判据住在 ADR 与脚本里；本文件只回答三件事：**东西在哪、怎么装、装完跑什么自证**。

## 什么时候进这里

- 新 agent / 新机器第一次接手：从零装到能跑。
- 换宿主或换执行体（Qoder、Codex、opencode、Claude Code 等）。
- 装 / 改 / 停 60 分钟唤醒定时器（只唤醒塔台，不是角色本体）。
- 技能改了却没在别家生效（正本与库不一致）。
- worktree 里跑不动（缺解释器、缺 node、缺依赖）。
- 撞见「同一条判据两处说法不一样」——配置面漂移，回到这里对表。
- 给目标项目仓生成项目本地技能骨架（生成式腿，首例＝验收/验证技能）。
- 项目仓配置实例还是 schema 2（读取端记 warn）——走迁移腿，别拖过双仓回归期。

## 装到别的项目：QA 初始化（先跑这个，再走下面的六步）

装进一个新项目不是拷文件，是**把项目差异问清楚**。一条命令跑完十问，生成实例 ＋ 铺两个组件：

```bash
python scripts/init-project.py --repo <目标仓>            # 逐题问，每题带默认，回车即默认
python scripts/init-project.py --repo <目标仓> --yes      # 全默认（先看 dry-run 输出）
python scripts/init-project.py --repo <目标仓> --answers a.json   # 机器填
```

> 本命令在 **kai-mode 框架仓根**执行；技能装到项目仓后，用 `<框架仓根>/scripts/init-project.py`（框架仓根见中央库来源标记或安装回执），**不是**项目仓的 `scripts/`。维护者的门禁脚本同理只住框架仓，项目侧收工跑项目自己的门禁。

**十问（顺序固定，缺一不装）**：

| # | 问什么 | 默认 | 落到哪 |
|---|---|---|---|
| 1 | 项目名 | 目录名 | `project` |
| 2 | 票源（github / none） | `github` | `issue.platform` |
| 3 | 仓库 slug（owner/name） | 从 `git remote` 猜 | 票面引用 |
| 4 | 日表目录 | 配置模板默认值 | `paths.day_tables_dir` |
| 5 | 交接目录 | `handoff` | `paths.handoff_dir` |
| 6 | 想法目录 | `ideas` | `paths.ideas_dir` |
| 7 | ADR 目录 | `docs/adr` | `registry.adrs.dir` |
| 8 | 宿主 | 回车＝本机当前宿主（**不设 qoder 默认**，模板铁律禁止偏置） | `host.adapter` |
| 9 | 收工门禁脚本（本项目没有就留空＝null，别抄别仓的门名） | 空 | `gates.captain_preflight` |
| 10 | 想法池汇总票号 | 空 | `issue.boom_summary_ticket` |

**脚本顺手铺两个组件**（这就是「作为组件引入」的落法）：

| 组件 | 铺什么 | 为什么合起来装 |
|---|---|---|
| `handoff/` | 八槽（含 `50-comms` 角色沟通面）＋ 规范 ＋ 两份模板 | 交接与角色传话同一层，同一套 frontmatter 与门禁 |
| `docs/` | `docs/adr/` 目录 ＋ `GLOSSARY.md` 骨架 | 长期正本面；与 handoff 并列，靠单向提炼联动 |

已存在的一律**不覆盖**。缺件（如票源选 github 但没 slug）脚本直接拒绝，不生成半成品实例。

## 一步配置（装完即可用）

**铁律：先看缺什么，再装。** 进本技能第一件事是跑「第 0 步 · 缺口扫描」（全只读），
把六件各自的现状列成一张**缺口清单**——已就位的明确标「跳过，不重复装」，缺的才列成「推荐处理项」。
**先把清单念给用户听，用户点头才执行对应步骤**；绝不闷头把六步全跑一遍（那会重复装已经就位的东西）。

| # | 装什么 | 验收 |
|---|---|---|
| 0 | **缺口扫描（只读，先看缺什么）** | 出一张缺口清单：每项标「已就位/跳过」或「需处理（原因）」，先念给用户 |
| 1 | 注入方法论与技能（仓库内正本） | 16 个技能文件在位（以注册表 `install:auto` 为准），入口/角色/协议互指一致 |
| 2 | 装技能到宿主（岗位技能 ＋ 入口/安装/协议技能） | 宿主技能列表里能看见，内容与正本同哈希 |
| 3 | 装 60 分钟唤醒定时器 | `list` 回读 `enabled=true`、周期 1 小时 |
| 4 | worktree 环境自检（三项） | 解释器 / node / 依赖三项都有明确读数 |
| 5 | doctor | 项目仓 `ready.py` 与 `env-doctor` 全绿或如实点红 |
| 6 | 缺件登记与交接 | 缺件如实登记进日报（三格判据唯一正本：[`principle-report-missing-parts`](../principle-report-missing-parts/SKILL.md)） |

### 0. 缺口扫描（只读，先看缺什么再决定装不装）

> **这一步只读数、不写盘。** 进本技能先跑它，把六件各自的现状列成「缺口清单」，再决定后面装不装。

| 项 | 只读探法 | 判「已就位（跳过）」 | 判「需处理」 |
|---|---|---|---|
| 1 正本技能 | 按 `.claude-plugin/marketplace.json` 的插件目录里 `skills/*/SKILL.md` 派生清单（当前 19 条自动件 ＋ 1 条手动件），逐个检查 `SKILL.md` ＋ 互指 grep | 清单内都在、互指路径一致 | 缺文件或互指断裂 |
| 2 宿主同步 | `python skills/set-kai-mode/scripts/magpie-sync.py check`（按回执档位；无回执=full） | 漂移表三面全绿（内容/落点/注册） | 有漂移文件（列出具体哪些） |
| 3 唤醒定时器 | 现测证据：项目配置 `paths.handoff_dir` 当日日报里 `cron-tower-*` 轮次 / 宿主 `list` 回读 `enabled` | 今日有真实运行轮次或 `enabled=true` | 无运行证据且宿主无定时口 |
| 4 环境三项 | `test -x` 解释器/node、`test -d node_modules` | 三项都有明确读数 | 任一项缺（报绝对路径） |
| 5 门禁 | 项目仓 `ready.py` / `env-doctor --hooks` | 全绿或只基线告警 | 有红（列出哪道门） |
| 6 存证 | 项目仓 `python scripts/skill-attest.py verify`（项目仓有该脚本时） | rc=0 全过 | 有哈希不符（列出哪个文件） |
| 7 项目配置实例 | 仓库根探测（只读）：`git rev-parse --show-toplevel` → 读 `<root>/.ai/kai-mode.project.json` 的 `schema` 字段 | schema 4 实例在位且过「模型核对」 | 无实例 → 按 D4 报缺件三格（怎么补＝本技能生成或手工按模板填）；schema 2/3 → 走「迁移腿」 |
| 8 宿主技能与命令 | 列宿主技能目录（`adapters/<宿主>.md`）与插件命令 | 角色技能与命令都能读到 | 缺落点 → 按 `adapters/<宿主>.md` 补，软约束要登记 |

**产出与动作**：
- 把清单念给用户：**已就位逐项说「跳过，不重复装」**；**需处理项列成推荐清单**，附原因。
- 用户点头后才执行步骤 1–6 里对应的「需处理」项；**标「已就位」的项只回读确认、不做任何写操作**（不重装、不重同步、不重建定时器）。
- 一条铁律：**能只读判定的，绝不做写操作**；写盘（sync apply / 建定时器 / attest）只在缺口清单确有该项时才发生。
- 步骤 1–6 因此变成「执行缺口清单」——只动清单里标了需处理的项，不是无脑六步全跑；
  两条腿**探到才走**：清单第 7 项探到 schema 2 实例 → 走迁移腿，用户要点生成 → 走生成式腿。

### 1. 注入方法论与技能

- 正本全部住在仓库里（中立层），任何宿主一进仓库即生效：
  - 入口与安装：`core/skills/{kai-mode,set-kai-mode}/SKILL.md`
  - 岗位技能：`airport/skills/{ground-crew,tower,pilot,copilot,ace}/SKILL.md`
  - 单票闭环：`airport/skills/loop/SKILL.md` ＋ `airport/skills/loop/references/loop-protocol.md`
  - 看板展示层：`board/skills/flight-info/SKILL.md`（SQLite 落库 ＋ 模块化采集/判据/渲染；装配与刷新都在它的 `scripts/`；板库根＝板配置 `output.root`，相对项目仓根）
- 项目仓落点从项目配置实例读：项目技能目录 `registry.skills.project_skills_dir`、单票闭环目录 `registry.skills.loop_dir`；
  剧本登记行收进配置实例 `registry.playbooks[]`（项目仓 router.md 已退役）；
  新增剧本只加登记行，**不在本文件或入口里复制判据**。
- 两种布局都认：项目仓 `registry.skills.project_skills_dir/<名>`（`loop` 在 `registry.skills.loop_dir`）与本仓
  `<插件>/skills/<名>`；`magpie-sync.py` 按这两种布局反查正本根。

### 2. 装技能到宿主

> 仓库里的 SKILL.md 是**正本**；宿主真正加载的往往是另一份拷贝（如 Magpie 中央库
> `<...>/magpie/data/library/skills/<名>/`，各家宿主目录只是指向它的链接）。
> **改了正本不回写，只有当下这一家生效**——正本与库是拷贝关系。

```bash
S=core/skills/set-kai-mode/scripts/magpie-sync.py
python $S --selftest      # 先证这把尺会响
python $S check           # 只读漂移表：内容面（逐文件 SHA-256）＋落点面＋注册面
python $S apply --dry-run --profile core   # 看将写哪些字节（core 最小闭环）
python $S apply --profile core             # 正本 → 库 → 各家链接；写前自动备份
```

- **角色命令与技能随插件装**：人格文件已退役；派活由技能正文让宿主起新上下文。
  宿主落点（技能目录、命令、子代理、定时口）按 `adapters/<宿主>.md`：探测 → 落点 → 降级 → 装完自证。
  落点必须项目级，不装全局。
- 要装/更新的技能（装机清单＝`.claude-plugin/marketplace.json` 列出的插件目录里 `skills/*/SKILL.md`；
  安装器现场派生，不落第二份清单）：
  `airport` 6 条、`core` 10 条（9 自动＋1 手动）、`board` 1 条、`intake` 1 条、`ops` 2 条。
- **安装档位**：`manifests/install-profiles.json` 定两档——`core`（9 条最小闭环：入口/安装/协议/五岗位/交接）、
  `full`（19 条自动件全部）。`apply/check --profile core|full`；缺省读库根回执里的档位，无回执＝`full`。
- **安装回执**：库根 `.kai-mode-source.json` 记来源根、HEAD、档位、技能清单与每技能哈希；
  `doctor` 的 `install-receipt` 项校验。回执里另记「宿主落点」：技能目录、命令名、子代理口。写库前整包备份到 `<库根>/.backups/`（保留 5 份），失败自动还原。
- 手动件（如 `harness-audit`）不进档位；需要时单独 `install:manual` 装。
- **全局数据根**：宿主的非项目数据统一按
  agent-data-layout
  放 `KAI_AGENT_DATA_ROOT`；各宿主专用变量住适配器文档，项目数据仍由项目仓自管。
- **安装面与开发件分开**：只装技能运行件；`tests/`、`__pycache__`、`.pytest_cache`、`*.pyc` 不装，
  `apply` 会在备份后清掉库里残留的这类文件。边界正本＝`manifests/package-layout.json`
  ，doctor 的 `package-layout`
  会实跑初始化器对账；用户项目里的骨架只按该清单生成，不会带出本仓 ADR 或交接历史。
- **旧角色一次性迁移**：角色改名后首次 apply 可加 `--retire-legacy`——旧中文目录移到 `<库根>/.retired/<时间>/`，
  宿主旧链摘掉；符号链接才摘，实体目录只报告不动；写前照样整包备份。
- **两套定时器各管各的，别混**：本技能装的是**塔台唤醒定时器**（只唤醒塔台；走宿主定时口、每轮拉起 AI 会话，要 token，
  归塔台排班发货，**1 小时一轮**）；看板的刷新**不归它**，走展示层自己的
  `board/skills/flight-info/scripts/install_hook.py` 与 `refresh_if_dirty.py`（git 钩子 ＋ 有脏才刷，零 token、跨 agent）。
- 加技能＝三步：① 放目录 `<插件>/skills/<名>/`（`SKILL.md` ＋ 可选 `scripts/`、`templates/`）；
  ② 新剧本才在 `.claude-plugin/marketplace.json` 加一个插件，已有剧本直接放进去；
  ③ 跑 `python scripts/plugin-check.py`（清单↔目录↔版本↔档位逐条对上）。
- 库位**不写死机器路径**：沿既有链接反查；读不出用环境变量 `KAI_MAGPIE_LIBRARY` 指到 `<...>/library/skills`，
  仍读不出就 rc=2 如实报，不猜一个路径写下去。
- **中央库记住装机来源**（`<库根>/.kai-mode-source.json`，`apply` 真跑完才写，`--dry-run` 不写）：
  从库里那份脚本跑，正本根也回到记录的那个仓，不会被 cwd 里的项目仓顶掉。
  标记坏了／那个仓没了 ⇒ 退回老路（跳过库根，继续按脚本位置／cwd 反查），不硬失败。
- 装完要**当场验装机同步**：比中央库副本与框架仓正本是否逐字相同、
  库记住的来源是不是本仓（红了就跑一次 `apply --root <本仓> --library <库>` 修）。
- 三条硬规矩：① 写库前**整包备份 ＋ SHA-256 基线**；② 脚本**只新增、只覆盖同路径，绝不删**库里多出来的东西
  （唯一例外＝安装面排除的开发件 `tests/`、缓存，`apply` 会清）；
  ③ Magpie 进程在跑时可能用内存版覆盖回注册档 ⇒ `apply` 后隔 ≥90 s 再 `check` 一次。
- 存证同批归零：`python scripts/skill-attest.py attest --by human:<批准人> && python scripts/skill-attest.py verify`（rc=0；脚本在项目仓）。
- 其它宿主没有中央库时：按宿主的技能目录**拷贝同一份正本**，拷完逐文件比哈希；不做「只在聊天里贴一遍」。

### 3. 装 60 分钟唤醒定时器

**目标形状**：定时器每 60 分钟唤醒塔台一次；塔台是独立岗位，人工 `/tower` / kai-mode 也能唤醒。每轮先发货、后补排班（排班放本轮最后）。
**定时器唤醒的塔台实例同样走令牌**：令牌防的是「多实例」——定时器、人工两路并发时靠它互斥，抢不到牌的一轮退位退出；kai-mode 只推荐命令，不唤醒。
**手段按宿主选**（／D5）：宿主能力探测与具体定时口见 `adapters/<宿主>.md`（Qoder 见 `adapters/qoder.md`）；其它宿主按同一契约装配。

**四步：探测 → 建 → 复读 → 缺件登记**

1. **探测**（结果一律现测，不抄旧读数）：

   ```bash
   command -v qodercli qoder codex opencode 2>/dev/null   # 谁有 shell 入口（Windows 漏报时用 Get-Command）
   git config core.hooksPath                              # 钩子指到哪
   python -V && node -v                                   # 运行时
   ```

   三问：宿主有没有**定时会话口**（有＝能装唤醒定时器）？有没有**会话创建口**（能否宿主内拉起角色，仅供人工点火）？
   项目仓 `.githooks/` 是否与正本同源（项目仓 `python scripts/env-doctor.py --hooks`）？

2. **建**：一枚唤醒任务即可，**不要四枚并存**。
   - 周期：`0 * * * *`（默认 1 小时；周期可调，改这里一处）。
   - 工作目录：主树绝对路径。
   - 执行模式：独立会话（Qoder `outputMode=independent`）。
   - prompt 只放**薄壳**：`读取并执行 airport/skills/tower/SKILL.md 全文；任务名 cron-tower-<日期>-<时分>`。
     长规则只住技能正本，任务配置里不存第二份。
   - Qoder 建任务时统一 `executionAuthorization=true`（Full Access，与既有定时任务同档）。
   - 旧的四枚定时任务：**停用或删除**，不得与 60 分钟唤醒定时器并存。
     顺序：先 `disable` → 等 `runningAt` 为空或确认已停 → 再 `remove`；**别对正在跑的直接 remove**。

3. **复读**（建完不算完，用之前再读一次）：
   宿主的定时口 `list` 子命令（Qoder 的具体命令见 `adapters/qoder.md`），回读 `enabled` / `nextRunAt`（换算成人话几点）/ `lastRunAt` 有没有动。
   **`enable` 返回成功不等于它一直开着**；看到 `pauseReason=manual` ＝ 有人手动停，**别自动重开**，
   报状态时把「建过、现在是停的」两句都写出来。建完写一条 jobId 到本机配置（不入 tracked 模板）。

4. **缺件如实登记**：宿主没有定时口 ⇒ 写「缺定时口，塔台只能人工 `/tower`」；
   三格判据与三个不许（不许写成已实现等）的唯一正本＝[`skills/principle-report-missing-parts/`](../principle-report-missing-parts/SKILL.md)。

**其它宿主：先探测，再把可用档位给用户选**（一次一问，推荐项排第一）：

| 档 | 宿主有什么 | 怎么装 |
|---|---|---|
| 直接定时 | 角色会话自带调度器的 run 工具 | 直接建 60 分钟唤醒任务 |
| 会话创建 | 有会话创建口 | 定时任务开薄壳子会话，由子会话自己起塔台 |
| shell 启动 | 有 shell 启动入口（见 `adapters/opencode.md`、`adapters/codex.md`） | 定时任务只调 shell 唤醒塔台；其它角色人工（付费档须显式授权） |
| 都没有 | — | 人工 `/tower`，缺件如实登记 |

角色之间不互相唤醒；塔台之外的角色只由人工喊口令启动。
宿主有会话创建口也不得由角色自动调用；kai-mode 只推荐命令。
选完把档位写进本机配置并**做一次自证**（到点真的跑一轮、目标真的起来），未实测的 flag 不写进正本。

### 4. worktree 环境自检（三项，缺一报错不静默）

工作树里**没有**主树运行时与依赖目录（检查目录由项目配置实例 `runtime` 段声明，均不入库）。所以每棵工作树开工前先量三项：

| 项 | 标准 | 缺了怎么办 |
|---|---|---|
| 后端解释器 | 主树正本解释器的**绝对路径**（从项目配置实例 `runtime.backend_python` 主树相对路径解析，装机写入 env `KAI_BACKEND_PYTHON`、读时优先 env） | 报「缺解释器」并给绝对路径；**不许退化成随便一个 `python`** |
| node | 主树正本 node 的绝对路径（从项目配置实例 `runtime.node` 主树相对路径解析） | 报「缺 node」并点名路径 |
| 依赖 | 树内用**项目自己的包管理器**离线装（从锁文件判定：`pnpm-lock.yaml`/`package-lock.json`/`yarn.lock`…）后才有前端定向测例环境 | 报「缺依赖」并点名判定结果；**绝不 junction/软链主树 `node_modules` 后跑安装**（会改写主树链接） |

```bash
test -x "$KAI_BACKEND_PYTHON" && "$KAI_BACKEND_PYTHON" -V
node_bin="<主树>/<项目配置实例 runtime.node 主树相对路径>"; test -x "$node_bin" && "$node_bin" -v
test -d <前端目录>/node_modules || echo "缺依赖：树内用项目自己的包管理器离线装"
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

- **缺件登记判据细则唯一正本**：[`skills/principle-report-missing-parts/`](../principle-report-missing-parts/SKILL.md)（何时进场/判据/反例/验证）；本步只管交接——缺件登记进项目配置 `paths.handoff_dir` 当日日报「要你拍」段。
- 装完交一张「安装回执」：装了哪几件技能、定时器 jobId 与周期、三项环境读数、doctor 结果、缺件清单、**宿主落点核对**。
- **回执含「宿主落点核对」格**：核三件事——①角色技能都在宿主技能目录里；②角色命令能读到（或已登记「该宿主无命令口」）；
  ③新上下文口可用（子代理／独立进程／新会话，至少一条），不可用就登记 `no-new-context`。
  核对结果原样写进回执；红项按缺件三格登记，不静默。
- **不把状态写进本地台账**：票状态只看 GitHub；日表只写排班视图。

## 按项目生成（生成式腿 · 装机时可选）

>
> 生成＝从模板抄实例＋逐段问答填实，**占位不落盘**。生成式腿首例＝验收/验证技能骨架
> （模式：探项目 → 出骨架 → 命令项目自己填。）

**两段生成，顺序不倒**：

1. **生成项目配置实例**：从 `templates/kai-mode.project.json`（schema 4 正本模板）抄底，逐段问答填实，
   落 `<项目仓根>/.ai/kai-mode.project.json`（tracked）。**填不实的字段不落盘**——带着占位符的实例不算生成完，
   先报缺件清单等补齐（缺什么/谁需要/怎么补，D4 三格）。
2. **生成项目本地技能骨架**（首例＝验收/验证技能）：
   - **探测（只读）**：在项目仓根列技术栈证据——包管理锁文件、测试配置、门脚本目录——逐项记读数；
     证据列不出就报「技术栈探不出」，不许猜一个栈往下走。
   - **产出**：按骨架模板 [`templates/verification-skill/SKILL.md`](templates/verification-skill/SKILL.md)
     出占位文件，落到实例 `registry.skills.project_skills_dir` 指向的项目技能目录；
     **验证命令一个都不猜**——生成端只探技术栈，命令由项目自己填实。
   - **登记与判据**：骨架填实后由项目在实例 `registry.playbooks[]` 加登记行；生成端不替项目写判据与命令——
     判据正本仍在框架层与项目 ADR，骨架只留「去哪读」的指针。
3. **生成完当场校验**（校验口径）：字段齐、路径字段指向存在的目录、`issue.platform` 在枚举内；
   红项按缺件三格登记，不静默。

- **不真跑**：真机生成属双仓回归那刀的活；本段先落流程与模板。

## schema 2→3→4 实例迁移（迁移腿 · 探到旧实例才走）

> 缺口扫描第 7 项探到项目仓实例 `schema==2` 才走本腿；没有旧实例整段跳过。
> ＋「验证」段（零数据丢失：逐字段 diff 留档）。兼容读口径：schema 2 迁移期可读（doctor 记 warn），
> **两轮双仓回归后即废**——迁移别拖过回归期。

1. **整包备份（迁移前）**：原实例整份拷到本地不入库的位置（文件名带日期），至少保留到迁移验收完；
   备份读不出就停下来报缺件，不许凭记忆重造。
2. **逐字段映射**（去向四类：改写/沿用/删除/新增；全表＝ 字段表）：
   - **改写**：旧 `paths.day_tables` → `paths.day_tables_dir`（补 `day_table_pattern`/`lanes`，问答填实）；
     旧 `paths.daily_report` → `paths.handoff_dir`；旧 `paths.skills` / `paths.loop_protocol` →
     `registry.skills.project_skills_dir` / `loop_dir`；旧 runtime 三门 → `gates` 段
     （活契约只读 `captain_preflight`/`scope_check`/`close_gate` 三键，其余门按项目仓实情自己扩键）；
     旧 runtime 机器绝对路径 → 发现方式字段（机器值走 env `KAI_BACKEND_PYTHON` 与主树相对路径，**不入 tracked 实例**）。
   - **沿用**：`project`/`ship_mode`、`tower_cron.interval_min`、`runtime`（发现方式）。
   - **删除**：`execution.host_tools`（宿主差异迁 `adapters/<宿主>.md`）；以及 schema 4 的零读者键——
     `execution`、`wip`、`limits`、`approval`、`acceptance`、`audit` 六段，`gates` 里除三键外的门名，
     `issue.ready_label`/`milestone_gating`，`tower_cron` 里除 `interval_min` 外的字段，`runtime.deps` 里除
     `check_dir_rel` 外的字段，`runtime.main_tree` 段与顶层 `repo_root`（主树由 git worktree 公共目录反推、
     仓根由调用方传入，两者都不需要实例里那份抄本）。它们不是判据搬家，而是本来就没有读者：在飞名额、失败重试、
     审查独立、风险闸的家＝单票闭环协议与仓库红线，宿主工具契约的家＝`adapters/<宿主>.md`；实例里那份抄本没人读，删掉不丢任何约束。
   - **迁移完成的验收**：实例内没有 host_tools；跑框架仓的 `scripts/check-instance.py --repo <目标仓>` 五条断言全绿
     （键集与模板逐键相等／零占位／零机器路径／落点逐个 stat／日表 pattern 对得上盘上文件）；
     多出来的键是逐条列给用户、他点头才删，不静默丢字段。
   - **新增**（问答填实，占位不落盘）：`registry.playbooks[]`（原登记面收编）、
     `registry.adrs`/`registry.rules`、`issue` 票平台段、`paths` 新增记录面字段（本项目没有的写 null）。
3. **逐字段 diff 留档**：schema 2 的每个字段在 diff 里都有明确去向，diff 写进交接日报（实例 `paths.handoff_dir`）；
   「零数据丢失」的口径就是这张 diff——字段级对不上号就停，不许静默丢字段。
4. **迁后校验**：新实例过校验口径（字段齐、路径在、`issue.platform` 在枚举内、host_tools 已不存在）；
   填不实的字段按缺件三格登记，不落占位。
5. **不真跑**：真机迁移属双仓回归那刀的活；本段先落流程与判据。

## 配置面总表（唯一对照表）

| 可调项 | 正本住在哪 | 改完跑什么 |
|---|---|---|
| 岗位职责与权限 | 岗位技能正文 | `grep -rn "地勤\|塔台" airport/skills/` 逐处认，出现第二本定义即返工 |
| 并发、名额与隔离 | 协议正本 §一 | 技能只指过来；数值只在协议正本出现 |
| 任务表格式与领取方式 | 塔台技能正文 ＋ 项目配置 `paths.day_tables_dir` | 日表行数见协议正本、只由塔台写 |
| 一轮流程（排班→施工→审查→发货） | 塔台与机长技能正文 | 用一张真票走通全链路 |
| 发货与 push 边界 | 塔台技能正文 | 塔台独占 push；机长/子代理不 push |
| 失败恢复与断点 | 塔台技能正文 | 断点三件套（日表＋Issue 评论＋分支提交）齐 |
| 技能注入（正本 → 宿主） | 本技能「2. 装技能到宿主」＋ `magpie-sync.py` | `magpie-sync.py check` 三面全绿 ＋ `skill-attest verify` rc=0 |
| 塔台唤醒定时器周期 | 本技能「3.」＋ 塔台技能 | `list` 回读周期与 `enabled`；人工 `/tower` 也能跑 |
| worktree 环境三项 | 本技能「4.」＋ 项目本机配置（不入库） | 三项各有读数；缺件报错不静默 |
| 剧本登记面 | 配置实例 `registry.playbooks[]`（router.md 退役） | 新增剧本只加登记行，入口与技能不复述 |
| 项目配置实例（落点 / 读取 / 缺件） | 配置实例 schema 正本（实例＝`<项目仓根>/.ai/kai-mode.project.json`） | 读不到实例 → 按 rc≠0 报缺件清单（缺什么/谁需要/怎么补），永不猜路径 |
| 生成式项目本地技能 | 本技能「按项目生成」段 ＋ [`templates/verification-skill/SKILL.md`](templates/verification-skill/SKILL.md) | 骨架落实例 `registry.skills.project_skills_dir` ＋ 项目在 `registry.playbooks[]` 登记一行 |
| schema 2→3→4 迁移 | 本技能「迁移」段的字段映射表 | 逐字段 diff 留档 ＋ host_tools 已不存在 ＋ 新实例过校验口径 |

## 改配置的四条规矩

1. **一次一项**，改完当场跑「改完跑什么」那一列，读数写进对应票面。**没读数＝没改完**。
2. **一个语义只许一个家**：判据细则唯一正本＝[`skills/principle-one-semantics-one-home/`](../principle-one-semantics-one-home/SKILL.md)（何时进场/判据/反例/验证）；本清单只留规矩位，不复述细则。
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
| 五岗位各自怎么干 | [`ground-crew`](../../../airport/skills/ground-crew/SKILL.md)／[`tower`](../../../airport/skills/tower/SKILL.md)／[`pilot`](../../../airport/skills/pilot/SKILL.md)／[`copilot`](../../../airport/skills/copilot/SKILL.md)／[`ace`](../../../airport/skills/ace/SKILL.md) |
| 单票闭环怎么跑 | [`airport/skills/loop/SKILL.md`](../../../airport/skills/loop/SKILL.md) ＋ `references/loop-protocol.md` |
| 本机环境事实（解释器、node、坑） | 本机 `agents.local.md`（不入库，每台一份） |
| 改了技能正本怎么让各家吃到 | 本技能「2. 装技能到宿主」＋ `magpie-sync.py` |
| 给项目出验收/验证技能骨架（生成式腿） | 本技能「按项目生成」段 ＋ [`templates/verification-skill/SKILL.md`](templates/verification-skill/SKILL.md) |
| 项目仓旧实例怎么升 schema 4 | 本技能「schema 2→3→4 实例迁移」段 ＋ 该段字段映射表 |
