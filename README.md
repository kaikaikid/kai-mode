# kai-mode —— 机场体系的技能与通用剧本仓库

> **状态：0.26.1（2026-10-27 loop v5.6／协议 v8.1 契约式委托：方法技能硬映射改「菜单＋判据」由子代理按票情自选，派工卡只给契约五件；轮次可并、环节不可省；吸收项目仓「回归切片定向跑」修订并重落镜像）。此前 0.26.0（2026-10-27 王牌飞行员：用户直连的加急通道成为第五岗位；`ace-queue` 标签是排队正本、`-ace.md` 是王牌自己的车道，同刻 1 张；简单免票热修、复杂自补票，发货仍归塔台；新增 `ace` 1.0.0 与 ADR-0020）。此前 0.25.1（2026-10-26 flight-info 补交接日报索引源（handoff-index）：板接上纸条层，只读文件名＋首行标题、正文不搬；首个非航班形态源，配套 schema/db/collect/render 四处最小改动，测例 29→33）。此前 0.25.0（2026-10-26 机长滚动消费日表＋跃迁窗口内自主裁决：`pass` 进待发货即释放在飞帽、停点收成五类、发货批次归塔台自决；取舍题改派第七人格 `adjudicator` 出 `ruling=`，窗内不向用户提问；doctor 新增 `command-surface`（技能声明的命令须在自己 allowed-tools 里），见 ADR-0017／0018）。此前 0.24.15（2026-10-26 flight-info 人读面结构重排：排班置顶＋卡点＋里程碑＋新鲜度）。此前 0.24.14（2026-10-26 flight-info 一键接上自动更新：钩子＋定时任务＋人工入口）。此前 0.24.13（2026-10-25 flight-info 修两个源缺陷：表格日表解析＋票面可带已关票，测试 29 项绿）。此前 0.24.12（2026-10-25 塔台轻量轮补例外：排班判据/技能版本变更后下一轮强制走 §8 全量排班，避免新规则落不到现有日表；`tower` 1.5.3）。此前 0.24.11（2026-10-25 塔台排班补「先亲和，后均衡」：前置/解挡票与同一交付链优先同车道，均衡只在独立项之间按可动作票数做；`tower` 1.5.2）。此前 0.24.10（2026-10-25 撤销副机长班车例外：定时器仍只唤塔台；副机长默认人工唤醒，`copilot` 2.5.4；见 ADR-0010 D2）。此前 0.24.9（2026-10-25 唤醒围栏曾加一条用户明示例外：用户可明确指令给其它角色开班车——首个例外＝某项目的副机长班车（每时 :30），当日已撤；`copilot` 2.5.3）。此前 0.24.8（2026-10-25 批 5：项目侧的 handoff 迁八槽——190 件分槽分月、README 加槽位表、模板补六字段、三个门脚本同步；旧指针残留 0；见 ADR-0016 D14）。此前 0.24.7（2026-10-25 两仓结构对齐审计：修 kai-handoff 的两处无条件承诺（60-board／六字段 frontmatter）；结论＝handoff 是唯一结构不一致的面，布局待拍；见 ADR-0016 D13）。此前 0.24.6（2026-10-25 批 4 收口：项目侧的审计脚本总表 70.2KB 按域拆三份＋总索引，38 行逐行守恒；该仓 annex 全部回到 64KB 内；见 ADR-0016 D12）。此前 0.24.5（2026-10-25 批 4 收尾：项目侧的 AGENTS 机场体系七条 bullet 压成三行索引，11,639→10,363B、⚠️转✅；顺带补回一条只活在 AGENTS 的车道规则；见 ADR-0016 D11）。此前 0.24.4（2026-10-25 批 4 下半：项目侧 红线收成 `annex-redlines.md` 一个家，五处复述改指针；AGENTS 11,639B／RULES 28,579B；见 ADR-0016 D10）。此前 0.24.3（2026-10-25 批 4 上半：项目侧的 RULES 五块细则迁附录，40,488→29,095B、余量 472B→11,865B，正文逐字校验；见 ADR-0016 D9）。此前 0.24.2（2026-10-25 批 3 补记：ADR-0142 拉继任停用对齐唤醒围栏、handoff 边界落该仓 README、轮巡周期登记待回读；见 ADR-0016 D8）。此前 0.24.1（2026-10-25 收敛批 3 记账：项目侧对齐 L1 的读数（治理红 4→3）；见 ADR-0016 D7）。此前 0.24.0（2026-10-25 收敛批 2·数值与出处各归一个家：在飞名额／日表行数 10 处复述改指针，`canon-dup` 扩到安装面；`sources` 死指针有了检查，首跑量出 4 处指向框架仓文档的已改。见 ADR-0016 批 2。此前 0.23.0（2026-10-25 收敛批 1·把只有正文没有尺的漏洞堵上：塔台令牌落成脚本 `tower-token.py`（三态退出码＋原子写＋缺件三格，正文净减 104B）；新增 `check-instance.py` 校验既有实例（五条断言，键口径 import doctor）；初始化器把路径型缺省逐个 stat，不存在转 null；doctor 第 27 项 `payload-budget` 按层卡字节并打印余量（最紧 set-kai-mode 31.0KB/77%）。见 ADR-0016 批 1。此前 0.22.1（2026-10-25 交接骨架让位项目约定：项目 `handoff/README.md` 无「槽位表」⇒ 初始化器跳过八槽并打印分歧，交接技能同步改为按该仓自己的存放／命名／TTL／门禁落盘；首例实测某仓 pre-commit 硬拦非 `templates` 子目录。此前 0.22.0（2026-10-25 schema 4 复量再收三键：删顶层 `repo_root` 与 `runtime.main_tree`（安装面 53 份里 0 读者），叶子键 44→41、顶层段 11→10；键数改由 doctor `config-instance` 的量法生成，三处手写数与「段 19→12」一并作废（ADR-0015 D5）；`registry.playbooks[]` 行形状写进入口技能；初始化器修两处实测缺陷——打印写死 `docs/adr`、非空 ADR 目录仍写「从 0001 起编号」占位；首例真项目实例落 某项目。此前 0.21.0（2026-10-25 schema 4：配置实例只留有消费者的键，叶子键 88→44、顶层段 17→11；删 `wip`／`limits`／`approval`／`acceptance`／`audit`／`execution` 六段与 `gates`／`issue`／`tower_cron`／`runtime.deps` 的无读者键；`paths.state_dir` 改用框架命名空间 `.git/kai-mode`，`audit_dir` 归 null；见 ADR-0015）。此前 0.20.0（2026-10-25 配置实例零虚构值：模板里没被十一问填到的字段一律 null（12 个门只保留问答过的 1 个）、占位改机械不落盘、宿主选择归一家 `host.adapter`；新增 doctor 第 26 项 `config-instance` 实跑初始化器对账键集／占位／机器路径；见 ADR-0014）。此前 0.19.0（2026-10-24 安装面零开发史：16 个自动安装技能里 70 条框架仓链接、27 处 ADR 编号、73 处 `docs/adr` 路径、18 处维护者门禁命令全部清除，判据改写为技能正文自解释；`payload-refs` 换成禁列实量；见 ADR-0013）。此前 0.18.2（2026-10-24 本仓开发流水出库：`handoff/` 的日期目录与看板工单移出 git 并加忽略，GitHub 上只剩方法论＋安装包；doctor 的 tracked-cache 扩面拦「被跟踪的流水」，当前 0 命中）。此前 0.18.1（2026-10-24 开发数据不入库：`.gitignore` 扩到会话/日志/DB/验证报告/agent 数据，doctor 的 tracked-cache 同步扩面；AGENTS 红线补一条；当前仓库 0 命中）。此前 0.18.0（2026-10-24 Claude Code 适配与全局数据根：新增 `adapters/claude.md`；非项目数据统一到 `KAI_AGENT_DATA_ROOT`，Claude 用 `CLAUDE_CONFIG_DIR`、Codex 用 `CODEX_HOME`、OpenCode 用仅进程生效的 XDG 启动包装；项目数据仍项目自管；见 ADR-0012）。此前 0.17.2（2026-10-24 引用口径收尾：私有仓访问要求写进打包说明，vendor 上游示例链单独说明，`payload-refs` 增框架 URL 路径存在性校验；doctor 25 项）。此前 0.17.1（2026-10-24 清理退役看板目录：删除 `航班信息`／`set-航班信息` 两个旧目录与 doctor 的 `LEGACY_LOCKED` 分支，盘面==注册表恢复严格；doctor 25 项）。此前 0.17.0（2026-10-24 解耦收口：活跃技能的框架文档引用改 GitHub 绝对出处，新增 `payload-refs` 门；ADR-0003 旧口径修正；doctor 25 项；见 ADR-0011）。此前 0.16.0（2026-10-24 三层打包边界：本仓开发件不进宿主库、也不进项目骨架；安装面排除 `tests/` 与缓存，项目骨架只从 `manifests/package-layout.json` 生成，doctor 24 项；见 ADR-0011）。此前 0.15.0（2026-10-24 角色唤醒围栏：角色之间不互相拉起/唤醒；只有人工与定时器（仅塔台）能唤醒角色，kai-mode 只推荐命令、不自动起角色；见 ADR-0010）。此前 0.14.1（2026-10-24 角色/唤醒器分离：塔台是独立岗位，定时器只是唤醒方之一，60 分钟是默认唤醒间隔、不是角色定义）。此前 0.14.0（2026-10-24 评估与安装治理：新增 semantic `harness-audit`、`core/full` 安装档位与安装回执/备份、reviewer `silent-failure` 模式、宿主中立与 frontmatter YAML 门；doctor 19→23，`--with-tests` 纳入 `scripts/tests`；见 ADR-0009）。此前 0.13.0（2026-10-24 人格层收口：六人格改裸名（`kai-` 前缀只用于 `skills/`，防中央库覆盖）、四角色改称「岗位」且人格 `metadata` 只留 `access`、六档词表退役（模型改由初始化第 11 问逐人格问用户，存项目实例 `models.agents.<人格>.model`，null＝宿主默认）、宿主落法从投影脚本改 `adapters/README.md` 方法论、`vendor/` 纳入 git 跟踪并新增 doctor 的 `vendor-sync` 项、入库 `security-audit` 作 reviewer 的 `security` 模式（见 ADR-0008）。此前 0.12.0 子代理人格层按行业规范重建：6 人格 ＋ Agent Skills 对齐的 8 字段机读契约、doctor 新增 `agents-contract` 与 `canon-dup` 两项门禁、清退 `skills/kai-mode/playbooks/` 七件平行正本（判据归位后删除，见 ADR-0007）。此前 0.11.0 看板人读面按 Diagram Design 的 editorial 皮肤重做：四色 tokens、衬线大标、发丝线、暗色整套、赭色只留两处；版式从「五张等宽 KPI 卡」改为页头 ＋ 方向句 ＋ 阶段轨 ＋ 两张表；`view.kpis` 退役，改 `focal_stage`／`font_source`／`metrics`／`labels`／`eyebrow`；字体缺省本地栈零网络。修链外阶段名、行链序、下一步重复三处 bug。此前 0.10.0 看板展示层重做为 `flight-info`（SQLite ＋ 模块化解耦 ＋ 钩子只打标记）；0.9.1 确立看板三层；0.9.0 砍掉非 kai-mode 内容、塔台轮巡改 **1 小时**、通用方法技能改 `vendor/skills/` 原样拉取、`handoff/` 增 `50-comms`、新装项目走 `scripts/init-project.py` 十问）。** 技能与协议已对齐本仓现行机场体系
> （[0003：四角色＋1 小时唤醒塔台](docs/adr/0003-airport-rebuild-four-roles.md)；[0020：王牌飞行员加急车道](docs/adr/0020-ace-pilot-expedited-lane.md)）；**本仓是宿主装机正本**（`magpie-sync apply --root <本仓>`，
> 8 个宿主按注册表 `install:auto` 装齐，当前 17 条），项目仓那份技能副本只作镜像。
> 旧五角色（Tower/Ground/Coordinator/Group-A/B）、租约、班次、handoff 按铃那套已随机场体系重做退役（本仓 [0003](docs/adr/0003-airport-rebuild-four-roles.md)）<!-- canon:allow-retired -->
> （git 历史可捞）。

