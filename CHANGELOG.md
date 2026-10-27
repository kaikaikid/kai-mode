# CHANGELOG

本仓变更记录；按版本倒序，每条一行。版本号正本＝仓根 [`VERSION`](VERSION)。

## 0.28.0 — 2026-10-27

- **单票闭环脚本化（P0）**：`loop` 技能新增三枚脚本，把机械判断从自然语言推理下沉成小 JSON——
  `ticket.py`（窄读票面／开工三件／判词形状与分母／回执字段／续跑指针四件）、
  `protocol.py`（按节取协议，整份 30.8KB → 单节 1.6–4.7KB）、
  `worktree.py`（车道槽／分支／HEAD／脏否只读体检）。
  `pilot` 改为先跑脚本再读正文；`loop` 6.1.0、`pilot` 3.1.0、`airport` 3.1.0。
  读数：pilot＋loop 17.6KB；单节协议 1.6–4.7KB。脚本测试 6 条并入 `skill-tests`，doctor 28 项全绿。

## 0.27.0 — 2026-10-27

- **插件化剧本（KWP 形态）**：仓根改为市场清单 `.claude-plugin/marketplace.json`，五个剧本各是一个插件目录
  （`airport`／`core`／`board`／`intake`／`ops`）；每个插件带两份 `plugin.json`（Claude Code／Qoder）、
  `PLAYBOOK.md`、`CONNECTORS.md`、`commands/` 与 `skills/`。**剧本＝插件，角色＝命令，步骤＝技能**。
  - **人格层退役**：`agents/` 七个人格文件、`agents-contract` 门、实例 `models.agents` 与初始化第 11 问全部移除；
    派活规则迁入协议同目录 `dispatch.md`，裁决形状迁入 `adjudication.md`；审查独立性由「另一段新上下文」保证。
  - **注册表退役**：`registry.json` 删除；安装器从市场清单＋插件目录现场派生技能清单（内存兼容形状，不落第二份文件）。
  - **判据正本随技能安装**：`loops/loop-protocol.md` 迁入 `airport/skills/loop/references/loop-protocol.md`，
    顶层 `loops/` 退役；项目仓若保留镜像，按新路径复制并核对哈希。
  - **协议 v9**：工作树改「一车道一棵」（`lane-main`／`lane-deputy`／`lane-ace`＋登记式推送工位，一票一树废止）；
    王牌车道写清「无对照道」与热修提交标识 `H-<日期>-<序号>`；门的自身成本（超时／全历史普查）不再冒充被审对象的红；
    塔台起手禁止每轮跑全历史普查，推送工位用完即拆。
  - **新增 `ops` 剧本**：`incident-response`（分级／时间线／复盘→补票）与 `runbook`（可重复运维步骤、失败分支、回滚）。
    `tech-debt` 与 `testing-strategy` 不吸收（已有 `harness-audit`／`tdd`／审查门），理由见 ADR-0021。
  - **分发体检**：新增 `scripts/plugin-check.py`（市场↔插件↔版本↔摘要锁↔档位）与 `.github/workflows/plugin-check.yml`；
    `manifests/plugins.lock.json` 钉版本与内容摘要，漂移即红，`--bump` 刷新。
  - **宿主**：Claude Code 与 Qoder 落到「装什么／放哪／叫什么都」；Qoder 技能落 `.qoder/skills/<名>/SKILL.md`，
    插件清单用 `.qoder-plugin/plugin.json`，旧 `qoder_cron` 标注为运行时观测、非公开 API；Codex／OpenCode 留骨架。
  - **顺带清既有两红**：安装面 ADR 引用（`payload-refs`）与项目硬路径（`decoupling-gate`）。
  - 项目仓 `Kai-vass-Control` **零字节改动**；镜像同步与项目侧门禁适配留作下一棒。

## 0.26.1 — 2026-10-27

- **loop v5.6.0 ＋ 协议 v8.1「契约式委托」**：方法技能从「环节硬绑定」（施工＝`tdd`｜审查＝`code-review`｜
  失败＝`diagnosing-bugs`）改「**菜单＋选用判据**」，由子代理按票情自选、派活方不代定——派工卡只给
  契约五件（票号／AC／允许修改面／验证命令／回执格式）。非代码／纯配置／纯文案票不再被迫写测试。
  **环节顺序不可反、轮次可并**：轻量票可把相邻环节并进同一轮，环节不可省、并步留痕。
  - `skills/loop/SKILL.md`：「派活用哪个方法技能」改「派活：契约写死，方法自选」；`dependencies` reasons
    改按选用判据（diagnosing-bugs 标条件触发，平时不预载）。
  - `loops/loop-protocol.md`：§二.3／§三 表／§三 末段同步改自选口径；§四 吸收项目仓「回归切片只跑本批
    touched 脚本（定向，不全库）」修订（原两处各改一份＝镜像漂移，本版收敛回一个家）。
  - **镜像同步**：项目仓镜像按协议自述同步口重落（`cp` ＋ `sha1sum` 一致）。

## 0.26.0 — 2026-10-26

- **loop v7 ＋ 0019「停与等分家」**：治「表里还有活，班却反复停下来」。四处根因当场量出——
  ① 项目仓协议停在 **v5**、框架已是 v6（0017/0018 那些「不停车」判据一条没生效），本仓 `scripts/loop-gate.py:7`
  还写着「v5 唯一正本」；② §八／`agents/dispatch.md` §10 那句「不许以等后台 agent 结束回合」与宿主执行模型
  （后台子代理只能靠通知唤醒）**正面冲突**，等子代理这一步在规范上无解；③ 等待时只列了三样本地活，做完就没事干；
  ④ 停的那一刻不要求留「下一步是什么」。
  - 协议：抬头加**正本身份**条（框架＝唯一正本，项目仓＝同哈希副本，禁止两处各改）；§七 加「停与等分家」＋
    **续跑指针**（≤8 行四件：等什么／下一步第一个动作／在飞面／接手能直接跑的验证命令；预算到顶同样适用）；
    §八 把「轮间干本地活」换成**等待梯六档**（第一档＝名额未满就补位），并把冲突那句改写成**两态收尾**
    （A 态还在干／B 态挂等牌收场），旧「委派完成契约」改为只约束**子代理回执**。
  - 技能：`pilot`／`copilot` 2.7.0——「跃迁窗口」更名「**取舍裁决（默认路径）**」（0019 D5 撤销 0018 D1 的
    会话绑定开窗；口令只剩「跑到日表清空、不逐票请示」），等待节换成梯＋两态＋指针；copilot 不再复读清单，
    只留车道差异「各报各的」。`agents/dispatch.md` §10 同步改写（矛盾正本的源头在这儿）。
  - **缺件登记**：两仓协议**哈希 parity 机检未实装**（该住在 `loop-gate` 或框架 `doctor`），0019 D4。

## 0.25.1 — 2026-10-26

- `flight-info`：补**交接日报索引**源（`handoff-index`）——板子接上纸条层，看得到最近
  `handoff/<槽>/<YYYY-MM>/*.md` 在哪、标题是什么，点开是相对链接直接跳原文件（`file://` 下可跳）。
  只读文件名＋首行标题，**不搬正文**（正文正本在文件里，板只做入口）。
  - 第一个**非航班形态**的源：产出 `handoffs` 键而非 `flights`／`schedules`。
  - 配套四处最小改动：`schema/002-handoff.sql` 建 `handoff_doc` 表、`db.replace_handoffs`／
    `fetch_handoffs`、`collect.run_sources` 汇总并落库（`handoffs` 计入源行数与源健康）、
    `render._handoff_section` 出「交接日报索引」段。
  - `SKILL.md` 的模块地图补上这条口径：航班形态源仍是一文件＋REGISTRY 一行、其他不动；
    非航班形态源要显式按键名汇总（`run_sources` 不自动透传自定义键）。
  - 测例 29→33（缺目录降级、排序与 limit、槽位白名单跳过 `templates/`、落库回读＋链接渲染）。

## 0.25.0 — 2026-10-26

