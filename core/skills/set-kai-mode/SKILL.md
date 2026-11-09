---
name: set-kai-mode
status: active
approved_by: human:kaikaikid
approved: 2026-10-21
sources:
  - resource: "../gold/SKILL.md"
    note: "对外唯一入口；本技能负责把它装到宿主并设为默认"
  - resource: "../../../engine/skills/fleet/SKILL.md"
    note: "施工与发货内核；装主 AI 人格时一并装它"
  - resource: "scripts/magpie-sync.py"
    note: "技能正本 → 中央库 → 各家宿主链接的回写口"
  - resource: "scripts/uninstall-v1.py"
    note: "卸载 V1 的机械腿：探测、退役、复核、回执都住脚本"
description: >
  kai-mode 的初始化安装入口（不是日常施工）：先看缺什么、列出推荐清单跟用户确认，再只装缺的。
  覆盖：装酒馆冒险团与执行内核、把康娜设为默认入口、worktree 环境自检、项目配置实例生成/校验/迁移、
  开票归属守卫、缺件如实登记。触发：新 agent 接手装配、换宿主、修技能落点、迁旧配置实例、
  问「这套东西都住在哪」。不做日常施工。
version: 7.0.0
updated: 2026-11-08
allowed-tools: Bash(*) Read Write Edit
compatibility: Requires python3, git
---

# Set Kai Mode —— 安装酒馆冒险团与执行内核

> `/gold` 是**用**这套框架的入口；`/set-kai-mode` 是**装**这套框架的入口。
> 本技能只做安装与配置，**不做日常施工**：不写产品代码、不开 run、不发货、不关票。
> 本文件只回答三件事：**东西在哪、怎么装、装完跑什么自证**；细节查 `references/`。

## 什么时候进这里

- 新 agent / 新机器第一次接手：从零装到能跑。
- 换宿主或换执行体。
- 技能改了却没在别家生效（正本与库不一致）。
- 项目配置实例还是 schema 4 或更旧——走迁移腿。
- 撞见「同一条判据两处说法不一样」——配置面漂移，回到这里对表。
- **已装的是旧版、要升到新版** ⇒ 走 `upgrade-kai-mode`。本技能只补缺、不覆盖已就位的东西。

## 一套体系，没有并行档位

旧体系（V1：地勤、塔台、机长、副机长、二副、王牌、日表、车道、60 分钟唤醒定时器）已整体下线。 <!-- canon:allow-retired -->
现在只装一套：

| 层 | 组件 | 干什么 |
|---|---|---|
| 入口 | `gold`（康娜的方法正文） | 主 AI 人格唯一对话面；判断、开票、开 run 清场、发货、回报 |
| 规划 | `staff` | 需求大、方向未定时由康娜调用；出规划表与拆票草案 |
| 执行 | `engine`（`fleet` 命令） | 一张票一个 run；主会话规划验收，宿主原生子代理施工 |
| 方法 | 宿主中央库原版 | TDD、审查、诊断、拆票、术语、写文档；按名调用，不随装 |
| 记录 | GitHub Issue ＋ `.coding/runs/` | 票面与 run 状态 |
| 展示 | `fleet status --html` | 进度看板（可选） |

## 铁律：先看缺什么，再装

进本技能第一件事是跑**第 0 步缺口扫描**（全只读），把现状列成**缺口清单**——
已就位的明确标「跳过，不重复装」，缺的才列成「推荐处理项」。
**先把清单念给用户听，用户点头才执行对应步骤**；不闷头按顺序全跑一遍。

## 装到别的项目：先问清楚

装进一个新项目不是拷文件，是**把项目差异问清楚**：十二问 ＋ 双仓五题。前十一问各带默认（回车即默认），
**双仓五题与第 12 问皮肤回车一律落「待定」**——那几项是团长的取舍，没拍板不许替选默认值；
第 12 问的提问提示里推荐 **guild**（酒馆康娜），推荐只进提示、不作默认值（见同表第 12 问）。
一条命令跑完：

```bash
python scripts/init-project.py --repo <目标仓>                    # 逐题问，每题带默认，回车即默认
python scripts/init-project.py --repo <目标仓> --yes              # 全默认（先看 dry-run）
python scripts/init-project.py --repo <目标仓> --answers a.json   # 机器填
```

