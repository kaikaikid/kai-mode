# 0016 收敛设计与反膨胀预算：机制住框架、事实住项目、判据要么可跑

## Status

proposed —— 2026-10-25 用户令「先梳理一遍收敛设计以免膨胀，先看 kai-mode 的设计存不存在缺陷，把漏洞堵完再覆盖
kai-vass 的开发框架设计，以后他的开发框架得跟随 kai-mode 一步步规范化重构」。本文只做设计与取证，不改机制；
批 1 起按 D4 的顺序执行，每批另有可测出口。

## Context

首个真项目（`Kai-vass-Control`，下称 KVC）装完当天量到两类问题：**框架把自己的约定无条件铺进已有约定的仓**
（交接八槽撞该仓「handoff 禁子目录」的 pre-commit 硬拦，已撤回并由 0.22.1 修根因），
以及**框架把自己的缺省当项目事实写进用户实例**（三个路径型值盘上不存在）。
再往深量，框架自身有六处设计缺陷，全部有读数：

| # | 缺陷 | 实测证据（2026-10-25） |
|---|---|---|
| F1 | 塔台令牌是**纯正文约定、零实现件**，并发互斥靠 agent 自觉 | `skills/tower/SKILL.md` 内「令牌」16 处；全仓 `*.py`/`*.ps1` 里 `tower-token` 命中 **0**；KVC 今日塔台日报每轮手写「收工删令牌释放」＝agent 自己建删 JSON；该仓历史出现过并行塔台（#1864 两条逐字节相同回执） |
| F2 | **没有校验既有实例的口**；今天的验收脚本住在 agent 数据根（scratch，没人跑） | doctor 的 `config-instance` 项只实跑 `init-project` 生成**临时**实例对账；`scripts/` 下无 `check-instance`；项目仓那份实例无任何机器校验 |
| F3 | 模板的**框架缺省被当项目事实**写进用户实例（0014 D1 的漏网） | KVC 实例三值盘上不存在：`registry.skills.loop_dir=.ai/skills/loop`、`runtime.backend_python.fallback.rel`、`runtime.node.rel`（`runtimes/` 整目录 MISSING）；`registry.rules.dir=.ai/rules` 命中属巧合，同样没被问答过 |
| F4 | 框架**没有字节尺**，反膨胀原则只活在正文 | doctor 仅有 ≤500 **行**的闸，且只覆盖 `SKILL.md` 与 `agents/*.md`；`loops/loop-protocol.md`（15,634B）、`adapters/*.md`、`AGENTS.md`、`docs/*.md` 无任何体量闸；最大件 `set-kai-mode/SKILL.md` 31,707B／378 行＝用掉 76% 行预算 |
| F5 | **数值型判据多处复述**，`canon-dup` 自认不管 | 安装面 48 份里：红线 20 个文件、`verdict=pass` 6、日表 5–10 行 4、在飞名额 3、独占 push 3、不写产品代码 4、令牌 2；`docs/canon.json` 自注「四岗位技能对协议数值的复述**暂未纳入** forbidden」 |
| F6 | 交接槽位无条件铺（0.22.1 已修），**同族风险仍在日表面** | `paths.day_table_pattern`／`lanes` 是框架常量写死，无人校验盘上真有当天匹配文件 |
| F7 | `sources[].resource` 的「只许随装件」规矩**无机械检查** | `docs/skill-layout.md` §「sources 只许指随技能安装的件」；doctor 里 `resource` 零命中 ⇒ 写了死指针也全绿 |

另核一条**不是缺陷**：定时器只有 qoder 一家给装法（claude／codex／opencode 各自明写「没有定时口」），
但 `set-kai-mode` 缺口扫描第 3 项已能按「今日日报有真实 `cron-tower-*` 轮次 或 宿主 `list` 回读 `enabled=true`」判定，
降级腿（人工唤醒）是设计内、已如实登记 ⇒ 不动。

KVC 侧读数（收敛对象，65 件治理文档 610,455B）：15 个语义里 **11 个有第二处复述**（四角色 3 处：RULES v5 §1＋AGENTS 表＋ADR-0137 D1；
worktree 隔离 4 处；想法池 #792 3 处）；`RULES.md` 41,042B 超该仓自己的 40KB 上限 82B（红）、`annex-audit-scripts.md` 71,856B 超 64KB；
13 个门，钩子走 `core.hooksPath=.githooks`（`pre-commit`＋`pre-push` 都在，实测）；
ADR-0131 D5 单令牌与 ADR-0132 D4 两层令牌**已退役**、ADR-0137 明文「不恢复跑道/令牌/租约/信箱/交班条/签派单/哨兵」，
而现实每轮在用令牌 ⇒ 该仓 ADR 与现实互斥（F1 落地后按新事实改写那一行）。