## 这是什么

kai-mode 是「一句话需求 → 票 → 排班 → 施工 → 审查 → 发货 → 关票」的闭环框架。

**仓定位（2026-10-22 用户定口径）**：本仓**独立于任何项目仓** —— 不属任何项目仓，**不受项目仓的票、日表、审查与门禁约束**；它只放**跨项目通用**的部分（别的仓能直接拿去用的那种）。

- 技能清单：**以仓根 [`registry.json`](registry.json) 为准**（单一事实源；本文件不再手写名单）。两类：
  - **框架技能**（`kind: framework`）：框架本身的一部分，各项目都该有，默认 `install: auto` 进中央库；
  - **个人技能**（`kind: personal`）：只给自己用的，默认 `install: manual`，**不进中央库**。
- 协议正本：`loops/loop-protocol.md`（v5）
- 通用方法：按上游名引用 `tdd`／`code-review`／`diagnosing-bugs` 等（`vendor/skills/` 原样副本，本仓不 fork）
- 可执行契约：`task` / `acceptance` / `event` schema
- 宿主适配器：Qoder（60 分钟唤醒定时器＋按需子会话）、opencode/codex 备胎
- 项目配置模板：`templates/kai-mode.project.json`

项目自己的 ADR、票、日报、门禁脚本与项目专用剧本留在项目仓。

