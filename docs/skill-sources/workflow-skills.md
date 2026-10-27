# workflow-skills —— 工作流技能素材（打包摘要）

> 一次引入的一批：主体来自同一上游（mattpocock/skills），另有一个安全专项（cloudflare/security-audit-skill），共用一个对账节奏，合成一份摘要省重复。
> 索引正本：`sources.json`（机器读）；本文件给人与 AI 读，**不是任何技能的正本**。

## 1. 收录口径：三种处置，只有一种算特化

| 状态 | 含义 | 本批 |
|---|---|---|
| `adopted` | **本仓自己设计的**东西 → 特化入 `skills/kai-*`，加前缀 | 1 个：boom-idea-log |
| `vendored` | 通用方法 → **原样拉取**到 `vendor/skills/`，不改内容不改名不登记 | 7 个：tdd／code-review／diagnosing-bugs／domain-modeling／to-tickets／writing-for-agents／security-audit |
| `watching` | 有价值但不适用，先观察上游 | 2 个：prototype／pr |
| `dropped` | 判定不引，理由在 `sources.json` 的 `reason` | 3 个：research／implement／grilling |

## 2. 什么才叫「特化」（fork 判据）

三个条件**全中**才许 fork：

1. **是我们设计的**：判据由本仓 ADR／流程／角色决定，上游没有（如想法池落点、handoff frontmatter、票面六件套）。
2. **有本仓接口**：必须接派工卡／回执／判词／门禁其中至少一个，否则只是抄一遍。
3. **不 fork 就没有家**：找不到现成正本承载它。

只改措辞、加一段「用的时候注意配合本仓」＝**假特化**，不许 fork。
通用方法（TDD、双轴审查、诊断法、术语建模、拆票法、写作法）都属此类：**方法与流程各有一个家——方法是上游技能，流程是本仓 `loops/` 与角色技能。**

**为什么不能 fork 通用件**：中央库已有同名通用件，fork 要么加前缀造出第二份同义判据，要么 `magpie-sync apply` 覆盖通用件、让非本项目场景失效。两条都坏。

## 3. 唯一特化的一个

### boom-idea-log → skills/kai-boom-idea-log

- **为什么是我们设计的**：落点、汇总面、发布动作由本仓角色分工决定（地勤只收不开票、全文进 `paths.ideas_dir`、汇总票只留简述），上游那份写死了单项目票号与目录。
- **本仓接口**：接 `skills/ground-crew/SKILL.md`「工作流 · 分流」第 3 步，输出回链 ground-crew 的记账表。
- 继承：本地全文正本 + 远端仅简述、查重、编号只增不减、`gh --body-file`、只暂存目标文件、毕业回写。
- 改：写死的票号与目录 → 项目配置 `paths.ideas_dir` ＋ 汇总票号；缺配置报缺件（`ADR-0004` D4）；补完成判据与失败降级。

## 4. 原样拉取的七个（vendored）

用法：**直接用 `vendor/skills/` 里那份原文**（`python scripts/vendor-sync.py` 刷新、`--check` 校验）。
本仓只在流程位写清「什么时候用它、产出交给谁」。

| 外部技能 | 用在工作流的哪一步 | 本仓承载「流程」的那一份（不复制方法） |
|---|---|---|
| `vendor/skills/tdd` | 施工：先红后绿 | `airport/skills/loop/references/loop-protocol.md` §三.3／§九（接缝＝票面验证命令、一测例一提交） |
| `vendor/skills/code-review` | 审查：双轴出判词 | 同文件 §四（机器门／语义门、判词四要素） |
| `vendor/skills/diagnosing-bugs` | 连续失败／原因不明 | 同文件 §七／§八（卡点、止损、等待纪律） |
| `vendor/skills/domain-modeling` | 定稿第 2 步：术语与 ADR | `skills/kai-mode/SKILL.md` 定稿段 ＋ `docs/adr/` |
| `vendor/skills/to-tickets` | 定稿第 3 步：拆票草案 | `skills/kai-mode/SKILL.md` 定稿段 ＋ `skills/ground-crew/SKILL.md` 票面六件套 |
| `vendor/skills/writing-for-agents` | 写 SKILL／AGENTS 文档 | `docs/skill-layout.md`（八字段、<500 行）＋ `scripts/doctor.py` |
| `vendor/skills/security-audit` | 审查：安全专项（六阶段漏洞猎取） | `airport/skills/loop/references/dispatch.md` 的 安全专项 ＋ `airport/skills/loop/references/dispatch.md` §2／§3 |

`vendor/skills/security-audit` 额外三条（与其他六个不同）：
上游 `cloudflare/security-audit-skill`（MIT，`LICENSE` 随件），**需要 node**（两个零依赖校验器）与**OS 沙箱**（真跑目标代码）；
无沙箱时按上游规定只做静态复核，结论最高 `needs_validation`。它是**父级编排**型技能：六阶段由派活方驱动，不为它新增人格。

`vendor/` 里的文件**一个字都不改**：`--check` 会报与源不一致，下次 sync 直接覆盖。要改行为就改上表右列。

## 5. 观察中的两个（watching）

| 源 | 为什么先不用 |
|---|---|
| `prototype` | 定稿阶段验可行性有价值，但带 `LOGIC.md` / `UI.md` 两份资产；等有真实需求再评估 |
| `pr` | 本仓塔台直推 `dev`、不走 PR；170 行里大半是 PR 描述与评审流程，暂不适用 |

## 6. 不引的三个（dropped）

| 源 | 理由 |
|---|---|
| `research` | 全文只有「起后台代理、查一手来源、落一份 md」；`agents/librarian.md` 已承载同一纪律 |
| `implement` | 15 行薄壳，内容＝按票实现→tdd→code-review；`airport/skills/loop/references/loop-protocol.md` §二 已写死同样顺序 |
| `grilling` | 「一次一问逐个确认」判据正本已是 `skills/principle-ask-one-question-at-a-time/` |

## 7. 对账（30 天一次）

```bash
python scripts/source-check.py                       # 全部素材
python scripts/source-check.py --id tdd-mattpocock   # 单个
```

对账四步：

1. 指纹变了 → 读上游 diff，判断是否影响**我们引用它的那个流程位**；
2. 影响 → 改本仓承载流程的那一份（§4 表右列），**不 fork 上游方法**；
3. 改完跑 `python scripts/doctor.py` 至绿；
4. 更新 `sources.json` 的 `sha256` / `last_diff` / `next_diff_due`。

**注意**：`referenced` 条目没有本仓副本，指纹只验「上游有没有变」，不做内容对齐。

## 8. 加一个新素材

按 `docs/skill-sources/README.md` §5；先回答 §2 三问——不满足就记 `referenced` 或 `watching`，别 fork。
同批同上游的可续写在本文件（新增一节 ＋ `sources.json` 一条，`note` 写本文件 `#<锚点>`）。
