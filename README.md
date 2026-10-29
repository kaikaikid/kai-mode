# kai-mode —— 机场体系的技能与通用剧本仓库

> **状态：0.34.0（2026-10-29 通用方法改 fork：7 个通用方法技能迁入 `methods/` 插件、加 `kai-` 前缀、可微调，`vendor/` 与 `vendor-sync` 退役，上游更新人工吸纳；见 [ADR-0026](docs/adr/0026-fork-generic-methods-with-kai-prefix.md)）。上一版 0.33.0（2026-10-28 文娱集团落地：新插件 `studio`——企划/主笔/主美/导演/终审/宣发六岗位，共享协议＋四个薄子代理模板；三坊两台改名，make 降为子代理）。上一版 0.32.0（2026-10-28 体检修复：AGENTS.md 死指针与人格局残留清退、协议版本三方统一 v11、`source-check.py` 退出码按需处理数返回、CI 补跑 `--with-tests`、doctor 补机器路径扫描面＋正文指针可解析性检查、schemas 三件退役、ace 执行帽正本收口协议 §一；第二波：doctor 硬化＋canon 数值键＋ADR-0025＋vendor 溯源）。上一版 0.31.0（2026-10-27）：塔台待发货探测：新增 `ship-queue.py`，从 Issue 判词派生待发货队列，增量扫描（`since=`）＋写前日志＋「票已关／sha 已进 `dev`」自动退役；零票时塔台只读一行即走轻量轮，探测失败 `rc=3` 不等于零票；机长不写账本。worker 预算加档：每车道子代理限额 3→5，规划权仍在机长（[ADR-0024](docs/adr/0024-worker-budget-five-per-lane.md)）。定时器改**门卫薄壳**：`wake-gate.py` 先判上一轮是否还在跑、有没有活，跳过时零模型调用（首个适配宿主＝Claude Code）。航班信息板换骨：KWP 暖白陶橙皮肤 ＋ 看板列＝阶段，新增待发货队列与塔台灯，钩子扩到三枚、30 分钟脚本定时器零黑窗，`--max-age` 兜底 GitHub 侧更新。初始化遇到同名不同内容技能时逐条问用户去留，默认保留现有，不再静默覆盖。上一版 0.30.0：二副车道——新增第四位机长 `second-officer`，塔台排班扩到三张正常日表，Issue 车道标签补齐四条；见 [ADR-0023](docs/adr/0023-second-officer-fourth-pilot-lane.md)）。**
> （[0003：四角色＋1 小时唤醒塔台](docs/adr/0003-airport-rebuild-four-roles.md)；[0020：王牌飞行员加急车道](docs/adr/0020-ace-pilot-expedited-lane.md)）；**本仓是宿主装机正本**（`magpie-sync apply --root <本仓>`，
> 按市场清单的插件目录装齐，当前 27 条自动件），项目仓那份技能副本只作镜像。
> 旧五角色（Tower/Ground/Coordinator/Group-A/B）、租约、班次、handoff 按铃那套已随机场体系重做退役（本仓 [0003](docs/adr/0003-airport-rebuild-four-roles.md)）<!-- canon:allow-retired -->
> （git 历史可捞）。

> 使用手册（HTML，多页）：[manual/index.html](manual/index.html)；完整技术图在附录。

## 这是什么

kai-mode 是「一句话需求 → 票 → 排班 → 施工 → 审查 → 发货 → 关票」的闭环框架。

**仓定位（2026-10-22 用户定口径）**：本仓**独立于任何项目仓** —— 不属任何项目仓，**不受项目仓的票、日表、审查与门禁约束**；它只放**跨项目通用**的部分（别的仓能直接拿去用的那种）。

- 技能清单：**以 [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) 为准**（单一事实源；安装器从插件目录现场派生，本文件不再手写名单）。两类：
  - **框架技能**（`kind: framework`）：框架本身的一部分，各项目都该有，默认 `install: auto` 进中央库；
  - **个人技能**（`kind: personal`）：只给自己用的，默认 `install: manual`，**不进中央库**。
- 协议正本：`airport/skills/loop/references/loop-protocol.md`（v11）
- 通用方法：`methods/skills/kai-*`（fork 自上游，`kai-` 前缀；可微调，改动记 `deltas`，上游更新按 30 天对账人工吸纳）
- 宿主适配器：Qoder（60 分钟唤醒定时器＋按需子会话）、opencode/codex 备胎
- 项目配置模板：`templates/kai-mode.project.json`