## 角色（单责）

| 角色 | 口令 | 只负责 | 绝不做 |
|---|---|---|---|
| kai-mode 入口 | `/kai-mode` | 一句话需求 → 判断 → 拷问 → 定稿 → 拍板 → 路由 | 执行 |
| set-kai-mode 装配 | `/set-kai-mode` | 安装、探测、装定时器、doctor、缺件登记 | 日常施工 |
| 地勤 | `/地勤` | 对话、规划、开票（六件套＋`ready-for-agent`）、收想法 | 写码、push、派施工 |
| 塔台 | `/塔台` | 独立岗位；默认每 60 分钟由定时器唤醒，也可人工唤醒；kai-mode 只推荐命令；先发货、后补排班（日表行数见协议正本，放本轮最后） | 写码、替审查下结论 |
| 机长 / 副机长 | `/机长` `/副机长` | goal 模式滚动跑完自己那张日表（在飞帽只算未完工票，`pass` 进待发货即释放）；每票 1 施工＋1 审查（新上下文），跃迁窗口内取舍派 `adjudicator` 出 `ruling=` | 写码、push、合并 |
| 王牌飞行员 | `/王牌飞行员` | 用户直连的加急通道；读 `ace-queue` 标签票，在自己那张 `-ace.md` 滚动消费（同刻 1 张）；简单免票热修、复杂自补票 | 写 `-main`/`-deputy` 日表、push、合并、关票 |