## Decision

### D1 两层正本地图（收敛的判据）

```
┌─ L1 框架仓 kai-mode ＝ 机制与判据的家 ───────────────────────────────┐
│ AGENTS.md（红线）│ loops/loop-protocol.md（票级协议）│ agents/（人格）  │
│ skills/（四岗位＋入口＋安装器）│ adapters/（宿主差异）│ templates/（实例模板）│
│ scripts/doctor.py（唯一门）│ manifests/（打包边界）│ docs/adr/（决策）  │
└───────────────────────────┬──────────────────────────────────────────┘
        装（set-kai-mode）＋ 运行时读（技能按名取实例字段）
                            ▼
┌─ L2 项目仓（KVC 等）＝ 项目事实的家 ─────────────────────────────────┐
│ .ai/kai-mode.project.json（唯一项目差异事实源，41 键）                │
│ AGENTS.md（薄入口）│ .ai/rules/（项目特有判据：设计系统、审计脚本清单）│
│ scripts/（项目自己的门：scope-check／close-gate／captain-preflight…）│
│ docs/artifacts/adrs/（项目 ADR 编号体系）│ handoff/（纸条层，H1 平铺）│
└──────────────────────────────────────────────────────────────────────┘
  禁止：L2 复述 L1 的数值判据 ｜ L1 写死 L2 的事实（本日两例都已抓到）
```

归属判定一句话：**换一个项目还成立的 ⇒ L1；只有这个项目成立的 ⇒ L2。**
路径、门名与子命令、票号、体量上限值、ADR 编号、设计系统治理、审计脚本清单 ⇒ L2；
角色职责与权限、名额、闭环七步、发货边界、令牌机制、交接槽位语义、实例 schema、宿主适配 ⇒ L1。

### D2 三条收敛规则（同时是反膨胀规则）

- **R1 一个语义一个家，跨仓也算。** L2 只许留「指针 ＋ 项目事实」，不许复述 L1 的判据数值；
  L1 不许出现任何项目事实（0014 已立，本轮补 F3 的机械执行）。
- **R2 判据要么可跑、要么不算判据。** 数值／串／路径／时序型判据必须有脚本或门在读它；
  只有正文的判据要么降级为「建议」并明写，要么补尺。F1（令牌 16 处正文 0 脚本）与
  `registry.playbooks[]`（0 代码消费者，0.22.0 已给行形状找到按名读者）是本条的两个反例。
- **R3 字节预算是一等判据。** 框架安装面与协议正本各有字节上限、doctor 卡；项目仓的上限可更严不可更松；
  新增正文必须说明预算从哪挪来，净增要指名。

### D3 六处缺陷的修法（含净字节方向）

| # | 修法 | 净字节 |
|---|---|---|
| F1 | 新增 `skills/tower/scripts/tower-token.py`：`acquire`／`heartbeat`／`release`／`who`，临时文件＋`os.replace` 原子写，过期阈值＝`tower_cron.interval_min × 2 + 5`，落点读实例 `paths.state_dir`，读不到实例报缺件三格不猜路径；`tower/SKILL.md` 的 16 处正文压成「三行命令 ＋ 一句判据指针」 | **净减** |
| F2 | 新增 `scripts/check-instance.py --repo <路径>`：四条断言（叶子键集与模板逐键相等／零占位／零机器绝对路径／登记落点逐个 stat，门值按「脚本 ＋ 子命令」解析后 stat 脚本）；`set-kai-mode` 的缺口扫描与 3→4 迁移验收改调它，不再各自手写 | 新脚本，正文只加一行指针 |
| F3 | `init-project` 落盘前对**所有路径型缺省**逐个 stat：不存在 ⇒ 改 `null` 并打印（与 `gates` 同口径）；`registry.rules.dir`／`registry.skills.*` 从「模板缺省」改成「探测到才写」 | ±0 |
| F4 | doctor 新增 `payload-budget`：按层给字节上限（安装面 `SKILL.md`／协议正本／适配说明／`AGENTS.md`），**绿也打印每层余量与最大件**（半盲的 ✅ 不算尺） | 一项检查 |
| F5 | 可机检的数值／串（在飞名额、日表行数区间、`verdict=pass`、令牌心跳公式）收进 `docs/canon.json` 单点表，`canon-dup` 扩面到安装面复述；复述处改指针 | **净减** |
| F6 | 并入 F2：`check-instance` 用 `day_table_pattern`＋`lanes` 去盘上找当天文件，找不到就报分歧（不猜、不静默） | ±0 |