- **机长滚动消费日表，发货与机长节奏解耦**（[0017](docs/adr/0017-captain-drains-day-table.md)，用户令 #6）：
  `pass` 写进待发货当场释放在飞名额（帽只算未完工票）；帽是并发上限不是批次，一张完工即补下一张，
  滚到日表跑空才停；停点收成闭集五类（红线／同错早停／修 1 次仍 fail／BLOCKED 与恢复对不上／表跑空），
  「批收尾」「等塔台收货」不再是停的理由。换手点下沉到单票收尾自检三件齐，塔台只在发现机长停摆时提换手；
  发货批次归塔台按触面与门成本自决。`pilot`／`copilot` 2.6.0、`loop` 5.4.0、`tower` 1.6.0、`kai-mode` 2.6.0。
- **跃迁窗口内自主裁决**（[0018](docs/adr/0018-in-run-adjudication.md)，同一张票）：开窗＝用户对这条会话说
  「跃迁」或明示跑到清空；窗内取舍题派新人格 `adjudicator`（只读、新上下文、`ruling=a|b|defer` ＋ 争点／判据／
  所选／撤销路径与改判条件）照判词执行，**不为取舍向用户提问**；红线仍停该票等人，两份正本互斥与人眼观感题
  转上报不转她；同争点不重派、两次互否停裁。协议 §十一 由四档变五档。
- **第七人格 `agents/adjudicator.md`**：`agents/README.md` §0／§2／§4 与 `dispatch.md` §3 同批登记，
  模板 `models.agents.adjudicator.model=null`（不发明模型 slug，强档由项目实例填）。
- **doctor 新增第 28 项 `command-surface`**：技能正文 ```bash 块声明要跑的命令必须出现在该技能
  `allowed-tools` 里（`Bash(*)`／裸 `Bash` 算全覆盖；先抹引号内文本，`--jq '{...}'` 不算命令）；
  绿话打印覆盖面（17 份／23 条）。首跑量出 5 个技能缺登记：`pilot`／`copilot` 补 `Bash(gh:*) Bash(python:*)`
  （正文自己声明要跑窄读与 preflight，旧白名单只有 git——到会硬拦的宿主上就是一步步弹审批）、
  `loop`／`tower`／`kai-handoff` 补 `Bash(python:*)`、`kai-boom-idea-log` 补 `Bash(git:*)`。测例 +3（红／绿／通配与串接）。
- 项数不再手抄：`AGENTS.md` 与 `docs/package-layout.md` 的「27 项」改成看 doctor 汇总行（手写数会随门漂移）。
- **新上下文审查判 `fail`（3/6）后补修**（同一张票 #6）：① 人格**计数**在三处写死成旧数（`skills/kai-mode`、
  `README.md`、`set-kai-mode` 第 11 问），一律改指针，`agents-contract` 加一条计数守卫（`× 7`、prose
  「一个人格从不排班」不误炸，测例 +1）；② 三条新语义（停点闭集／跃迁开窗判据／裁决四件形状）登记进
  `docs/canon.json`——`loops/` 与 `agents/` 是 repo_only、装到宿主读不到，所以技能留一份可执行副本是**声明过**的，
  第三份才红；`ruling=` 的三值与四件收回人格自己的输出契约，技能只用 marker；③ `command-surface` 修假绿假红：
  带空格的管道分段（`git log | jq` 现在会量到 `jq`）、heredoc 正文跳过、`$( )` 与反引号剥离、行内注释截断、
  大写首词归一、`Bash(git:add:*)` 这类细粒度前缀算覆盖（测例 +1，全套 51 项绿）；④ 两份 ADR 的「全绿」验证行
  补上并行在制件的归属口径。

## 0.24.15 — 2026-10-26

- `flight-info`：人读面（`index.html`）结构重排，板子不再偏薄。
  - **排班表置顶**：原本在航班表之后，现移到最前（航班组当天排了哪些活，第一眼就看到）。
  - 顶部加**「今日收尾 N 张」**读数＋**「卡点 / 挡住」区**（阶段=hold 的票，标掌机与卡点原因，最多 8 张）。
  - 航班表之后加**「里程碑进度」**（按里程碑分组，画 已关/总 进度条；单里程碑则不显示，避免噪声）。
  - 页脚源健康区加**快照时刻**（数据新鲜度一眼可见）；每源仍带 ok/fail 圆点。
  - 全部从既有 `payload` 的 `flights`/`schedules`（含 `milestone`/`stage`/`closed_at`）现算，
    **不扩大数据模型**；手机窄屏下置顶双栏自动叠成单栏。

## 0.24.14 — 2026-10-26

- `flight-info`：加**一键接上自动更新**（`scripts/install_auto.py`，Windows）。
  把三件事按依赖收齐：① git 钩子（写进仓的*有效* `core.hooksPath`，不只是 `.git/hooks`；
  钩子只打脏标记，不同步刷、不阻塞 git）② 定时任务（`schtasks`，当前用户上下文、仅登录时、
  隐藏窗口，**无 token＝不存密码**；消费脏标记、周期调 `refresh_if_dirty`）③ 人工入口
  `refresh.vbs`（复制到板目录，`start "" /min` 隐藏窗口，无黑窗强制重建）。
  - 页面右上角加「刷新」按钮（`location.reload()` 重读磁盘最新页；真正的重生成走钩子/定时/vbs）。
  - `schtasks /Create` 被本机安全策略拒（`Access is denied`）时**降级成告警、不阻断安装**——
    钩子与手动刷新仍可用，周期刷新在能建任务的环境补。
  - 设计一个事实：静态 `file://` 页面不能从按钮直接执行本地 vbs（浏览器会下载而非运行），
    所以按钮只 reload；立刻重建靠双击 `refresh.vbs`。
  - 记一笔：`magpie/data/library` 下的技能副本是单向同步落点，直接改会被宿主复位；
    正本永远是真源仓。

## 0.24.13 — 2026-10-25

- `flight-info`：修两个让板子说假话的源缺陷（真实项目装板时实测）：
  - `tasks-table` **只认列表行**：项目侧五列表格日表被读成「0 张票」还报 `ok`——排班看得见、票全丢，
    失败不点名。现按表头列名（中英两套，精确优先、其次包含）解析表格行；列表行照旧支持，两者可混用，
    表格行另带 `milestone`。
  - `github-issues` 加 `include_closed` / `closed_limit`：只拉 open 票时，残留的 `exec/<票号>-*` 分支
    压不下去，板子把陈旧分支报成「在飞」；顺带拉已关票后按 `state_closed` 归到已收尾。
  - 测试 +5（表格解析、老写法不退化、`queries_for` 三种取值），全套 29 项绿。
  - 记一笔：`magpie/data/library` 下的技能副本是**单向同步的落点**，直接改会被宿主复位；
    正本永远是真源仓 `skills/flight-info`。

## 0.24.12 — 2026-10-25

- `tower` 1.5.3：补轻量轮例外——**排班判据/技能版本变更后，下一轮强制走 §8 全量排班**，不得以
  「无实质变化」走轻量轮；否则新分配规则不会落到现有日表（2026-10-25 实测：规则改完后塔台连走两轮
  轻量轮，日表仍是旧的主 5／副 1）。

## 0.24.11 — 2026-10-25

- `tower` 1.5.2 排班判据补「**先亲和，后均衡**」（用户 2026-10-25 口径：有些任务必须在同一机长下完成才是最佳，
  不能平均分配）：前置/解挡票、同一交付链/ADR/spec/验收上下文、同一文件域优先同车道；
  均衡只在独立项之间按**可动作票数**（不是日表行数；占行/等回执/hold 不算）做；不为凑行数拆散亲和组。
  跨表未在飞的解挡票可从原表挪到被挡车道（只改日表，不关票、不写状态）。

## 0.24.10 — 2026-10-25

- **撤销 0.24.9 的副机长班车例外**（用户 2026-10-25 复述「副机长默认不应该走定时模式」）：
  ADR-0010 D2 恢复「定时器只唤醒塔台」；AGENTS 同步；`copilot` 2.5.4 触发恢复「人工唤醒」。
  项目侧的副机长定时任务已移除；塔台班车保留（标准唤醒方）。

## 0.24.9 — 2026-10-25