**权限硬线（[0003](docs/adr/0003-airport-rebuild-four-roles.md) ＋ [0020](docs/adr/0020-ace-pilot-expedited-lane.md)）**：塔台**独占** push 与关票；机长/副机长/王牌只管理不写码（王牌热修是受控例外）、不 push；地勤只开票；记录面三分——主副日表只由塔台写、王牌日表只由王牌写、状态只写 Issue 评论、代码只进分支。

**唤醒围栏（[0010](docs/adr/0010-role-wake-fence.md)）**：角色之间不互相拉起/唤醒；只有人工与定时器（仅塔台）能唤醒角色，kai-mode 只推荐命令、不自动起角色。子代理是票内委派，不受此围栏影响。

## 闭环

```text
用户一句话 → /kai-mode（拷问→定稿→拍一次板）
                    │
                    ▼
              地勤（开票：里程碑＋ready-for-agent＋AC＋禁区）
                    │  三选一：等塔台（不打标）│ 进王牌队列/现在拉起（打 ace-queue）
                    ├──────────────────────────────────┐
                    ▼                                  ▼
              塔台（先发货：合并/push/关票，           王牌飞行员（写自己的 -ace.md，
                    最后补排班写两张日表）              同刻 1 张；简单可免票热修）
                    │                                  │
                    ▼                                  │
        机长 ──┬── 机长 ──┐   ← 主/副各按协议名额在飞；子代理按需
        副机长 ┘          │                          │
       （每票：施工子代理[独立 worktree] → 审查子代理[新上下文]）
                    │  verdict=pass ＋逐条 AC 证据 → 「待发货」
                    ▼
              塔台（再发货：批内合并 → 收尾门一次 → push 一次 → 关票）
                    │
                    └── 库存下降 → 下一轮补排班
```

