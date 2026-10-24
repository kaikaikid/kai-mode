---
slot: 10-session
type: handoff
ticket: "#1"
date: 2026-10-23
owner_role: 机长
persona: -
---

# kai-mode 重造工程交接文档

日期：2026-10-23 ｜ 交接自：kai-mode 重造会话（QwenWork） ｜ 接收：任何新会话/新 agent
工程主文档：`handoff/20-plan/2026-10/2026-10-23-kai-mode-rebuild-plan.md`（方案槽，含全部决策与验收口径）

---

## 一句话现状

重造主线 **Phase 0–4 已完成并提交（7 笔）**；工作区剩一批 **他人/他会话的航班信息在制件（勿动）**；未完：外部 skill 纳管、板工坊泛化、#1 票执行方式裁定、Phase 5 双仓回归。doctor 14 项中 2 红均由在制件引起，收口后自愈。

## 一、工程目标与总口径（接手人必须先懂这个）

- **pstack 全部保留、原样当规范蓝本**（`../pstack`，相对仓根，本地 clone，零改动）。
- **重造对象是 kai-mode**：按 pstack 的结构规范重打造——判据正本归位、skills/agents 模板化、set-kai-mode 初始化适配项目、与项目仓解耦。
- 解耦三层模型：**框架正本层**（判据/流程，零项目痕迹）／**项目差异层**（唯一事实源＝目标项目仓 `.ai/kai-mode.project.json`，schema 3）／**宿主适配层**（adapters/ 三家）。

## 二、已拍板决策（除非开哥重新拍板，不得推翻）

| # | 决策 | 裁定 |
|---|---|---|
| 1 | 判据迁入 | 重述迁入本仓 ADR-0002/0003；项目仓侧只加「已迁出」注记且走该仓流程，**不代改** |
| 2 | 剧本登记面 | 收进配置实例 `registry.playbooks[]`，项目仓 router.md 退役 |
| 3 | schema 兼容 | schema 2 双仓回归通过后**即废**，不留只读降级 |
| 4 | host_tools | 归 adapters/（宿主差异），实例内清空 |
| 5 | 六档映射 | 代码 C／判断 V／评审团 V 轮换／验证 C fast／守望 R／编排 P；**词表只有 R/C/P/V/G/W，永不写模型 slug**（doctor 解耦门拦） |
| 6 | agents 层 | 只留**一份泛用设定**（agents/ 八件，宿主中立，装机时 AI 自适配）；子代理日常管理归 magpie |
| 7 | 原则层 | 6 条照抽（判据搬家、流程留指针） |
| 8 | 航班信息 | 留模板、**用户自选看板**；泛化针暂缓（见待办 2） |
| 9 | 等待与止损 | 三层机制（ADR-0005）：增量提交最优先 |
| 10 | 塔台令牌 | 拿令牌才是塔台（ADR-0006）；**现阶段机长/副机长不得唤塔**，拉起方＝人工口令/kai-mode 入口/30 分钟定时器，三路靠令牌互斥 |

## 三、提交史（本工程 7 笔，均已本地提交未 push）

| commit | 内容 |
|---|---|
| `f09e8b1` | Phase 0 判据迁入：ADR-0002/0003 重述接管、24 文件指针翻转、矛盾行清理 |
| `5a80a12` | Phase 1 配置面：schema 3 转正、16 文件硬路径清零、host_tools 迁 adapters、doctor 解耦门 |
| `ad34049` | Phase 2 结构对齐：playbooks 七件入路由技能、agents/ 泛用层八件、contracts 特化版退役 |
| `a4d3a1f` | Phase 3 原则层：principle-* 六条，registry 15 条 |
| `75a12c0` | Phase 4 初始化器：档位核对、生成式腿（验证技能骨架模板）、schema 2→3 迁移腿 |
| `2bb0484` | 等待与止损：ADR-0005＋loop-protocol §八等待纪律/§九增量提交＋机长副机长硬清单＋派工卡第 8 项 |
| `be8b313` | 塔台令牌：ADR-0006＋塔台「0. 抢令牌」步＋权限矩阵收紧 |

## 四、当前架构速览

```
kai-mode/
├── AGENTS.md · registry.json(15 条) · handoff/（交接文档槽，本件在 10-session/）
├── docs/adr/0001 独立仓 · 0002 入口拷问定稿 · 0003 四角色机场
│           0004 配置面 schema3 · 0005 等待止损 · 0006 塔台令牌   ← 判据正本，一字不许外引
├── skills/  kai-mode(入口+playbooks 七件) · set-kai-mode(初始化器 v4.3)
│           地勤/塔台/机长/副机长/loop · principle-*×6 · 航班信息/set-航班信息(在制)
├── agents/  README 契约 + 七人格件（explorer/librarian=R worker=C planner=P
│           reviewer=V visual-designer=G archivist=W；宿主中立，装机自适配）
├── adapters/ codex · qoder · opencode（宿主工具探测段）
├── templates/ kai-mode.project.json(schema 3 正式模板) · skill 骨架
├── loops/loop-protocol.md（单票闭环协议正本，含 §八等待纪律 §九增量提交）
├── subagents/codex/  scripts 工具（measure/check-tiers）；contracts 已退役 _superseded/
└── scripts/doctor.py  ← 14 项机检门，含 decoupling-gate 解耦门
```

