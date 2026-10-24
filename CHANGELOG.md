# CHANGELOG

本仓变更记录；按版本倒序，每条一行。版本号正本＝仓根 [`VERSION`](VERSION)。

## 0.17.1 — 2026-10-24

- **清理退役看板目录**：删除 `skills/航班信息`、`skills/set-航班信息`（v0.10.0 起由 `flight-info`
  取代；删除前确认无未提交件，git 历史可恢复）。
- doctor 移除 `LEGACY_LOCKED` 兼容分支：`unregistered-skill` 恢复严格「盘面==注册表」；
  `skill-tests` / `host-neutral` 不再按目录名跳过。
- `manifests/package-layout.json` 移除退役目录注记；ADR-0003 演进注改为「已从仓内移除」。

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