记录面三分：**日表**（主副塔台写／王牌写自己的，排班视图）＋ **Issue 正文与评论**（唯一事实源）＋ **分支与提交**（代码与回执）。断点三件套 = 这三样，继任者按它续跑。
热修免票但仍留四件：分支提交、新上下文判词、`-ace.md` 的 `H-` 行、当日日报——**少的是票，不是记录**。

## 交接与断点（省叙述，不省证据）

- 票进入日表即完成领取；状态只由机长写 Issue 评论（开工/施工完成/审查完成/待发货/卡点）。
- 施工回执字段固定为 `ticket/role/verdict/files/commits/checks/summary/evidence/risks/next`，行数上限与字段语义见 [loop-protocol §五](loops/loop-protocol.md)；禁止贴 diff 全文与原始日志。
- 塔台发货**只认审查子代理的判词**（`verdict=pass` 且逐条 AC 有证据），不认机长口头总结。

## 可靠性（[loop-protocol §七](loops/loop-protocol.md)）

- 单票失败 **1 次重试**；再失败 → 卡点停票；同错连发触发熔断。
- 上限数值只住 `loops/loop-protocol.md`（票级协议的家），实例不再抄一份；到限写 `blocked`/`failed` 留读数，不许「再试一次看看」。
- 红线（花钱/对外真发布/不可逆改历史/删未提交内容）→ **只停那张票**，立即报人。

## 目录

```text
skills/           技能目录：一个技能一目录，必含 SKILL.md（清单见 registry.json）
skills/kai-mode/  入口与路由：正本地图（判据不住这里，只给路径）
agents/           子代理人格层：人格文件（裸名，清单见 `agents/README.md` §4）＋ dispatch.md（派发策略）
skills/flight-info/   看板展示层：SKILL.md ＋ flightinfo/（db·stage·sources·collect·render）＋ schema/*.sql ＋ scripts/（建板/刷新/钩子）
registry.json     技能注册表：技能清单的单一事实源（装机清单从它派生）
scripts/          仓级工具：doctor.py（校验入口，一条命令验全仓）
loops/            loop-protocol.md（v5 单票闭环正本）
schemas/          task / acceptance / event
adapters/         README（宿主落法总则：探测/六家对照/降级/自证）＋ qoder、opencode、codex（起岗位）
templates/        kai-mode.project.json（schema 3：宿主选择器/日表/轮巡/名额/限额/审批/审计）
templates/skill/  技能骨架模板（SKILL.md）：加新技能从这里复制
docs/             ADR（0001–0009）、技能契约、外部素材对账
docs/skill-layout.md  技能目录契约（目录 / frontmatter / 注册表字段 / 加技能三步 / 读契约）
CHANGELOG.md      版本变更记录
.gitattributes    行尾口径（仓内存 LF；.bat/.cmd 落 CRLF，防 cmd 崩）
```

## 接入一个新项目

1. 项目根写 `.ai/kai-mode.project.json`（从 `templates/` 复制），填运行时**发现方式**（主树反推、env、相对路径）与门禁命令；机器绝对路径不入库。
2. 把本仓 `skills/` 与 `loops/loop-protocol.md` 落到项目仓 `.ai/skills/` 与 `loops/`（或由 `set-kai-mode` 按宿主装配）。
3. `/set-kai-mode` 探测宿主能力（定时口 / 会话创建口 / shell 启动器），按四档可选装配 60 分钟唤醒定时器（只唤醒塔台，不是塔台本体）；装机按 `core`／`full` 档位（`manifests/install-profiles.json`），缺件如实登记。
4. 项目 ADR 记角色与权限裁决（先例：本仓 [0003](docs/adr/0003-airport-rebuild-four-roles.md)）；开票走地勤六件套；用一张真票走通「排班→施工→审查→发货」全链路做自证。
5. 项目专用路径、票号、job id 只进项目配置与本机文件，不进本仓技能正文。