项目自己的 ADR、票、日报、门禁脚本与项目专用剧本留在项目仓。

## 角色（单责）

| 角色 | 口令 | 只负责 | 绝不做 |
|---|---|---|---|
| kai-mode 入口 | `/kai-mode` | 一句话需求 → 判断 → 拷问 → 定稿 → 拍板 → 路由 | 执行 |
| set-kai-mode 装配 | `/set-kai-mode` | 安装、探测、装定时器、doctor、缺件登记 | 日常施工 |
| upgrade-kai-mode 升级 | `/upgrade-kai-mode` | 读回执与漂移表出升级清单、备份、回写、迁移、验收、回滚 | 首次安装、碰项目数据 |
| 地勤 | `/ground-crew`（说「地勤」也认） | 对话、规划、开票（六件套＋`ready-for-agent`）、收想法 | 写码、push、派施工 |
| 塔台 | `/tower`（说「塔台」「出货」也认） | 独立岗位；默认每 60 分钟由定时器唤醒，也可人工唤醒；kai-mode 只推荐命令；先发货、后补排班（日表行数见协议正本，放本轮最后） | 写码、替审查下结论 |
| 机长 / 副机长 | `/pilot` `/copilot`（说「机长」「副机长」也认） | goal 模式滚动跑完自己那张日表（在飞帽只算未完工票，`pass` 进待发货即释放）；每票 1 施工＋1 审查（新上下文），跃迁窗口内取舍派只读裁决子代理出 `ruling=` | 写码、push、合并 |
| 二副 | `/second-officer`（说「二副」「第二副机长」也认） | 同机长：滚动跑完 `-second.md`；第三条正常机长道，与副机长并列而非替补 | 写码、push、合并、读写别人的日表 |
| 王牌飞行员 | `/ace`（说「王牌」也认） | 用户直连的加急通道；读加急队列标签票，在自己那张 `-ace.md` 滚动消费（执行帽口径见协议 §一）；简单免票热修、复杂自补票 | 写 `-main`/`-deputy`/`-second` 日表、push、合并、关票 |

**权限硬线（[0003](docs/adr/0003-airport-rebuild-four-roles.md) ＋ [0020](docs/adr/0020-ace-pilot-expedited-lane.md) ＋ [0023](docs/adr/0023-second-officer-fourth-pilot-lane.md)）**：塔台**独占** push 与关票；机长/副机长/二副/王牌只管理不写码（王牌热修是受控例外）、不 push；地勤只开票；记录面三分——主、副、二副三张日表只由塔台写、王牌日表只由王牌写、状态只写 Issue 评论、代码只进分支。

**唤醒围栏**：正本＝协议 §一（裁决理由见 [0010](docs/adr/0010-role-wake-fence.md)）；kai-mode 只推荐命令、不自动起角色。子代理是票内委派，不受此围栏影响。

## 闭环

```text
用户一句话 → /kai-mode（拷问→定稿→拍一次板）
                    │
                    ▼
              地勤（开票：里程碑＋ready-for-agent＋AC＋禁区）
                    │  三选一：等塔台（不打标）│ 进王牌队列/现在拉起（打加急队列标签）
                    ├──────────────────────────────────┐
                    ▼                                  ▼
              塔台（先发货：合并/push/关票，           王牌飞行员（写自己的 -ace.md，
                    最后补排班写两张日表）              同刻 1 张；简单可免票热修）
                    │                                  │
                    ▼                                  │
        机长 ──┬── 机长 ──┐   ← 主/副/二副各按协议名额在飞；子代理按需
        副机长 ├── 副机长 │
        二副   ┘          │                          │
       （每票：施工子代理[车道工作树] → 审查子代理[新上下文]）
                    │  verdict=pass ＋逐条 AC 证据 → 「待发货」
                    ▼
              塔台（再发货：批内合并 → 收尾门一次 → push 一次 → 关票）
                    │
                    └── 库存下降 → 下一轮补排班
```