## 五、运行态铁律（接手人逐条背下来）

1. **跨仓治理边界**：绝不往 Kai-vass-Control 等项目仓开票/关票/写 issue。跨仓事务只向开哥交底，由他或那边角色（地勤开票/塔台关票）走。*本会话曾误开 Kai-vass#1886 已被纠正关闭。*
2. **在制件勿代提交**：工作区现有 `skills/航班信息`＋`skills/set-航班信息` 的 board-types 重构（8 改动文件＋未跟踪 `templates/board-types/`）＝**他人/他会话的活**：不动、不提交、不回滚、不裹进任何提交。doctor 的 2 红（broken-link 指向已删的 board.config.example.json、install-sync 库内多出该件）由它引起，它收口提交后自愈。
3. **一个语义一个家**：判据住 ADR/协议/原则叶子正本，别处只留指针；改判据先问「第一条住哪」。docs/adr/0001–0006 与 loop-protocol 的判据正文一字不许动（演变用「演变注」，见 0003 范例）。
4. **机制类改动先设计后落地**：先出 ADR（accepted 才生效）→开哥拍板→才动执行面。写进 ADR 不算落地。
5. **中央库回写**：改任何 SKILL.md 后 doctor 的 install-sync 会红；跑 `python skills/set-kai-mode/scripts/magpie-sync.py apply --root "D:\kaikaikid\tools\kai-mode" --library "D:\kaikaikid\tools\magpie\data\library\skills"` 后复跑 doctor 至绿（apply 后隔 ≥90s 再 check）。<!-- # doctor:allow-machine-path：命令行参数，不是路径引用 -->
6. **配置纪律**：技能运行时只读 `<项目仓根>/.ai/kai-mode.project.json`（仓库根探测），读不到 rc≠0 输出三格缺件清单（缺什么/谁需要/怎么补），**永不猜路径、永不退回硬路径**。
7. **提交纪律**：精确 `git add <文件清单>`，**禁止 `git add -A` 全仓**（会裹挟在制件）；一次语义一笔提交；本工程节奏＝每刀一提交，message 写清判据来源。
8. **装机集合**：registry 里 `install: auto` 的 15 条走中央库；agents/ 不进 registry（doctor 不扫 agents/，自查口径见 skill-layout §9）。

## 六、验证入口（一条命令验全仓）

```bash
python scripts/doctor.py --with-tests      # 14 项：registry/frontmatter/链接/解耦门/install-sync/pytest
python skills/set-kai-mode/scripts/magpie-sync.py check   # 正本↔中央库↔宿主 三面漂移表
```

当前读数：14 项中 11 绿 2 红 1 跳过——**两红全挂在航班信息在制件上**，接手人先确认该在制件归属与收口节奏，再谈全绿。

## 七、待办（按优先级）

1. **针G 外部 skill 纳管**（开哥口径已给，未细化未派）：把外部技能（automate-me、tdd 等）纳入本仓管理——registry 增 `kind: external` 类别＋**源头指针**（保留上游仓库地址，方便升级同步）；机场体系定位＝**编程模块剧本**。automate-me 在 pstack 仓有现成件（`skills/automate-me/SKILL.md`）可作首个引入样例；tdd 源头需侦察（QwenWork 技能库现挂版本）。
2. **板工坊泛化**（暂缓中）：等航班信息在制件收口后重派，口径＝「留模板，由用户自选看板」（方案要点：板型模板目录化 board-types/、set-航班信息 加板型选择步、不改技能名）。
3. **本仓 #1 票**（needs-triage）：Kai-vass ADR-0130/0137 迁出注记＋0132/0133/0135/0136/0140/0141 盘点——**跨仓活，执行方式待开哥裁定**（亲自改/授权那边会话/授权本仓代理），未裁定不动。
4. **Phase 5 双仓回归**：Kai-vass 腿（要写那边 `.ai/` 配置实例，**需开哥授权**）＋干净仓腿（可自建临时仓跑 set-kai-mode 全链路）；双仓回归通过后废 schema 2 读法（决策 #3 生效条件）。
5. **push**：7 笔提交均未 push（kai-mode 远端 kaikaikid/kai-mode，是否 push 由开哥定）。

## 八、历史背景（为什么会有这工程）

pstack（backnotprop/pstack，Cursor 工程纪律 skill 集，56 skills，poteto-mode 路由）→ 开哥决定全部保留当蓝本，把 kai-mode 按 pstack 规范重造。已完成 pstack 真机盘点与分层能力分析（结论沉淀在重造方案文档）；pstack 本体零改动。更早的机场体系沿革看 docs/adr/0002/0003 的「出处与迁移」段与 MIGRATION.md。