> 本命令在**框架仓根**执行；技能装到项目仓后，用 `<框架仓根>/scripts/init-project.py`，
> **不是**项目仓的 `scripts/`。维护者的门禁脚本同理只住框架仓。

题目清单、落到哪个键、脚本顺手铺哪些组件、覆盖口径、缺件拒绝规则见
[`references/setup-qa.md`](references/setup-qa.md)。人格层角色件要**宿主（第 8 问）与皮肤（第 12 问）
都拍了板**才产，缺一个就点名缺件、不替你选；皮肤记在哪、为什么不进配置实例，同一份文件说了算。
两条腿的取法与验收在 `references/default-entry.md`「人格层激活」。

## 九步（每步一个可判的验收）

| # | 装什么 | 验收（能判才算完） |
|---|---|---|
| 0 | **缺口扫描（只读）** | 出一张缺口清单：每项标「已就位／跳过」或「需处理（原因）」 |
| 1 | 注入方法论与技能（仓库内正本） | 技能文件在位；清单以 `.claude-plugin/marketplace.json` 现场派生为准 |
| 2 | 装技能到宿主（`gold` ＋ `staff` ＋ `fleet` ＋ `pk`） | 宿主技能列表里能看见，内容与正本同哈希 |
| 3 | **把康娜设为默认入口** | 项目或全局级有默认入口段；无斜杠命令时按康娜执行；项目级优先 |
| 4 | worktree 环境自检（解释器／node／依赖） | 三项都有明确读数 |
| 5 | doctor | 门禁全绿或如实点红 |
| 6 | 开票归属守卫（宿主钩子） | 无 `--repo` 的 `gh issue create` 被拒；带 `--repo` 放行 |
| 7 | 缺件登记与安装回执 | 缺件按三格登记，回执含宿主落点核对 |
| 8 | 子代理模板（可选，用户点名才装） | 目标目录 7 个 `.md` 在位；新会话里同名内置被覆盖 |

### 0. 缺口扫描（只读）

十项探法、各自「已就位」与「需处理」的判据见
[`references/gap-scan.md`](references/gap-scan.md)。
产出：把清单念给用户；已就位逐项说「跳过」；需处理项附原因。**能只读判定的，绝不做写操作。**

### 1. 注入方法论与技能

正本全部住在仓库里（中立层），任何宿主一进仓库即生效：

- 入口 `core/skills/gold/SKILL.md`；规划 `core/skills/staff/SKILL.md`
- 执行内核 `engine/skills/fleet/SKILL.md`（命令 `engine/bin/fleet`，安装见 `engine/README.md`）
- 想法池 `intake/skills/kai-boom-idea-log/SKILL.md`；看板（可选）`board/skills/flight-info/SKILL.md`
- 方法不随装，按名用宿主中央库原版

项目仓落点从配置实例读 `registry.skills.project_skills_dir`；剧本登记行收进 `registry.playbooks[]`。
新增剧本只加登记行，不在入口里复制判据。

### 2. 装技能到宿主

仓库里的 SKILL.md 是**正本**；宿主真正加载的往往是另一份拷贝，**改了正本不回写，只有当下这一家生效**。

```bash
S=core/skills/set-kai-mode/scripts/magpie-sync.py
python $S --selftest                          # 先证这把尺会响
python $S check                               # 只读漂移表
python $S apply --dry-run --profile core      # 看将写哪些字节
python $S apply --profile core                # 正本 → 库 → 各家链接；写前自动备份
```

档位（`core` / `full`）、安装回执、来源标签、加技能三步、库位反查、三条硬规矩见
[`references/host-install.md`](references/host-install.md)。

### 3. 把康娜设为默认入口

两个落点二选一：项目级（默认）／全局级；**优先级项目级 > 全局级**，两处都写了按项目那份。
正文段、全局装的兜底句、生成物文件的禁忌、验收方式见
[`references/default-entry.md`](references/default-entry.md)。

**同一步还要激活人格层**（默认入口只带流程；名字与脾气另住 `roles/`，指令文件里不许抄人格文字）：
按两条腿取一次——项目内有 bootstrap 产出的 `_primary` 角色件就读它，否则现读渲染器 `prompt --primary`；
皮肤与宿主没记录就问团长一次，不替她选默认；两条腿都不可达登记 `persona-source-unreachable`。
腿名、canon／skin 指纹回执与验收三条同在 `references/default-entry.md`「人格层激活」节。