记录面三分：**日表**（主、副、二副塔台写／王牌写自己的，排班视图）＋ **Issue 正文与评论**（唯一事实源）＋ **分支与提交**（代码与回执）。断点三件套 = 这三样，继任者按它续跑。
热修免票但仍留四件：分支提交、新上下文判词、`-ace.md` 的 `H-` 行、当日日报——**少的是票，不是记录**。

## 交接与断点（省叙述，不省证据）

- 票进入日表即完成领取；状态只由机长写 Issue 评论（开工/施工完成/审查完成/待发货/卡点）。
- 施工回执字段固定为 `ticket/role/verdict/files/commits/checks/summary/evidence/risks/next`，行数上限与字段语义见 [loop-protocol §五](airport/skills/loop/references/loop-protocol.md)；禁止贴 diff 全文与原始日志。
- 塔台发货**只认审查子代理的判词**（`verdict=pass` 且逐条 AC 有证据），不认机长口头总结。

## 可靠性（[loop-protocol §七](airport/skills/loop/references/loop-protocol.md)）

- 单票失败 **1 次重试**；再失败 → 卡点停票；同错连发触发熔断。
- 上限数值只住 `airport/skills/loop/references/loop-protocol.md`（票级协议的家），实例不再抄一份；到限写 `blocked`/`failed` 留读数，不许「再试一次看看」。
- 红线（花钱/对外真发布/不可逆改历史/删未提交内容）→ **只停那张票**，立即报人。

## 目录

```text
.claude-plugin/marketplace.json   唯一分发清单：六个剧本插件的名字、版本、来源
airport/    机场体系剧本：commands/（六岗位）＋ skills/（loop·pilot·copilot·second-officer·tower·ground-crew·ace）
core/       入口与安装剧本：commands/ ＋ skills/（入口、安装、交接、审计、六条原则）
board/      看板剧本：skills/flight-info（SQLite → board.json ＋ index.html）
intake/     想法池剧本：skills/kai-boom-idea-log
ops/        事故与运维剧本：skills/incident-response、skills/runbook
studio/     文娱集团剧本：skills/studio（共享协议）＋ 企划/主笔/主美/导演/终审/宣发 六岗位
<插件>/.claude-plugin/plugin.json  Claude Code 插件清单
<插件>/.qoder-plugin/plugin.json   Qoder 插件清单
<插件>/PLAYBOOK.md                 剧本总览：角色、阶段、记录面、红线指针
<插件>/CONNECTORS.md               工具类别与降级
manifests/  install-profiles.json（档位）· package-layout.json（三层边界）· plugins.lock.json（版本/摘要钉死）
scripts/    仓级工具：doctor.py（校验入口）· plugin-check.py（清单体检）· init-project.py
adapters/   宿主落法：README（总则）＋ claude、qoder、codex、opencode
templates/  kai-mode.project.json（schema 4）＋ skill/ 技能骨架
manual/     使用手册（多页静态 HTML；技能表由 scripts/manual-gen.py 生成）
docs/       ADR、技能契约、打包说明、设计图
CHANGELOG.md  版本变更记录
```

## 接入一个新项目

1. 项目根写 `.ai/kai-mode.project.json`（从 `templates/` 复制），填运行时**发现方式**（主树反推、env、相对路径）与门禁命令；机器绝对路径不入库。
2. 把插件目录里的 `skills/` 落到项目仓技能目录或宿主技能目录（或由 `set-kai-mode` 按宿主装配）；判据正本随 `loop` 技能安装。
3. `/set-kai-mode` 探测宿主能力（定时口 / 会话创建口 / shell 启动器），按四档可选装配 60 分钟唤醒定时器（只唤醒塔台，不是塔台本体）；装机按 `core`／`full` 档位（`manifests/install-profiles.json`），缺件如实登记。
4. 项目 ADR 记角色与权限裁决（先例：本仓 [0003](docs/adr/0003-airport-rebuild-four-roles.md)）；开票走地勤六件套；用一张真票走通「排班→施工→审查→发货」全链路做自证。
5. 项目专用路径、票号、job id 只进项目配置与本机文件，不进本仓技能正文。


## 加一个技能（四步）