### D4 批次与出口（每批一个可测出口，做完才进下一批）

| 批 | 做什么 | 出口（可测） | 代价 |
|---|---|---|---|
| 1 | 框架堵漏 F1／F2／F3／F4（＋F6 并入） | doctor 项数 26→28 全绿；`check-instance --repo <KVC>` 绿；KVC 实例三个假值转 `null`；`tower/SKILL.md` 字节数**下降** | 一夜内；不碰 canon，回归面小 |
| 2 | 框架收复述 F5（数值／串进 `canon.json` 单点表）＋F7（`sources[].resource` 死指针检查） | `canon-dup` 报「数值复述点 0」；`sources` 死指针 0；被碰技能版本升＋中央库刷新＋`payload-refs` 复跑绿 | 一夜；碰约 10 支安装面正文，有回归面 |
| 3 | KVC 对齐 L1（需用户点头：该仓 `rules/` 明写「仅限用户明确指令或已批准批次」） | 四角色／worktree／#792 三处复述改成「L1 指针 ＋ L2 事实」；ADR-0137 令牌那一行按 F1 的新事实改写；该仓 `governance-health-check` 红 4→0 | 每批只碰一个干净件、留脏不提交（该仓有 peer 塔台每小时跑、主树 174 枚脏件） |
| 4 | KVC 门与体量收敛 | 13 个门对框架 `gates` 三键的归属表（承接／留项目／退役）；`RULES.md` 与 `annex-audit-scripts.md` 降回上限内 | 另开；体量治理要迁附录，逐件列清单先给用户过 |

### D5 批 1 执行记录（2026-10-25，0.23.0）

| # | 落成什么 | 出口读数 |
|---|---|---|
| F1 | `skills/tower/scripts/tower-token.py`：`acquire`／`heartbeat`／`release`／`who`；原子写；阈值 `interval_min×2+5`；缺件三格；退出码 0／1／2 三态。`tower/SKILL.md` §0 压成四行命令＋指针 | 端到端实测：FREE→ACQUIRED→HELD(rc1)→NOT_HOLDER(rc1)→TAKEOVER(过期牌)→RELEASED 全对；`tower/SKILL.md` 15,283→**15,179B**（净减 104B） |
| F2 | `scripts/check-instance.py --repo`：五条断言，键口径 `import doctor` | KVC 实跑：绿 19／红 0／提示 0；全新空仓：绿 6／红 0／提示 12（按需生成的落点只提示） |
| F3 | 初始化器 `resolve_guesses()`：路径型缺省逐个 stat，不存在 ⇒ null；问答答案型保留 | 空仓实测 5 个猜测转 null、4 个答案保留；KVC 那三处假值（`loop_dir`、`runtime.*.rel`×2）已转 null，复跑 check-instance 红 0 |
| F4 | doctor 第 27 项 `payload-budget`：五层字节上限，绿也打印每层最大件与余量 | 27 项全绿；最紧 `set-kai-mode/SKILL.md` 31.0KB（77%）；合计 151KB；变异测试（上限压到 1KB）当场转红 |
| F6 | 并入 check-instance 第 ⑤ 条：`day_table_pattern`＋`lanes` 去盘上找文件 | KVC：匹配 10 个、今天 2 张；空仓：目录未建＝提示不判红 |
| 口径 | `AGENTS.md`／`docs/package-layout.md` 的 26 项改 27；迁移验收改调 `check-instance` | doctor 自报 27 项 |

### D6 批 2 执行记录（2026-10-25，0.24.0）

| # | 落成什么 | 出口读数 |
|---|---|---|
| F5 | `canon.json` 增 `pilot-wip`（`(最多|各|只能)\s*2\s*张|2\s*张在飞|…`）与 `day-table-rows`（`5\s*[–—-~～]\s*10\s*(行|条)`），home 都是 `loops/loop-protocol.md`；10 处复述改指针 | 复述点 0；`canon-dup` 6 判据键单点住家；首跑即咬住 tower 排班步里漏改的「5–10 行照排」 |
| F7 | `broken-link` 扩面校验 `sources[].resource`：路径型必须是随装件，花括号展开，含空白视为自然语言，manual 豁免 | 首跑量到 4 处死指针（2 支技能指向框架仓 `docs/`）；改完后 20 条随装件路径全在 |
| 边界 | `verdict=pass` **不**进单点表：它是审查与适配之间的字面接口，不是可调数值；登记进 canon 会逼适配层写指针，反而降低可操作性 | 记在 `canon.json` 的 `_note` 里 |