- **唤醒围栏放开一条用户明示的口子**（[ADR-0010 D2](docs/adr/0010-role-wake-fence.md) 演变注）：
  定时器默认仍只唤醒塔台；其它角色要开班车须**用户明确指令**并在项目侧登记。首个例外＝某项目的
  副机长班车（每时 :30，与塔台 :00 错开），用于塔台停摆期间继续推进副表。角色之间仍互不唤醒。
- `copilot` 2.5.3：描述里的触发补「用户明确授权的定时班车」；中央库已回写（`install-receipt` 绿）。

## 0.24.8 — 2026-10-25

- **批 5·项目侧的 handoff 迁八槽**（[ADR-0016 D14](docs/adr/0016-convergence-design-and-byte-budget.md)）：
  190 件平铺件按词元分槽、按日期分月移入 `10-session`／`20-plan`／`30-research`／`40-review`；README 与 templates 留根；
  新增 `## 槽位表`（框架技能据此走「有槽位表」路径）、模板补六字段 frontmatter、H1/H5/§7 与三个门脚本同步改
  （naming 三查、cleanup 递归归档 90-archive、governance-health 纸条层递归）。全仓旧指针残留 0。
  迁移中一次自纠：README 被误搬入槽并带偏 6 处指针，当场归位回正。无框架侧代码改动。

## 0.24.7 — 2026-10-25

- **结构对齐审计（两仓逐面对照）＋修 L1 两处失配**（[ADR-0016 D13](docs/adr/0016-convergence-design-and-byte-budget.md)）：
  `kai-handoff` 不再无条件承诺 60-board（项目没有就走它的 Issue／lane 面）、不再无条件要求 frontmatter 六字段
  （无槽位表的仓按其模板写）；版本 0.3.3→0.3.4。审计结论：handoff 是唯一结构不一致的面（布局／格式／命名），
  其余已对齐或属 L1/L2 分工。布局是否统一待用户拍。

## 0.24.6 — 2026-10-25

- **批 4 收口·项目侧审计脚本总表按域拆三份**（[ADR-0016 D12](docs/adr/0016-convergence-design-and-byte-budget.md)）：
  `annex-audit-scripts.md` 71,856B → governance 40.6KB／backend 22.3KB／frontend 9.8KB ＋ 3.9KB 总索引；
  38 行逐行集合相等、无重复，索引每条都能落到分册。该仓 `governance-health` warn 5→4，`annex-*` 全部回到 64KB 内。
  无框架侧代码改动。

## 0.24.5 — 2026-10-25

- **批 4 收尾·AGENTS 机场体系七条 bullet → 三行索引**（[ADR-0016 D11](docs/adr/0016-convergence-design-and-byte-budget.md)）：
  2,143B → 846B，`AGENTS.md` 11,639 → **10,363B**（距 12KB 上限余 1,925B，⚠️ 转 ✅）。
  删前逐条做「事实→家」对照，查出「两条车道各自复查、互不替对方判空」原本只活在 AGENTS、别处无家，
  已先补进 `RULES.md` §3「车道互不代判」。无框架侧代码改动。

## 0.24.4 — 2026-10-25

- **批 4 下半·项目侧的红线收成一个家**（[ADR-0016 D10](docs/adr/0016-convergence-design-and-byte-budget.md)）：新建 `annex-redlines.md`
  （定义／处置／Git 面／与审批边界关系），RULES §6／§4／Git 约定第 4 条与 AGENTS 三处复述全部改指针；
  完整复述点 5→0。`AGENTS.md` 11,778→11,639B（五件清单留在入口，只能省 139B）、`RULES.md` 29,095→28,579B。无框架侧代码改动。

## 0.24.3 — 2026-10-25

- **批 4 上半·项目侧的 RULES 体量治理**（[ADR-0016 D9](docs/adr/0016-convergence-design-and-byte-budget.md)）：五块「查表才看」的正文
  （backend 落点表／§9 验收取数／§10 中立门禁／§11 规则↔执行者／治理产物落点，合计 12,074B）迁附录，
  RULES 只留「标题＋指针」、节号保留作锚；正文一字未改（5/5 逐字校验）。
  `RULES.md` 40,488 → **29,095B**（余量 472B → 11,865B），该仓 `governance-health` 对 RULES 由 ⚠️ 转 ✅。无框架侧代码改动。

## 0.24.2 — 2026-10-25

- **批 3 补记三处冲突的处置**（[ADR-0016 D8](docs/adr/0016-convergence-design-and-byte-budget.md)）：ADR-0142 的「塔台拉继任」停用
  （对齐唤醒围栏，原文加修订注）；handoff 边界写进该仓 README（框架八槽不采用、归档只走清理脚本、存量 37 件待批量搬）；
  轮巡周期读不到真值 ⇒ 登记不改（实例 60 与实测 63–79 分钟间接吻合）。无框架侧代码改动。

## 0.24.1 — 2026-10-25

- **收敛批 3 记账**（[ADR-0016 D7](docs/adr/0016-convergence-design-and-byte-budget.md)）：项目侧 4 件活口治理文档对齐 L1
  （角色表压成正本指针、10 处数字改指针、ADR-0137 令牌条加用户批准修订注）；该仓 `governance-health` 红 4→3
  （剩余 3 条是历史日表超限，存量证据不动）。本版只记读数与三处未动冲突，无框架侧代码改动。

## 0.24.0 — 2026-10-25

收敛设计（[ADR-0016](docs/adr/0016-convergence-design-and-byte-budget.md)）批 2：把「数值判据多处复述」与「sources 死指针」两条收掉。

- **F5 两处可调数值收成单点**（家＝`loops/loop-protocol.md`）：在飞名额（§一）与日表行数区间（§零）的 **10 处复述**
  全部改成指针（kai-mode 路由表、pilot 描述与 CONTINUE 行、tower 描述/来源注/排班步、ceremony 原则、set-kai-mode 迁移表、README 两处）。
  `docs/canon.json` 增 `pilot-wip`／`day-table-rows` 两条判据键，`canon-dup` 扩面到安装面技能；
  **接口字面（如 `verdict=pass`）不登记**——它是审查与适配之间的字面契约，不是可调数值（ADR-0016 F5 的边界）。
  首跑当场咬住我漏改的半句（`tower/SKILL.md` 排班步里的「5–10 行照排」）。
- **F7 `sources[].resource` 有了机械检查**：`broken-link` 扩面——路径型 resource 必须指向随装件
  （本技能自己的文件或 `skills/<名>/…`，支持花括号展开）；含空白的条目视为自然语言出处不判；`install: manual` 豁免。
  首跑量到 **4 处指向框架仓文档的死指针**（`kai-boom-idea-log`、`principle-one-semantics-one-home` ×1、
  `kai-handoff`、`flight-info`），已改成非路径表述；`kai-handoff` 两条指向同一文件的资源合并成一条。
  现读数：17 份 SKILL.md 相对链接全在、**sources 随装件路径 20 条全在**。

## 0.23.0 — 2026-10-25

收敛设计（[ADR-0016](docs/adr/0016-convergence-design-and-byte-budget.md)）批 1：把四处「只有正文、没有尺」的漏洞堵上。

- **F1 塔台令牌有了实现件**：新增 `skills/tower/scripts/tower-token.py`（`acquire`／`heartbeat`／`release`／`who`）——
  落点读实例 `paths.state_dir`、原子写、过期阈值＝`tower_cron.interval_min × 2 + 5`、缺件三格不猜路径；
  退出码三态：0 成／1 退位（他人在飞或不是持牌人）／2 缺件。`tower/SKILL.md` 的令牌正文压成四行命令＋指针，
  文件字节 **−104B**（机制住脚本，正文只留怎么用）。此前 16 处正文、0 个脚本，靠 agent 手工建删 JSON。
- **F2 既有实例有了校验口**：新增 `scripts/check-instance.py --repo <项目仓>`，五条断言（叶子键集与模板逐键相等、
  零占位、零机器绝对路径、登记落点逐个 stat（门值按「脚本＋子命令」解析）、日表 pattern 对得上盘上文件）；
  键口径**直接 import doctor**，不写第二把尺。刚装完还没建的落点只提示不判红。