## 加一个技能（三步）

1. **复制骨架**：把 [`templates/skill/SKILL.md`](templates/skill/SKILL.md) 复制到 `skills/<名>/SKILL.md`，把 `<占位>` 全替换掉（目录名＝frontmatter 的 `name`）。
2. **注册表加一行**：在仓根 [`registry.json`](registry.json) 里加一条（字段口径见 [`docs/skill-layout.md`](docs/skill-layout.md)）。
3. **doctor 过**：跑 `python scripts/doctor.py`，全绿才算加完 —— doctor 会抓「目录在、没登记」这类漏项。

契约细节（目录必含什么、frontmatter 八字段与顺序、注册表字段表、读契约）见 [`docs/skill-layout.md`](docs/skill-layout.md)。

## 验证

一条命令验全仓：

```bash
python scripts/doctor.py --with-tests
```

覆盖：注册表 schema / 字段 / 枚举、每个技能的目录与 `SKILL.md`、frontmatter 八字段与顺序、三处 name 一致、盘上有技能目录但没登记、`SKILL.md` 相对链接断链与宿主中立、机器绝对路径入正文、仓内行尾口径、`VERSION` 与本文件版本串一致、解耦门、交接文档分类、Agent Skills 1.2 对齐、人格层契约、判据归属、`vendor/` 跟踪与漂移、中央库副本与本仓是否逐字相同＋库记住的装机来源是不是本仓（`install-sync` 项；中央库定位不到时跳过），以及各技能自己的 pytest。

单独跑某个技能的测试：见该技能 `SKILL.md` 的「验证命令」段（如 `python -m pytest skills/flight-info/tests/ -q`）。

## 当前不做

- 不改项目仓的日表、Issue、门禁脚本——那些归项目仓与各角色。
- 不把项目专用路径、票号、job id 写进技能正文。
- 项目专用件（ADR、票、日报、门禁脚本、项目专用剧本）不进本仓。
- 个人技能默认 `install: manual`，不进中央库。
- 装机正本＝本仓（`registry.json` 的 `install:auto` 条目）；项目仓 `.ai/skills/` 只是镜像，不是装机源。中央库记住装机来源（`<库根>/.kai-mode-source.json`），从库里那份脚本跑，正本根也回到本仓。

## 判据正本

- 机场体系唯一现行裁决：本仓 [`docs/adr/0003-airport-rebuild-four-roles.md`](docs/adr/0003-airport-rebuild-four-roles.md)
- 单句入口与拍板：本仓 [`docs/adr/0002-single-entry-and-dual-lane.md`](docs/adr/0002-single-entry-and-dual-lane.md)
- 评估与安装治理：本仓 [`docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md`](docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md)
- 角色唤醒围栏：本仓 [`docs/adr/0010-role-wake-fence.md`](docs/adr/0010-role-wake-fence.md)
- 三层打包边界：本仓 [`manifests/package-layout.json`](manifests/package-layout.json)（说明 [`docs/package-layout.md`](docs/package-layout.md)，裁决 [`0011`](docs/adr/0011-package-layout-three-layers.md)）
- 全局 agent 数据根：本机 [`docs/agent-data-layout.md`](docs/agent-data-layout.md)（裁决 [`0012`](docs/adr/0012-global-agent-data-root.md)）
- 单票闭环协议：本仓 `loops/loop-protocol.md`（v5）
- **技能清单与装机清单**：仓根 [`registry.json`](registry.json)（装机清单＝其中 `install: auto` 的条目）
- **技能目录契约**：[`docs/skill-layout.md`](docs/skill-layout.md)（目录结构 / frontmatter 八字段与顺序 / 注册表字段 / 读契约）
- 版本与设计沿革：`CHANGELOG.md`（逐版变更）＋ `docs/adr/`（裁决）