### D7 批 3 执行记录（2026-10-25，KVC 侧对齐 L1，未提交）

用户批准后改 `Kai-vass-Control` 的 4 件活口治理文档（3 条历史件早已脏，未碰）：

| 件 | 改动 | 读数 |
|---|---|---|
| `AGENTS.md` | 机场体系加「角色正本＝装到宿主的四角色技能＋协议」指针行；角色表 4 列压 3 列（权限边界归 L1）；四处数字（名额／日表行数／轮巡周期）改指针 | 11,527 → 11,652B（上限 12,288） |
| `.ai/rules/RULES.md` v5 §1 | 6 行角色表＋3 条 bullet 压成「正本指针＋入口／本仓差异／保留面／宿主中立」 | 41,042 → 40,337B（上限 40,960，由红转绿） |
| `.ai/rules/RULES.md` §2/§3/§4/§11/附录 | 日表行数 3 处、在飞名额 1 处、物理隔离 1 处改指针（物理隔离细则归 `annex-worktree.md`） | 同上 |
| `.ai/router.md` | 塔台行「每 30 分钟」＋「5–10 行」改指针 | 9,658B |
| `ADR-0137` | 保留原文「不恢复…令牌…」，其下加 2026-10-25 用户批准修订注（退役的是票级派单租约；岗位互斥锁不在其列） | ADR 索引门复跑 0 缺项／0 幽灵 |

该仓自己的门复跑：`governance-health` 红 4→**3**（剩余 3 条是 10-22／10-23 三张历史日表超限，属存量证据，不在本批改）；`check-adr-index` 干净；
活口文档里「5–10 行」「30 分钟」「各 2 张」复述 **0 处**（协议镜像里的那两处是 L1 正本，设计内）。

**未提交**：该仓 push 门 A2 按提交信息里的票号找租约，无票号的独立治理提交会被判越界 ⇒ 留脏等用户给票号或自行提交。

**同批发现、未动的三处冲突**（登记不猜）：① 轮巡周期三个数——文档原写 30（已清）/ 实例 60 / 日报实测 63–79 分钟，
实例值需在 KVC 会话里读一次真实 cron 才能定；② `ADR-0142` 写「塔台拉继任机长」，与 L1 唤醒围栏（角色互不拉起）
及该仓塔台自己日报里的「交人工唤醒继任机长」相反；③ `handoff/` 旧平铺 191 件与新八槽（已撤）的边界仍只在 handoff/README。

### D8 批 3 补记：三处冲突的处置（2026-10-25，用户令「按建议直接改」）

| 冲突 | 处置 | 读数 / 证据 |
|---|---|---|
| 轮巡周期三个数 | **登记，不改值**：本工作区 `qoder_cron list` 为空（任务绑在 KVC 工作区）、本机存储里扫不到 schedule 档 ⇒ 真值读不到。间接吻合：若按「上一轮结束后顺延」，60 分钟＋每轮 3–19 分钟正好解释日报实测的 63–79 分钟。实例保持 `interval_min: 60`（方向安全：TTL 125 分钟只会更早接管死牌，不会更晚） | 待 KVC 会话回读一次 `qoder_cron list` 即可定值 |
| ADR-0142 与唤醒围栏相反 | D3「塔台拉继任」**停用**、D2 第 4 项作废（原文保留，加用户批准修订注）；`RULES` §1 与 `AGENTS.md` 造班 bullet 同步改成「角色之间不互相拉起/唤醒，塔台只播报＋写日表，等人工唤醒」 | 依据：该仓塔台自 10-24 起实际就这么跑（日报原文「交人工唤醒继任机长，不自己开新会话」） |
| handoff 边界 | 写进该仓 `handoff/README.md`：框架八槽**不采用**（框架 0.22.1 起技能读到「README 无槽位表」按项目约定落盘）；归档只有 `handoff-cleanup.py` 一条腿（按**文件名日期**超 15 天 → `docs/archive/handoffs/<YYYY-MM>/`），不许再发明第二套；存量到期 **37 件**待里程碑收尾批量搬 | dry-run 只读实测 37 件；日常轮次不搬 |

复量：`AGENTS.md` 11,778B（上限 12,288）／`RULES.md` 40,488B（上限 40,960，余 472B）／`handoff/README.md` 12,355B；
该仓 `governance-health` 红 3（全是历史日表）、`check-adr-index` 干净、命名门禁子目录违规 0。