1. **选剧本**：把 [`templates/skill/SKILL.md`](templates/skill/SKILL.md) 复制到 `<插件>/skills/<名>/SKILL.md`，把 `<占位>` 全替换掉（目录名＝frontmatter 的 `name`）。
2. **登记剧本**：已有剧本直接放进去；新剧本才在 [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) 加一个插件目录（含两份 `plugin.json`）。
3. **体检**：跑 `python scripts/plugin-check.py --bump && python scripts/doctor.py`，全绿才算加完 —— 漏登记、版本漂移、摘要不符都会红。
4. **刷新手册**：跑 `python scripts/manual-gen.py`，把新技能写进 `manual/assets/skills-data.js`；手册的技能表只读这份生成数据。

契约细节（目录必含什么、frontmatter 八字段与顺序、插件清单字段、读契约）见 [`docs/skill-layout.md`](docs/skill-layout.md)。

## 验证

一条命令验全仓：

```bash
python scripts/doctor.py --with-tests
```

覆盖：市场清单与插件清单、每个技能的目录与 `SKILL.md`、frontmatter 八字段与顺序、三处 name 一致、盘上有技能目录但没登记、`SKILL.md` 相对链接断链与宿主中立、机器绝对路径入正文、正文指针指向的仓内文件、协议版本号三方一致、仓内行尾口径、`VERSION` 与本文件版本串一致、解耦门、交接文档分类、Agent Skills 1.2 对齐、判据归属、中央库副本与本仓是否逐字相同（`install-sync` 项），以及各技能自己的 pytest。

清单与版本另有一道独立体检：

```bash
python scripts/plugin-check.py
```

覆盖：市场↔插件↔两份 `plugin.json`↔技能名/版本↔`manifests/plugins.lock.json` 的版本与内容摘要↔`core`/`full` 档位。

单独跑某个技能的测试：见该技能 `SKILL.md` 的「验证命令」段（如 `python -m pytest board/skills/flight-info/tests/ -q`）。

## 当前不做

- 不改项目仓的日表、Issue、门禁脚本——那些归项目仓与各角色。
- 不把项目专用路径、票号、job id 写进技能正文。
- 项目专用件（ADR、票、日报、门禁脚本、项目专用剧本）不进本仓。
- 个人技能默认 `install: manual`，不进中央库。
- 装机正本＝本仓（插件目录里可安装的技能）；项目仓 `.ai/skills/` 只是镜像，不是装机源。中央库记住装机来源（`<库根>/.kai-mode-source.json`），从库里那份脚本跑，正本根也回到本仓。

## 判据正本

- 插件化剧本（现行结构）：本仓 [`docs/adr/0021-plugin-playbooks-and-persona-retirement.md`](docs/adr/0021-plugin-playbooks-and-persona-retirement.md)
- 在飞容量与并行判据（触面互斥／共享状态黑名单／执法门）：本仓 [`docs/adr/0022-touchset-based-inflight-cap.md`](docs/adr/0022-touchset-based-inflight-cap.md)
- 机场体系裁决：本仓 [`docs/adr/0003-airport-rebuild-four-roles.md`](docs/adr/0003-airport-rebuild-four-roles.md)
- 单句入口与拍板：本仓 [`docs/adr/0002-single-entry-and-dual-lane.md`](docs/adr/0002-single-entry-and-dual-lane.md)
- 评估与安装治理：本仓 [`docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md`](docs/adr/0009-harness-audit-install-profiles-and-host-neutrality.md)
- 角色唤醒围栏：本仓 [`docs/adr/0010-role-wake-fence.md`](docs/adr/0010-role-wake-fence.md)
- 三层打包边界：本仓 [`manifests/package-layout.json`](manifests/package-layout.json)（说明 [`docs/package-layout.md`](docs/package-layout.md)，裁决 [`0011`](docs/adr/0011-package-layout-three-layers.md)）
- 全局 agent 数据根：本机 [`docs/agent-data-layout.md`](docs/agent-data-layout.md)（裁决 [`0012`](docs/adr/0012-global-agent-data-root.md)）
- 单票闭环协议：本仓 `airport/skills/loop/references/loop-protocol.md`（v11）
- **技能清单与装机清单**：[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)（安装器从插件目录现场派生）
- **技能目录契约**：[`docs/skill-layout.md`](docs/skill-layout.md)（目录结构 / frontmatter 八字段与顺序 / 注册表字段 / 读契约）
- 版本与设计沿革：`CHANGELOG.md`（逐版变更）＋ `docs/adr/`（裁决）