- **F3 框架猜测不再冒充项目事实**：初始化器落盘前把路径型缺省逐个 stat，不存在 ⇒ `null` 并打印
  （`registry.rules.dir`／`registry.skills.*`／`runtime.*.rel`／`runtime.deps.check_dir_rel`）；
  问答答案型落点（日表／交接／想法／state_dir）保留原值、只提示按需生成。
- **F4 反膨胀有了尺**：doctor 新增第 27 项 `payload-budget`——按层卡字节（`AGENTS.md` ≤12KB／协议正本 ≤40KB／
  适配说明 ≤16KB／安装面 `SKILL.md` ≤40KB／技能内其它 md ≤64KB，与项目仓体量上限同尺），**绿也打印每层最大件与余量**。
  当前：`set-kai-mode/SKILL.md` 31.0KB 最紧（77%），合计 151KB。
- 迁移验收改调 `check-instance`（set-kai-mode 4.8.1→4.9.0），不再让人手工对账键集。

## 0.22.1 — 2026-10-25

- **交接骨架不再无条件铺八槽**：项目 `handoff/README.md` 已在、且没有「槽位表」⇒ 初始化器跳过八槽并打印分歧
  （按缺件登记，不静默）。首例实测撞到的形状：某真项目的手册明写「本目录禁子目录」，其 `handoff-naming-check.py`
  把非 `templates` 的子目录判为 problem 并在 pre-commit **硬拦**，而 TTL 清理脚本用 `iterdir()` 只扫根
  ⇒ 八槽铺进去＝两套存放约定并存＋子目录里的件逃出 TTL＋撞它自己的门。空仓回归照旧铺 8 槽＋`templates`。
- **交接技能同步让位**（`kai-handoff` 0.3.1→0.3.2）：流程第 1 步与失败降级表各加一条——项目 README 无槽位表时
  按该仓自己的存放地／命名／TTL／门禁写，不造子目录；框架的槽位与 frontmatter 六字段只在有槽位表的仓生效。
- **初始化器 ADR 目录那行打印改口径**：已有 ADR 的仓印「不动（不写「从 0001 起编号」占位）」；
  此前印的「只补空目录占位」与 0.22.0 已改的行为不符（会报一个不发生的动作）。

## 0.22.0 — 2026-10-25

- **schema 4 复量再收三键**（[ADR-0015 D5](docs/adr/0015-schema-4-keys-with-consumers.md)）：删顶层 `repo_root` 与
  `runtime.main_tree.{discover,env_fallback}`。读数：安装面 53 份（`skills/`＋`loops/`＋`agents/`＋`adapters/`）里
  `main_tree`／`git_common_dir`／`KAI_MAIN_TREE`／`env_fallback` 命中 0 处；`repo_root` 只作 `skills/flight-info/flightinfo/*.py`
  的形参与 `ctx["repo_root"]`（运行时上下文）出现，无人按配置键读。叶子键 44→**41**、顶层段 11→**10**。
- **键数不再手写**：0.21.0 那条与 ADR-0015 首版一共写了三个数（88→44、段 19→12、Consequences 的 41），两个口径、互不一致。
  ADR-0015 D5 记下可复跑量法（doctor `_cfg_leaves`：不计 `schema`／`_note_*`）与三版读数表 88／17 → 44／11 → **41／10**；
  「段 19→12」量法没写明、复现不出，作废。README 与 0.21.0 那条同步更正。
- **`registry.playbooks[]` 行形状有了按名读者**：入口技能剧本段写出「一行四格」（`name`／`trigger`／`route`／`notes`）。
  此前四字段只活在模板示例里，逐键量具判为零读者（技能 2.5.2→2.5.3）。
- **初始化器两处实测缺陷**（在首个真项目实跑时撞到）：① 计划打印写死清单默认 `docs/adr`，答的是别的目录也照印默认
  ⇒ 改印答出来的目录，并注明是新建还是已存在；② ADR 目录已非空时仍写「从 0001 起编号」占位（在已有 137 号 ADR 的仓里是假话）
  ⇒ 只在目录为空时写占位。
- **初始化器「下一棒」补两条**：`gates` 值可带子命令（读取端按 `python <值>` 插值，例 `scripts/scope-check.py close-gate`）；
  `paths.audit_dir`／`module_cards`／`dashboard` 按本仓实有落点补、没有的留 null。
- **迁移段删除清单补全**（set-kai-mode 4.8.0→4.8.1）：schema 3→4 的「沿用」里去掉 `repo_root`，「删除」里补 `runtime.main_tree` 段与顶层 `repo_root`。
- 首例真项目实例落地：`某项目/.ai/kai-mode.project.json`（41 键与模板逐键相等、零占位、零机器绝对路径；
  14 个登记落点逐个 stat 通过；三门按该仓 AGENTS.md 实测值填；六人格模型全 null＝宿主默认）。

## 0.21.0 — 2026-10-25

- **schema 4：配置实例只留有消费者的键**（[ADR-0015](docs/adr/0015-schema-4-keys-with-consumers.md)）：按 `段.键` 点号形对全部活契约
  （16 个自动技能正文与脚本、`loops/`、`agents/`、`adapters/`、`scripts/`、`schemas/`、AGENTS、README）逐键取证，叶子键 88→44、顶层段 17→11（doctor `config-instance` 口径；发布时手写的「段 19→12」量法不明，0.22.0 作废）。
- 删：`wip`／`limits`／`approval`／`acceptance`／`audit`／`execution` 六段（名额/重试/审查独立/风险闸的家＝单票闭环协议与仓库红线，
  宿主工具契约的家＝`adapters/<宿主>.md`，实例里那份抄本没人读）＋ `gates` 12→3 键、`issue` 去 `ready_label`/`milestone_gating`、
  `tower_cron` 只留 `interval_min`、`runtime.deps` 只留 `check_dir_rel`。
- 更正上一轮的量具偏差：`paths.audit_dir`／`dashboard`／`module_cards`、`issue.verdict_marker` 其实有读者（塔台与协议按名读），本轮保留；
  0014 的「60 个零读者」是裸 token 匹配造成的误报，已在该 ADR 内标注更正。
- 缺省值再收一遍：`paths.audit_dir` → null（本项目没这记录面就如实报缺件）、`paths.state_dir` → `.git/kai-mode`（不再借别仓命名空间）、
  `set-kai-mode` 第 9 问缺省改空、依赖自检的包管理从 `pnpm` 改为按项目锁文件判定。
- 同步：`config-instance` 与解耦门的 models 检查认 schema 3/4；`set-kai-mode` 迁移腿改 2→3→4 并列明删除清单与验收；测试夹具升 schema 4；
  README 的「上限全部进项目配置 `limits`」改指 `loops/loop-protocol.md`。26 项全绿。
- 存量 schema 3 实例不自动改写：迁移由 `set-kai-mode` 走，逐字段 diff、多出来的键列给用户点头才删。

## 0.20.0 — 2026-10-25

- **配置实例零虚构值**（[ADR-0014](docs/adr/0014-config-instance-no-invented-values.md)）：从干净 clone 实跑 `init-project` 对账，
  量出 6 处漂移、本轮修 4 处硬矛盾——7 处 `<占位>` 落盘、`gates` 12 键全是本仓门名（用户项目里 0 个存在）、
  宿主两处（`host.adapter` 与 `execution.preferred`／`fallbacks`）、包管理与前端目录等本仓布局被当缺省塞给用户。
- 模板：没被十一问填到的键一律 `null`；`init-project.py` 加 `drop_placeholders()` 机械保证「占位不落盘」并打印被抹的键；
  第 9 问缺省从 `scripts/captain-preflight.py` 改空（别仓的门名不再自动进用户实例）。
- doctor 新增第 26 项 `config-instance`：实跑初始化器 → 断言叶子键集与模板逐键相等、零占位、零机器绝对路径、
  `gates` 非 null 只能来自问答清单；红绿回归 3 条。25→26 项口径同步 AGENTS／package-layout／domain。
- **量具有偏差**：同轮报的「60 个零读者」按裸 token 匹配，误伤了 4 个确有读者的键（`paths.audit_dir`／`dashboard`／
  `module_cards`、`issue.verdict_marker`——塔台与 loop 协议按名读它们）。ADR-0015 改按 `段.键` 点号形重取证据后再删。