### 4. worktree 环境自检

工作树里**没有**主树运行时与依赖目录（检查目录由配置实例 `runtime` 段声明，均不入库）。
解释器、node、依赖三项各有读数，缺了就报绝对路径，不退化成随便一个 `python`。
命令与判据见 [`references/env-and-gates.md`](references/env-and-gates.md)。

### 5. doctor

读数**只能出自门**；红就报红，不静默吞错。长期红的门只走基线文件，不在本技能里改判据。

### 6. 开票归属守卫

> 治的病：在项目仓里跑 `gh` 会按 cwd 落仓，随手 `gh issue create` 就把框架问题开到项目仓。

先探宿主 `settings.json` 的 `hooks.PreToolUse`；已挂就只跑 `--self-test`，未挂则在用户点头后安装。
宿主没有钩子口 ⇒ 三格登记 `no-hook-surface`，不许谎报已拦截。
钩子形状与验收见 [`references/env-and-gates.md`](references/env-and-gates.md)。

### 7. 缺件登记与交接

缺件判据见 `../principles/SKILL.md`（§5）；本步管交接。
装完交一张「安装回执」：装了哪几件技能、默认入口落在哪个文件、三项环境读数、doctor 结果、缺件清单、宿主落点核对。
**宿主落点核对**：① `gold` 与 `fleet` 在宿主技能目录；② 新上下文口可用（子代理／独立进程／新会话至少一条），
不可用就登记 `no-new-context`；③ 旧 V1 链接已摘或已列清单。
不把状态写进本地台账：票状态只看 Issue；run 状态只看 `.coding/runs/`。

### 8. 子代理模板（可选）

模板正本在本技能 `agents/`（四自建 ＋ 三内置覆盖），只写模型、权限、轮次上限；判据不住这里。
安装命令、落点规则、新会话才生效的验收见
[`references/host-install.md`](references/host-install.md)「子代理模板」。

## 卸载 V1（下线腿）

探 → 退 → 核 → 回执四步，脚本做哪些、哪些必须人拍、验收三格见
[`references/uninstall-v1.md`](references/uninstall-v1.md)。

## 配置实例（schema 5）

schema 5 删掉了 V1 的任务表、工作树槽位、定时器与三键门禁；保留**只有活读者**的键。
键表、已删除项、迁移规矩见 [`references/config-schema.md`](references/config-schema.md)。

## 改配置的四条规矩

1. **一次一项**，改完当场跑验收，读数写进对应票面。**没读数＝没改完**。
2. **一个语义只许一个家**：判据细则见 `../principles/SKILL.md`（§4）。
3. **机制类改动先设计后落地**：先出图与代价进 ADR；用户拍板后才动执行面。
4. **宿主中立**：依赖某家专有能力必须同时有 ①能力探测 ②降级腿 ③缺件如实登记。

## 红线与冻结面

- 红线先问：**花钱**／**对外真发布**／**不可回滚或改写历史**的 git 动作／**删任何未提交内容**。
- 不碰项目仓 `.githooks/**`；确需改先问。钩子只当发令员：只写标记、fail-open，不派工。
- 付费档宿主：起它必须显式授权；没授权就只用免费档或人工。
- 写中央库前必须整包备份 ＋ 哈希基线；库内凭据只报字段名与位置，严禁抄值。
- 本技能不施工、不发货、不关票、不写产品代码。

## 与相邻文件的关系

| 你要的 | 去哪 |
|---|---|
| 用户入口、清场、发货 | `../gold/SKILL.md` |
| 参谋部（规划与拷问方法） | `../staff/SKILL.md` |
| 施工与发货命令 | `../../../engine/skills/fleet/SKILL.md` |
| 方法库 | 宿主中央库原版（按名调用，本仓不存副本） |
| 想法池 | `../../../intake/skills/kai-boom-idea-log/SKILL.md` |
| 看板（可选） | `../../../board/skills/flight-info/SKILL.md` |
| 改了技能正本怎么让各家吃到 | 本技能「2. 装技能到宿主」 |