### D9 批 4 上半：KVC 的 RULES 体量治理（2026-10-25，用户令「优先把附录迁出压缩」）

该仓 `RULES.md` 在批 3 后只剩 472B 余量（40,488/40,960）。按它自己的处置顺序「先迁 → 再拆 → 最后才议抬限」，
把五块「查表才看」的正文迁附录、RULES 只留「标题＋指针」（**节号保留作锚**，外部 `§N` 引用不断），
正文**一字未改**（逐块从备份切出、断言在目标附录里逐字存在，5/5 通过）：

| 原位置 | 体量 | 新家 |
|---|---|---|
| `### backend 结构落点表` | 4,519B | 新 `.ai/rules/annex-backend-structure.md` |
| `### 9. 验收取数与两型死判据` | 1,596B | `annex-rules-details.md` 追加节 |
| `### 11. 规则↔执行者对照` | 2,312B | `annex-rules-details.md` 追加节 |
| `### 10. D10 中立门禁` | 1,903B | 新 `.ai/rules/annex-host-neutral.md` |
| `### 治理产物落点` | 1,744B | `annex-artifact-locations.md` 置顶节（优先于该文件旧行） |

读数：`RULES.md` 40,488 → **29,095B**（腾出 11,393B，距 40KB 上限余 **11,865B**）；该仓 `governance-health`
`RULES.md` 由 ⚠️ 转 ✅，warn 7→6；红仍 3（全是历史日表）。四份附录都远低于 64KB 上限（最大 `annex-rules-details` 15.9KB）。
剩余体量欠账：`annex-audit-scripts.md` 70.2KB 超 64KB（warn），下一步按域拆分。

### D10 批 4 下半：KVC 的红线收成一个家（2026-10-25，用户令「把 AGENTS 的红线描述迁进 annex」）

查的时候发现红线在 KVC 有 **5 处**（AGENTS 三处、RULES §6 定义 + §4 处置 + Git 约定第 4 条），
其中 RULES §6 是真正的定义正本、AGENTS 三处是复述。做法不是「把 AGENTS 那份搬进附录」再留两个家，而是：
**新建 `annex-redlines.md` 当唯一家**（定义／已放行·仍先问的划分／处置／Git 面／与审批边界的关系），
RULES 与 AGENTS 全部改成指针；AGENTS 保留一行「五件清单」不让硬停被藏进附录。

| 位置 | 处理 |
|---|---|
| 新 `.ai/rules/annex-redlines.md` | 2,204B：定义（含「对外真发布不含 push 自有远端」）／处置（只停该票、其余继续、留痕、出选择题）／Git 面（`--no-verify`／force-push／改写已推历史／`git add -A`／删分支／拆树走脚本）／与 §6 审批边界的关系 |
| AGENTS 机场体系「红线只停那张票」 | **删除**（内容进 annex §二），同一文件不再放第二个指针 |
| AGENTS Git「红线先问」 | 收成一行：五件清单 + 「踩线只停该票、其余继续」+ 唯一指针 |
| AGENTS 审批边界那段 | 括号里那串红线清单改成指针 |
| RULES §6 红线 bullet | 定义整段 → 指针 |
| RULES §4 红线只停票 | 处置整段 → 指针 |
| RULES Git 约定第 4 条 | 清单（多出 `--no-verify`／改写已推历史／拆树走脚本三条）→ 指针，三条补进 annex §三 |

读数：`AGENTS.md` 11,778 → **11,639B**（只省 139B——五件清单必须留在入口，省不动；下次腾地方要动机场体系那七条 bullet）；
`RULES.md` 29,095 → **28,579B**；红线完整复述点 **5 → 0**（剩下 7 处提及全是一句话政策或指针）。

## Consequences

- 批 1 之后，令牌从「正文约定」变成「有脚本、可回读、可审计」的岗位互斥锁：这也让 KVC 的 ADR-0137
  那行「不恢复令牌」可以按事实改写——被退役的是**票级派单租约**，塔台岗位锁不是同一物（票的领取仍只靠日表）。
- 批 1／2 都是**净减或中性**的字节方向：反膨胀不靠自觉，靠 F4 的尺与 F5 的单点表。
- 代价：`check-instance` 与 `payload-budget` 会让「模板改一处、忘了同步」当场红；这是要的。
- 不做的事：不给 claude／codex／opencode 造定时器（无定时口是宿主事实，降级腿已登记）；
  不把 KVC 的 13 个门搬进框架（门是 L2 事实，框架只读 `gates` 三键）；不替 KVC 重写它的 ADR 编号体系。