## 0.19.0 — 2026-10-24

- **安装面零开发史**（[ADR-0013](docs/adr/0013-installed-payload-no-dev-history.md)）：新用户装完拿到的不再是我们仓的决策史。
  实测 16 个 `install:auto` 技能的 37 件 payload 里混着 70 条框架仓链接（私有仓＝死链）、27 处 `ADR-NNNN`、
  73 处 `docs/adr` 路径、18 处把维护者门禁 `scripts/doctor.py` 当用户验收步骤——现全部为 0。
- 改法：出处链接去链留文、`## 正本` 列表与「落地 000X」引言删除、frontmatter `sources` 只留随装件（`kai-mode` 空成 `[]`）、
  维护侧件改写成「框架仓 `loops/loop-protocol.md`（不随技能安装）」这种名称＋路径，判据留在技能正文。
- doctor 的 `payload-refs` 从「框架 URL 路径存在性校验」换成五条禁列实量（URL／ADR 文件名／ADR 编号／维护者门禁／装不走的相对链接），
  `install:manual` 件豁免；测试改成红绿各 4 条（含 `env-doctor.py` 合法反例）。项数仍 25。
- 口径回写：`docs/skill-layout.md` 定引用正本，`docs/package-layout.md` 硬规矩 4 与「维护侧引用」节改判据，
  删掉私有仓 404 访问说明；`docs/agents/domain.md` 现行裁决加 0013。
- **历史净化（2026-10-25 执行）**：`git filter-branch` 逐提交抹掉 `skills/**` 历史件里的四类 token（豁免 manual 件）。
  验收：提交数 60 不变、`main^{tree}` 前后同为 `a22d134`（现行内容面一字未动）、215 个历史 blob 版本 token 归零；
  远端 `4104cea → ea3ce62`（`--force-with-lease`）。备份与别的机器要对齐的动作见 ADR-0013 执行记录。

## 0.18.2 — 2026-10-24

- **本仓开发流水出库**：外部用户 clone 到的应是干净的方法论＋安装包。`handoff/` 的 3 份日期目录件
  （评审、重造交接／方案）与 `50-comms/2026-10/.gitkeep` 用 `git rm --cached` 移出索引，盘上证据不删。
- `.gitignore` 屏蔽 `handoff/*/YYYY-MM/` 与 `handoff/60-board/*/*.md`（槽位与看板状态的 `.gitkeep` 保留）。
- doctor 的 `tracked-cache` 加一轴：跟踪文件里出现本仓 handoff 流水 ⇒ 红；规范四件＋槽位占位放行，
  清单不在（用户项目）时该轴不适用。当前仓库 0 命中，新增红／绿各一条回归用例。
- 口径落点：`AGENTS.md` 红线补「this repo's own handoff records」，明细写进 `docs/package-layout.md`
  新「GitHub 上的仓库可见面」一节，`manifests/package-layout.json` 的 `_repo_only_note` 同步。

## 0.18.1 — 2026-10-24

- **开发数据不入库**：AGENTS 红线补「Commit/push development data」；`.gitignore` 扩到
  会话/日志/DB/缓存/验证报告/agent 数据。
- doctor 的 `tracked-cache` 扫面扩到 `.db`／`.sqlite*`／`.log`／`.jsonl`／`.tmp`／`.pid`
  与根级 `agent-data/`、`verify/`、`logs/`、`.cache/`；当前仓库 0 命中。
- `docs/agent-data-layout.md` 补 §7：运行数据不进 git，验证报告留在数据根。

## 0.18.0 — 2026-10-24

- **Claude Code 适配**：新增 `adapters/claude.md`（探测、起角色、项目级 `.claude/agents/` 人格、
  只读权限、模型、付费边界）；`adapters/README.md` 补 Claude 起岗位指针。
- **全局 agent 数据根**（[ADR-0012](docs/adr/0012-global-agent-data-root.md)）：`KAI_AGENT_DATA_ROOT`；
  Claude 用 `CLAUDE_CONFIG_DIR`、Codex 用 `CODEX_HOME`、OpenCode 用仅进程生效的 XDG 启动包装；
  项目数据仍由项目自管。
- 新增 [`docs/agent-data-layout.md`](docs/agent-data-layout.md) 与 `scripts/setup-agent-data.ps1`
  （dry-run／Apply／Migrate／OpenCodeLauncher；备份用户环境；复制不搬家；符号链接用 junction）。
- 本机落地：Claude Code 2.1.310 全局安装；Claude／Codex／OpenCode 配置与认证已复制到新根；
  OpenCode 大 DB 与 Codex 历史保留旧路径；Qoder 应用自管不改，已登记为例外。
- `set-kai-mode` 4.7.0：装机时按 `docs/agent-data-layout.md` 核对全局数据根。
- 适配器实测版本同步：Claude Code 2.1.310、Codex 0.164.0-alpha.11.1、OpenCode 2.1.4。

## 0.17.2 — 2026-10-24

- **引用口径收尾**：`docs/package-layout.md` 注明仓库当前为私有，绝对出处链接需仓库访问权限；
  无权限用户会 404，但技能运行不依赖链接。
- `vendor/README.md` 说明上游文档的 `./src/...` 等示例链接不是本仓文件、不参与 `broken-link`，
  不改 vendor（避免 `vendor-sync --check` 漂移）。
- `payload-refs` 增框架 URL 路径校验：指向 `kaikaikid/kai-mode` 的 `blob|tree/main/<path>`
  必须在本仓真实存在；附「缺失路径红、存在路径绿」用例。

## 0.17.1 — 2026-10-24

- **清理退役看板目录**：删除 `skills/航班信息`、`skills/set-航班信息`（v0.10.0 起由 `flight-info`
  取代；删除前确认无未提交件，git 历史可恢复）。
- doctor 移除 `LEGACY_LOCKED` 兼容分支：`unregistered-skill` 恢复严格「盘面==注册表」；
  `skill-tests` / `host-neutral` 不再按目录名跳过。
- `manifests/package-layout.json` 移除退役目录注记；ADR-0003 演进注改为「已从仓内移除」。
- `docs/canon.json` 移除两个退役目录的豁免项；首次审计记录补「已执行」收尾注。

## 0.17.0 — 2026-10-24

- **解耦收口**：活跃技能 payload 里 77 处指向本仓 `docs/`／`loops/`／`agents/`／`adapters/`／
  `handoff/`／`schemas/` 的相对链接改为 GitHub 绝对出处 URL；安装副本不再依赖本仓目录结构，
  技能内部与兄弟技能相对链接保留。
- doctor 新增第 25 项 `payload-refs`：安装面 Markdown 只能链自身、兄弟技能或 http(s)；
  出现本仓开发件相对路径即红，附回归用例。
- 修正 ADR-0003 活口：塔台表与部署步骤去掉「kai-mode 唤醒」；角色/唤醒器分离注记标明被 0010
  收窄；中文看板目录补退役演进注。
- `manifests/package-layout.json` 补 `.gitattributes`／`.gitignore` 与退役目录注记。
- 相关技能补丁版本：copilot/pilot 2.5.1、ground-crew 1.2.1、kai-mode 2.5.1、loop 5.3.2、
  principle-one-semantics-one-home 0.1.1、set-kai-mode 4.6.1、tower 1.4.1、flight-info 1.1.1。
- 验证：doctor --with-tests 25 项全绿；仓级 `scripts/tests` 66 条 ＋ 技能测试目录 29 条。

## 0.16.0 — 2026-10-24

- **三层打包边界**（[ADR-0011](docs/adr/0011-package-layout-three-layers.md)）：新增
  `manifests/package-layout.json`，把本仓开发件、宿主安装件、项目生成件分开；安装面只装
  `install:auto` 的运行件，项目骨架只从清单生成。
- 技能安装面排除 `tests/`、`__pycache__`、`.pytest_cache`、`*.pyc`；`magpie-sync.py` 的复制／比对／
  回执统一走 `payload_files()`，`apply` 备份后清掉库里残留的开发件。
