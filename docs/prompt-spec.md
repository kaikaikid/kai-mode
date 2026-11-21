# 角色提示词分层规范（常驻层 token 预算）

> 开票：2026-11-21 团长拍板。背景：主 AI 常驻层实测 17,317 字符 ≈ 5,111 tok，
> 逐星团长手写卡仅 3,105 字符 ≈ 1,100 tok——差距主要来自 canon 内联复述
> 「唯一家」已管辖的语义（信封规格／总结体例／输出契约三大段）。
> 唯一家：本文件。canon／README 不复述，只引用。

## 1. 分层内联清单

常驻层（指纹行以下的渲染正文）分三层，逐层定内联纪律：

**必须内联**（人格与当场可执行的最小集）：

- `identity`／`personality`（皮肤逐字，人格本体不指针化——`roles/README.md` 已裁决）；
- 职责四块：mission／boundaries／workflow 核心步骤／本角色专有判据表（如拍板权表）；
- 红线与停止条件（一句话级，展开版留指针）；
- 总结槽位词（渲染器从 `roles/summary-slots.json` 前置，角色不手写）；
- 栏头 shorthand：≤3 行的输出约束锚点（如「四段／信封／证据／状态词」）。

**必须外置指针**（细则一个家，常驻层只留名字）：

- 字段表、原因码表、状态机全文 → `docs/schema.md`；
- 信封逐字规格、总结体例红线 → `roles/envelope-header.md`、`roles/summary-convention.md`
  （渲染器逐字前置，正文不得二次展开）；
- 模板全文、样例、历史沿革、ADR 论证 → 对应 docs/adr、模板文件；
- 宿主专有机制（开话题／清场／routine）→ `adapters/`。

**禁止内联**（写了就是违规，验收打回）：

- 复述「唯一家」已管辖的语义——同一句判据在常驻层出现两次即违规，哪怕措辞不同；
- 字段表逐条抄写、原因码逐条罗列、模板整段粘贴；
- 为「以防模型忘了」而加的重复提醒——靠 shorthand 锚点，不靠复读。

渲染器前置块（输入契约／信封／载体路由／总结体例／槽位词）是** sanctioned 内联**，
不计入「复述」违规；canon body 与手写区不得再复述它们的内容。

## 2. token 预算档

按常驻层每次会话全量进上下文计。档位可按实测微调，调整要写依据。

| 档 | 适用 | 预算 | 依据 |
|---|---|---|---|
| A | 主 AI／团长对话面（每轮常驻，承载调度） | ≤3k tok | 现状 5,111 tok 超标 65%；逐星手写卡 1,100 tok 证明 1/5 体量可承载同构职责；3k 留出人格＋调度表余量 |
| B | 常驻可派发角色（agent 目录渲染件） | ≤1.5k tok | 角色只吃任务包，不需要调度表与汇报梯；现七份渲染件 3–4k chars，天然在档内 |
| C | 声明性层（手写卡、profile 按需层、depth） | ≤300 tok | 按需加载，常驻仅一行指针；逐星卡实测 3,105 字符≈1,100 tok 是 A 档下限参照 |

测算口径：中文按 ≈1 tok/char 估、英文按 ≈4 chars/tok 估，混合取 0.5–0.3 tok/char；
验收一律报**字符数**（可复现），token 数标注估算口径。

## 3. 指针格式

指针必须「一个家＋可定位」，三种合法形态：

1. 文件级：`roles/summary-convention.md`；
2. 锚级：`docs/schema.md` 的「BLOCKED 原因码」节（标题锚，不用行号——行号漂移）；
3. 渲染前置：写「渲染器已前置，不复述」（envelope／routing／convention／slots 四块专用）。

禁止：裸文件名不带角色语境、行号锚、相对路径出仓、指向已退役文件。

## 4. 新建角色 checklist

- [ ] canon body ≤ A 档预算（主 AI）或 B 档预算（可派发）；
- [ ] 四块齐：mission／boundaries／workflow／output_contract（output_contract 只写
      本角色专有约定＋栏头 shorthand，不复述信封/总结/路由）；
- [ ] 皮肤 identity／personality 双皮同步，identity_core 与 guild 逐字一致；
- [ ] summary-slots.json 有本角色槽位词（七键齐）；
- [ ] depth 块（可选）≤8KB，不内联进常驻层；
- [ ] registry 重导出＋doctor 全绿＋落点重渲；
- [ ] grep 自检：canon body 不含 envelope-header.md／summary-convention.md 的标志句
      （如「信封头三行」「三槽固定顺序」）。
