# kai-mode —— 机场体系的技能与通用剧本仓库

> **状态：0.3.0（2026-10-22 同步 ADR-0137；同日加技能注册表与 doctor）。** 技能与协议已对齐项目仓现行机场体系
> （ADR-0137：四角色＋30 分钟塔台轮巡）；**本仓已于 2026-10-22 成为宿主装机正本**（`magpie-sync apply --root <本仓>`，
> 8 个宿主装齐 8 个技能），项目仓那份技能副本自此只作镜像。
> 旧五角色（Tower/Ground/Coordinator/Group-A/B）、租约、班次、handoff 按铃那套已随 ADR-0137 退役
> （git 历史可捞）。

## 这是什么

kai-mode 是「一句话需求 → 票 → 排班 → 施工 → 审查 → 发货 → 关票」的闭环框架。

**仓定位（2026-10-22 用户定口径）**：本仓**独立于任何项目仓** —— 不属任何项目仓，**不受项目仓的票、日表、审查与门禁约束**；它只放**跨项目通用**的部分（别的仓能直接拿去用的那种）。

- 技能清单：**以仓根 [`registry.json`](registry.json) 为准**（单一事实源；本文件不再手写名单）。两类：
  - **框架技能**（`kind: framework`）：框架本身的一部分，各项目都该有，默认 `install: auto` 进中央库；
  - **个人技能**（`kind: personal`）：只给自己用的，默认 `install: manual`，**不进中央库**。
- 协议正本：`loops/loop-protocol.md`（v5）
- 通用剧本：任务合同、执行三职、可靠性、审批、审计、上下文、验收
- 可执行契约：`task` / `acceptance` / `event` schema
- 宿主适配器：Qoder（30 分钟塔台定时＋按铃子会话）、opencode/codex 备胎
- 项目配置模板：`templates/kai-mode.project.json`

项目自己的 ADR、票、日报、门禁脚本与项目专用剧本留在项目仓。

## 角色（单责）

| 角色 | 口令 | 只负责 | 绝不做 |
|---|---|---|---|
| kai-mode 入口 | `/kai-mode` | 一句话需求 → 判断 → 拷问 → 定稿 → 拍板 → 路由 | 执行 |
| set-kai-mode 装配 | `/set-kai-mode` | 安装、探测、装定时器、doctor、缺件登记 | 日常施工 |
| 地勤 | `/地勤` | 对话、规划、开票（六件套＋`ready-for-agent`）、收想法 | 写码、push、派施工 |
| 塔台 | `/塔台` | 30 分钟轮巡：先排班（日表 5–10 行）、后发货（合并/push/关票） | 写码、替审查下结论 |
| 机长 / 副机长 | `/机长` `/副机长` | goal 模式各管 2 张票；每票 1 施工＋1 审查（新上下文）＋2 机动子代理 | 写码、push、合并 |

**权限硬线（ADR-0137）**：塔台**独占** push 与关票；机长/副机长只管理不写码；地勤只开票；记录面三分——日表只由塔台写、状态只写 Issue 评论、代码只进分支。

## 闭环

```text
用户一句话 → /kai-mode（拷问→定稿→拍一次板）
                    │
                    ▼
              地勤（开票：里程碑＋ready-for-agent＋AC＋禁区）
                    │  后备池 = 开放票
                    ▼
              塔台（先排班：写两张日表）
                    │
                    ▼
        机长 ──┬── 机长 ──┐   ← 主/副各 2 张在飞、6 子代理
        副机长 ┘          │
       （每票：施工子代理[独立 worktree] → 审查子代理[新上下文]）
                    │  verdict=pass ＋逐条 AC 证据 → 「待发货」
                    ▼
              塔台（再发货：批内合并 → 收尾门一次 → push 一次 → 关票）
                    │
                    └── 库存下降 → 下一轮补排班
```

记录面三分：**日表**（塔台写，排班视图）＋ **Issue 正文与评论**（唯一事实源）＋ **分支与提交**（代码与回执）。断点三件套 = 这三样，继任者按它续跑。

## 交接与断点（省叙述，不省证据）

- 票进入日表即完成领取；状态只由机长写 Issue 评论（开工/施工完成/审查完成/待发货/卡点）。
- 施工回执 ≤40 行：`ticket/role/verdict/files/commits/checks/summary/evidence/risks/next`；禁止贴 diff 全文与原始日志。
- 塔台发货**只认审查子代理的判词**（`verdict=pass` 且逐条 AC 有证据），不认机长口头总结。

## 可靠性（`playbooks/reliability.md`）