- `init-project.py` 改读清单（不再硬编码槽位与复制源）；新增 `templates/GLOSSARY.md`；空
  `docs/adr/` 写 `.gitkeep`，结构能被 git 带进用户项目。
- doctor 新增第 24 项 `package-layout`：静态校验 ＋ 临时目录实跑初始化器，生成集合必须与清单
  逐件相等；`install-sync` 同时量库内残留开发件。
- 回归测试：源仓有 `tests/` 允许、安装面含 `tests/` 才红；交接历史作骨架源即红；骨架源缺失即红。
- 看板脚本移入 `kai-handoff/scripts/` 随技能安装（框架仓保留兼容入口）；交接骨架文档去掉本仓专名、
  ADR 链接与框架仓命令，改为项目中立写法。`kai-handoff` 0.3.0。

## 0.15.0 — 2026-10-24

- **角色唤醒围栏**（[ADR-0010](docs/adr/0010-role-wake-fence.md)）：`ground-crew`／`tower`／`pilot`／`copilot`／`kai-mode`
  之间不互相拉起/唤醒；只有**人工**与**定时器（仅塔台）**能唤醒角色。`kai-mode` 只推荐命令，不调用会话创建口。
- 塔台发现机长停摆：只写日表备注/Issue/播报，交人工唤醒继任机长；不自己开新会话。
- 适配器里的宿主启动命令统一标注「仅人工执行」；`set-kai-mode` 的 shell 启动档只用于唤醒塔台，其它角色人工。
- `docs/canon.json` 增 `wake-fence` 判据键，角色技能出现禁止的自动拉起短语即红；AGENTS 增 Wake fence 段。
- 相关技能版本：tower 1.4.0、pilot/copilot 2.5.0、kai-mode 2.5.0、ground-crew 1.2.0、set-kai-mode 4.5.0。
- 相互拉起的正式设计留待后续 ADR；在此之前本围栏是硬约束。

## 0.14.1 — 2026-10-24

- **角色与唤醒器分离**：明确塔台是独立岗位，定时器只是唤醒方之一；60 分钟是默认唤醒间隔，不是塔台定义。
  人工 `/塔台`、kai-mode 入口、定时器三路都只是“唤醒塔台”，无定时口时塔台照常可人工运行。
- 术语收敛：`塔台定时器` → `唤醒定时器`、`塔台任务` → `唤醒任务`、`定时器拉起的塔台` → `定时器唤醒的塔台实例`；
  同步 README、塔台/机长/副机长技能、set-kai-mode、ADR-0003/0004/0006、Qoder/opencode 适配器与配置模板 `tower_cron._note`。
- ADR-0006 增“角色与唤醒器分离”横幅；ADR-0003 增演变注。判据归属不变。

## 0.14.0 — 2026-10-24

- **语义审计入场**：新增 manual 技能 `harness-audit`（盘点器 + Keep/Improve/Update/Retire/Merge 判词，落
  `handoff/40-review/`），补 doctor 的“形状绿、语义盲”；不做硬门（[ADR-0009](docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md) D1）。
- **安装档位/回执/备份**：`manifests/install-profiles.json` 定 `core`（8 条）/`full`（16 条）；`magpie-sync`
  支持 `--profile`，库根回执记来源根/HEAD/档位/技能清单/哈希；写库前备份到 `<库根>/.backups/`（保留 5 份），
  异常或回写后漂移自动还原（D2）。
- **评审模式与收口**：`reviewer` 增 `silent-failure` 模式（空 catch/吞异常/危险 fallback/丢栈/缺 timeout）；
  `agents/dispatch.md` §10 增委派完成契约（最终消息即交付物、谁派谁收、不许以等后台 agent 结束回合）（D3）。
- **宿主中立与 YAML 形状**：doctor 增 `host-neutral`（宿主专有 token 只许住 `adapters/`）与 `frontmatter-yaml`
  （未加引号 `': '`、`@`/反引号开头）；`set-kai-mode` 的 Qoder 细节改指 `adapters/qoder.md`（D4）。
- **doctor 19 → 23 项**：新增 `frontmatter-yaml`、`install-profiles`、`install-receipt`、`host-neutral`；
  `--with-tests` 现在同时跑技能测试与仓级 `scripts/tests`，测试红＝门红。
- **P0 收敛**：模板 `interval_min` 30→60、playbooks route 改英文目录；`init-project` 写 `issue.platform`/
  `issue.boom_summary_ticket`/`host.adapter`，不再写无消费方的 `tracker.source`/`registry.ideas_pool_issue`；
  40 行回执统一为硬上限；ADR-0003 子代理上限、ADR-0006 过期阈值（125 分钟）对齐；README 与 `set-kai-mode`
  的过期路径/“九个技能”/schema 2 说法清理；补 `GLOSSARY.md` 与 `templates/verification-skill/SKILL.md`。

## 0.13.0 — 2026-10-24

- **六人格去 `kai-` 前缀**（[ADR-0008](docs/adr/0008-persona-model-config-and-host-adaptation.md) D1）：`agents/explorer.md`、
  `librarian.md`、`planner.md`、`worker.md`、`reviewer.md`、`visual-designer.md`，`name` 与文件名同名，正文互指改裸名。
  前缀的动因（中央库同名覆盖、`magpie-sync apply`）只对 `skills/` 成立——人格不经中央库安装，故不存在冲突。
- **术语归位（D2）**：四角色正式称**岗位**（会话身份，管权责），人格＝委派契约；删 `metadata.role`（与六人格 1:1、零信息）。
  `handoff` 的 `owner_role`／`persona` 两字段照旧承载，措辞统一。
- **六档词表退役，模型归用户（D3）**：删 `models.tiers`／`default`／`roles`；改 `models.agents.<人格>.model`（`null`＝宿主默认）。
  `scripts/init-project.py` 由十问扩到**十一问**（回车全默认／填一个模型名六个共用／`n` 逐个填；`--answers` 键 `agent_models`）。
- **人格 frontmatter 只留 `access`（D4）**：`role`／`tier`／`spawn`／`output` 全删（前三个无消费者，第四个与正文重复）；
  正文上限从自造的 35 行改回规范的 500 行，四小节降为建议。
- **宿主落法改为方法论（D5）**：删投影脚本与 per-host json、删无校验器的 `agents.schema.json`；
  新增 [`adapters/README.md`](adapters/README.md)——探测四步／六家落法对照／三级降级／缺件登记／装完自证／边界。
- **`vendor/` 纳入 git 跟踪 ＋ doctor 第 19 项 `vendor-sync`（D6）**：此前 `git ls-files vendor` 为 0，克隆出来缺 6 个技能；
  现在未跟踪即红、本机无镜像则 skip、有镜像比漂移。
- **入库 `security-audit`（D7）**：`vendor/skills/security-audit`（上游 `cloudflare/security-audit-skill`，MIT，`LICENSE` 随件，
  原样不改名不登记）。它是**父级编排**型六阶段漏洞猎取，接在 `reviewer` 的 `security` 模式上，不为它新增人格；
  需要 node 与 OS 沙箱，无沙箱时结论最高 `needs_validation`。
- **doctor 项数 18 → 19**；`agents-contract` 收窄到规范派生规则（顶层键／name==文件名／`metadata` 只许 `access`／正文 <500／
  零外链／零 slug／README 两向一致／`persona` 有家）。

## 0.12.0 — 2026-10-24

- **子代理人格层按行业规范重建**（[ADR-0007](docs/adr/0007-agents-layer-generic-contract.md)）：人格 frontmatter 只留规范顶层字段
  （`name`/`description`/`version`/`license`/`compatibility`/`metadata`），自有语义 `role`/`access`/`tier`/`spawn`/`output`
  全部进 `metadata` —— Agent Skills 规定的唯一合法扩展位。正文固定四小节（我是谁／范围与权限／输出契约／交棒）、≤35 行、零外链。
- **人格收成 6 个**：撤销 `kai-archivist`，能力降为 `kai-explorer` 的 `large-source` 模式（依赖多数宿主没有的 1M 宽窗）；
  确立「模式先于人格」——新增能力先加 `mode`，不加文件。
- **一源多投影**：新增 `adapters/opencode.json`（`tier_models`／`access`→`permission`／`spawn_deny`／`emit_to`）＋
  `scripts/agent-emit.py`（`--host` 生成、`--check` 报漂移）。人格不再写工具名与模型 slug，六家六种权限写法由投影表吸收。
- **doctor 加两项门禁（16 → 18）**：`agents-contract`（顶层键白名单／name==文件名／metadata 枚举／四小节／零外链／
  README 表两向一致／handoff `persona` 有家）、`canon-dup`（退役词黑名单 ＋ 判据键唯一家，`docs/canon.json` 为正本）。
- **清退平行正本**：`skills/kai-mode/playbooks/` 七件按归位表逐节归位后删除（判据进 `loops/loop-protocol.md` §七、
  派发策略进 `agents/dispatch.md`、审批红线进 `AGENTS.md`），`skills/kai-mode/SKILL.md` 的「七件剧本」改为「正本地图」一张表。
- **根因治理**：`AGENTS.md` 增「一类判据一个家」归属表与 Red lines 表；退役词（租约／班次／按铃／Coordinator／合同哈希／
  五角色／Group-A）在 adapters、tower、set-kai-mode 里清零。
- **修两处断句**：`agents/kai-*.md` 与 `loops/loop-protocol.md` 里批量替换留下的 `> ），…` 残句全仓清零。

## 0.11.0 — 2026-10-24

- **看板人读面按 Diagram Design 的 editorial 皮肤重做**（`flightinfo/render.py` 的 `CSS` 常量）：
  纸／墨／次字／赭四色 tokens、标题衬线＋正文无衬线＋票号等宽、发丝线代替阴影、圆角 ≤8px、间距 4 的倍数；
  跟 `prefers-color-scheme` 出整套暗色。**赭色只留两处**（方向句红线、阶段轨焦点数字），
  源失败时才多一个赭点——同一个语义：有活要干。
- **版式改结构**：页头（`RUN <run_id>` 小标 ＋ 衬线大标 ＋ 生成时刻）→ 方向句 → **阶段轨**
  （一条带子＋发丝分隔，链外阶段挂虚线右侧）→ 次级读数 → 航班表 → 排班表 → 源状态。
  原「五张等宽 KPI 卡」取消（等宽卡片是反模式），`view.kpis` 退役，改 `view.focal_stage` /
  `view.font_source` / `view.metrics` / `view.labels` / `view.eyebrow`。
- **字体缺省走本地栈，零网络**（国内 `fonts.googleapis.com` 不可达会拖首屏）；要正版字体设 `view.font_source: "web"`。
- **修三处真 bug**：①链外阶段（可领／挡住）名字掉成「未定」——`collect` 的阶段名表只收了 `stages`；
  ②航班行按 `stage` 字母序排（closed→flying→hold…）——`build_summary` 改按阶段链顺序，同阶段新的在前；
  ③`next_label` 与阶段名相同时界面重复一遍——相等即不显示。
- **KPI 加 `by_stage`**（`{阶段key: 张数}`），自定义阶段也认；`closed` 单独成项。
- **测试** 21 → 24 项（链序、链外阶段名、下一步去重）。

## 0.10.0 — 2026-10-24

- **看板展示层重做为 `flight-info`**（原 `航班信息` 退役，目录被环境锁死待人工删）：
  - **数据落 SQLite**：`schema/001-init.sql` 定义 `flight` / `evidence` / `schedule_row` / `source_run` / `board_run`
    ＋ `v_flight` 视图；一板一库（`board.db`）。只用标准库 `sqlite3`。
  - **模块化解耦**：`db`（唯一碰库）← `stage`（纯判据）← `sources/*`（一源一文件，不连库）← `collect`（编排合并）
    ← `render`（只读库出两个产物）、`config`（加载校验定位）。加源＝加一个模块 ＋ REGISTRY 一行。
  - **渲染不再烘焙进板**：板目录只留 `board.config.json` ＋ `board.db` ＋ 产物；改渲染逻辑一处全生效。
  - **装配合并**：不再单独设装配技能，用 `scripts/init_board.py`。
- **触发层改成「钩子只打标记 ＋ 有脏才刷」**：`install_hook.py` 写 `.git/flight-info-dirty`（退出码恒 0，绝不阻塞 commit），
  `refresh_if_dirty.py` 有脏才刷、刷完清标记。避免 commit 等几十秒联网。
- **中文只作唤醒词**：`name: flight-info`（Flight Information），`metadata.alias: 航班信息`，口令 `/航班信息` 照旧。
- **doctor 两处改进**：`skill-tests` 无 pytest 时退化到标准库 `unittest`、跳过 `LEGACY_LOCKED`；
  `install-sync` 遇源件拦读记 `skip` 并点名。**16 项全绿（0 红 0 跳过）**。
- **测试**：`tests/test_flightinfo.py` 21 项（判据优先级、frontmatter 解析、跨源合并、库幂等、视图只认最新轮、
  配置校验、KPI、摘要裁剪、端到端）。全绿。

## 0.9.1 — 2026-10-24

- **看板确立三层**：数据层 `handoff/60-board/`（卡片，AI 读写）＋ 展示层 `航班信息`（人读 HTML ／机读 `board.json`）
  ＋ 触发层（git 钩子 `post-commit`/`post-merge` ＋ 系统闹钟）。层间**只靠触发层连，不共享文件**；展示层单向只读。
- **`航班信息`／`set-航班信息` 恢复为正式件**：重新登记 registry（`kind: framework`、`install: auto`），
  `LEGACY_LOCKED` 清空。它们不是旧项目遗留，是航空体系看板的展示形态。
- **去「板工坊」旧称**：两份 SKILL.md 一律改称「看板展示形态／装配面」，与 `docs/` 用词对齐。
- **清具体项目痕迹**：板配置样例 `.design/航班信息/HTML` → `boards`；删 `~/.codex/ysk/notes.jsonl` 源与对应视图段；
  去掉 `判据出处：项目仓 ADR-xxxx` 注记；`set-kai-mode` 里写死的 `.design/` 落点改为「板库根＝板配置 `output.root`」。
- **修死引用**：`set-kai-mode` 装机清单里的四角色目录仍是改名前的 `{地勤,塔台,机长,副机长}`，改为 `{ground-crew,tower,pilot,copilot}`。

## 0.9.0 — 2026-10-24

- **只留 kai-mode 自己的东西**：旧项目设计吸收稿、Codex 退役契约（`subagents/`）、迁移档（`MIGRATION.md`）、
  旧项目 ADR 注记与「重述自项目仓」段落、pstack 署名 —— 全部出仓，
  备份在仓外隔离区（未硬删）。技能 17 → 15。
- **塔台轮巡 30 分钟 → 1 小时**：`0003`／`0006`／`tower`／`set-kai-mode`（cron `0 * * * *`）／项目配置模板／`loop-protocol` 同步。
- **通用方法改原样拉取**：`vendor/skills/`（tdd／code-review／diagnosing-bugs／domain-modeling／to-tickets／writing-for-agents）
  ＋ `scripts/vendor-sync.py`（`--check` 校源与副本一致）＋ `vendor/manifest.json` 逐文件 sha256。
  **不改内容、不改名、不登记 registry**，`skills/` 只留本仓设计件。
- **`handoff/` 增 `50-comms`**：角色之间传话（`msg`／`ask`／`answer`／`notice`），配 `templates/COMMS-template.md`；
  与 `60-board`（派活）分工固定：要人干活走看板，只让人知道走这里。
- **新装项目走 QA**：`scripts/init-project.py` 十问 → 生成 `.ai/kai-mode.project.json` 实例，
  并把 `handoff/`（八槽＋规范＋模板）与 `docs/`（`adr/` ＋ `GLOSSARY.md`）作为**组件**一起铺，已存在不覆盖。
- **doctor**：`PermissionError` 记 `skip` 而非红（红要能修）；`handoff-slots` 认 `50-comms` 与四个沟通类型词。

## 0.8.0 — 2026-10-24

- **新增一个技能**：`kai-boom-idea-log`（想法入库）——地勤「分流」步的方法与模板正本。
  这是本批唯一满足特化判据的一份：落点与发布动作由本仓角色分工决定，上游那份写死了单项目票号与目录。