- 单票失败 **1 次重试**；再失败 → 卡点停票；同错连发触发熔断。
- 上限全部进项目配置 `limits`；到限写 `blocked`/`failed` 留读数，不许「再试一次看看」。
- 红线（花钱/对外真发布/不可逆改历史/删未提交内容）→ **只停那张票**，立即报人。

## 目录

```text
skills/           技能目录：一个技能一目录，必含 SKILL.md（清单见 registry.json）
skills/航班信息/   板工坊：SKILL.md ＋ templates/（生成器模板＋板配置样例）＋ scripts/（脚手架/索引页/刷新）
registry.json     技能注册表：技能清单的单一事实源（装机清单从它派生）
scripts/          仓级工具：doctor.py（校验入口，一条命令验全仓）
loops/            loop-protocol.md（v5 单票闭环正本）
playbooks/        task-contract / execution-roles / reliability / approval / audit / context / acceptance
schemas/          task / acceptance / event
adapters/         qoder（30 分钟塔台定时＋按铃子会话）、opencode、codex
templates/        kai-mode.project.json（schema 2：日表/轮巡/名额/限额/审批/审计）
templates/skill/  技能骨架模板（SKILL.md）：加新技能从这里复制
docs/             设计基线吸收记录（V1.0 对照与偏离，沿革）
docs/skill-layout.md  技能目录契约（目录 / frontmatter / 注册表字段 / 加技能三步 / 读契约）
CHANGELOG.md      版本变更记录
.gitattributes    行尾口径（仓内存 LF；.bat/.cmd 落 CRLF，防 cmd 崩）
```

## 接入一个新项目

1. 项目根写 `.ai/kai-mode.project.json`（从 `templates/` 复制），填主树解释器/node 绝对路径与门禁命令。
2. 把本仓 `skills/` 与 `loops/loop-protocol.md` 落到项目仓 `.ai/skills/` 与 `loops/`（或由 `set-kai-mode` 按宿主装配）。
3. `/set-kai-mode` 探测宿主能力（定时口 / 会话创建口 / shell 启动器），按四档装配 30 分钟塔台定时器；缺件如实登记。
4. 项目仓 ADR 记角色与权限裁决（先例：ADR-0137）；开票走地勤六件套；用一张真票走通「排班→施工→审查→发货」全链路做自证。
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

覆盖：注册表 schema / 字段 / 枚举、每个技能的目录与 `SKILL.md`、frontmatter 八字段与顺序、三处 name 一致、盘上有技能目录但没登记、`SKILL.md` 相对链接断链、机器绝对路径入正文、仓内行尾口径、`VERSION` 与本文件版本串一致、中央库副本与本仓是否逐字相同＋库记住的装机来源是不是本仓（第 13 项 `install-sync`；中央库定位不到时跳过），以及各技能自己的 pytest。

单独跑某个技能的测试：见该技能 `SKILL.md` 的「验证命令」段（如 `python -m pytest skills/航班信息/scripts/tests/ -q`）。

## 当前不做

- 不改项目仓的日表、Issue、门禁脚本——那些归项目仓与各角色。
- 不把项目专用路径、票号、job id 写进技能正文。
- 项目专用件（ADR、票、日报、门禁脚本、项目专用剧本）不进本仓。
- 个人技能默认 `install: manual`，不进中央库。
- 装机正本＝本仓（`registry.json` 的 `install:auto` 条目）；项目仓 `.ai/skills/` 只作镜像，不再是装机源（见 `MIGRATION.md`）。中央库记住装机来源（`<库根>/.kai-mode-source.json`）：从库里那份脚本跑，正本根也回到本仓，不会被 cwd 里的项目仓顶掉。⚠ 项目仓那份**旧** `magpie-sync.py` 若被再跑（它没有标记逻辑），仍会把中央库刷回项目仓版本 ⇒ 须与本仓对齐或停用。

## 判据正本

- 机场体系唯一现行裁决：项目仓 `docs/artifacts/adrs/ADR-0137-airport-rebuild-four-roles.md`（supersedes ADR-0131/0132/0133/0135/0136 的对应裁决，残留表在该 ADR §取代明细）
- 单句入口与拍板：项目仓 `docs/artifacts/adrs/ADR-0130-kai-mode-and-dual-lane-rewire.md`
- 单票闭环协议：本仓 `loops/loop-protocol.md`（v5）
- **技能清单与装机清单**：仓根 [`registry.json`](registry.json)（装机清单＝其中 `install: auto` 的条目）
- **技能目录契约**：[`docs/skill-layout.md`](docs/skill-layout.md)（目录结构 / frontmatter 八字段与顺序 / 注册表字段 / 读契约）
- 设计吸收沿革：`docs/design-v1-absorption.md`