- **确立 fork 判据（写进契约）**：只有「判据由本仓设计 ＋ 有本仓接口 ＋ 不 fork 就没有家」三条全中才特化入库并加 `kai-` 前缀；
  **通用方法一律按上游名引用，不 fork、不改名、不登记**。落在 `docs/skill-sources/workflow-skills.md` §2 与 `docs/skill-layout.md` §1。
- **六个按上游名引用**：`tdd`（施工）、`code-review`（审查）、`diagnosing-bugs`（诊断）、`domain-modeling`（定稿·术语）、
  `to-tickets`（定稿·拆票）、`writing-for-agents`（写文档）。方法住上游，流程仍住 `loops/loop-protocol.md` 与角色技能；
  `loop`／`kai-mode` 的 `dependencies` 改为写上游名。
- **素材库**：`docs/skill-sources/workflow-skills.md`（打包摘要 ＋ 逐源结论 ＋ 对账四步），`sources.json` 13 条：
  2 `adopted`、6 `referenced`、2 `watching`（`prototype`／`pr`）、3 `dropped`（`research`／`implement`／`grilling`）。
- **技能总数 16 → 17。**
- **收工门禁回归单一正本**：门禁脚本归项目仓（配置实例 `gates.captain_preflight`），框架不再自带副本；
  `pilot`／`copilot`／`loop` 三处命令改为读配置门，`null` 即报缺件。同步修正车道口径为 `main|deputy`。
- **补两处闭环缺口**：`tower` 增「验证命令」（发货前核提交、关票门、收尾门各一条）；`kai-handoff` 增「失败降级」（判不出槽、类型词未登记、门禁红、超寿命、票状态五类）。

## 0.7.0 — 2026-10-23

- **提示词真正瘦身**：`机长` 7253→约 3.2k 字节、`副机长` 7170→约 1.4k 字节、
  `loop` 6154→约 1.3k 字节；三份合计约 5.9k 字节，较 0.6.0 降约 71%。
- **围栏 / 负担分层**：硬约束只留不写码、不 push / 合并 / 关票、不写日表、不改 AC / 判词、
  单写手、同文件域不并行、审查新上下文、红线只停该票、收工复查。派几个子代理、拆活方式、
  回执与评论详略、机动子代理都归自决，不再写成「必须 / 禁止」。
- **宿主中立**：预检只依赖 `python + git + gh`，不引用任何宿主专有 API；技能正文只留
  `/机长` / `/副机长` / `/kai-mode` 入口。
- **单一详细源**：流程细节只留在 `loops/loop-protocol.md`；三份技能只写启动、围栏、自决、
  收工复查和断点，不再复制七步闭环与审查细则。
- **与 #1877 对齐**：子代理不设数量硬上限，任务级 WIP 仍是一机长同时最多 2 张 issue。

## 0.6.0 — 2026-10-23

- **去掉子代理编制上限（用户拍板）**：`机长` / `副机长` / `loop` / `loops/loop-protocol.md` / `README.md`
  同步改为「一机长同时最多 2 个 issue；子代理按需展开、不设数量硬上限」。保留每票 1 施工 + 1 审查、
  审查必须新上下文、单写手、同一文件域不并行这四条硬线；机动子代理由固定 2 个改为按需拉起。
- **收工前强制复查**：三份技能与协议正文补「手上票做完后重新读日表与 Issue；有新排班继续跑，
  确认无新任务才停」，堵住「读到旧表就提前收工」。

## 0.5.0 — 2026-10-22

- **航班信息板定时刷新落地（零 token、跨 agent）**：新增 `skills/航班信息/scripts/install_refresh_timer.py`
  —— 走**操作系统闹钟**（Windows 任务计划 / POSIX crontab）直接调该板的刷新壳（纯 Python），
  不经过任何 AI ⇒ 零 token；不依赖宿主定时口 ⇒ 换哪家的 agent 跑、甚至没 agent 在跑都一样刷
- **修掉一条断链**：航班信息原先声明「定时由 set-kai-mode 装」，但塔台技能的 9 段工作流里**一次都没提刷板**，
  塔台定时器只叫醒塔台排班发货 ⇒ 板的数据停在最后一次人工刷新（实测停在 6 小时前）。
  现改为板工坊自己装系统定时器，塔台职责不变；`set-kai-mode` 补一句「两套定时器各管各的，别混」
- 刷新通道写进文档：四条通道只有「系统闹钟」和「人工跑生成器」两条真更新；
  页面「刷新」按钮只是重读磁盘旧文件，页面 60 秒计时只改「几分钟前」文字
- 系统命令调不动（没装 / 被安全策略挡）时**如实报「调不动 / 查不了」，不再崩栈**，也不冒充「未装」
- 新脚本自带回归 `scripts/tests/test_install_refresh_timer.py`（9 条：扫板 / 壳行尾 / 降级 / 状态区分 /
  干跑不写盘 / 协议解析 / 协议干跑不写注册表 / 分发降级）
- **页面「刷新」按钮跟刷新脚本绑上**：`--register-protocol` 注册系统级 `flight-info://` 协议（HKCU，
  用 pythonw 不弹窗），模板改「隐藏 iframe 触发协议 → 4 秒后重载」，没装协议静默降级为重读旧文件；
  机器级小账本 `~/.kai-mode/flight-info-boards.json` 记「板名 → 刷新壳」
- **事件驱动落地**：`--install-hook` 给项目仓挂 `post-commit` ＋ `post-merge`（不碰既有 pre-commit / pre-push），
  首选 `schtasks /Run` 异步叫醒定时任务；带 60 秒去抖；没装定时任务只提示不硬刷
- 实测留档：纯本地源刷一次 ≈2 秒，**联网的机场板一次 ≈55 秒**（73 票 + 69 交接）⇒ 周期别压到 1 分钟，钩子绝不能同步硬刷

## 0.4.0 — 2026-10-22

- 新增装配技能 `set-航班信息`：选配置 → 建板 → 补 `.gitignore` 规则 → 出第一版板 → 出索引 → 回执；默认不动中央库，显式 `--install` 才装
- 板面改软 UI 壳层：**左侧垂直侧边栏**（**壳层几何**取自中央库 soft-design-system §06 当前版）
- **板面配色回退到板子自己的暖纸色系**（`--paper`／`--card`／`--ink`／`--accent`／`--accent-soft` 等；中央库的冷灰＋暖黄色板撤掉；几何仍用中央库实值）
- 板面改造：排班表置顶 ＋ 逐段可折叠
- **装机来源标记**：中央库记住从哪个仓装来的（谁跑都回本仓）
- **doctor 第 13 项 `install-sync`**：库副本与本仓逐字对账 ＋ 核对来源钉没钉死

## 0.3.0 — 2026-10-22

- 技能注册表 `registry.json` 落地：技能清单单一事实源，装机清单从它派生（`install:auto`）
- 仓级校验入口 `scripts/doctor.py`：注册表 / 契约 / 链接 / 绝对路径 / 行尾 / 版本 / 测试，一条命令验全仓
- 技能目录契约 `docs/skill-layout.md` ＋ 骨架模板 `templates/skill/SKILL.md`
- 行尾口径 `.gitattributes`：`.bat`＝crlf（防 cmd 崩）
- 航班信息技能升级为板工坊：板配置 ＋ 模板 ＋ 脚手架 ＋ 板库归档
- `magpie-sync.py` 装机布局档：本仓自身可作正本根
- **doctor 加装机同步检查**（第 13 项 `install-sync`）：中央库副本与本仓逐字对账（逐文件 SHA-256）＋ 库记住的装机来源是不是本仓（`.kai-mode-source.json`）；红了当场给 `apply` 修法 ⇒ 「本仓为准」从口头约定变成可发现
- **宿主装机切到本仓**：`apply --root <本仓>` 实装，8 个宿主（`.claude`／`.cline`／`.codex`／`.cursor`／`.dsh`／`.qoder-cn`／`.workbuddy`／`.workbuddy-ai`）装齐 8 个技能（新增 `航班信息`），`library.json` 追加 11 个平台条目；装机拷贝跳过 `__pycache__`／`*.pyc`
