# 子代理人格层：一源多投影 + 判据归属门禁

现状（2026-10 前）是「契约写在文档、机制一根没接」：`agents/README.md` 三处承诺 tier→模型解析住 adapters，三个 adapter 里 tier 表数量为 0；承诺 spawn 时传人格全文，实际传的是角色技能；`doctor.py` 零扫描 `agents/`，导致 7 份人格文件里的断句、指向已删目录的出处表、与 `ADR-0004` 漂移的档位映射全部一路全绿。同时 `skills/kai-mode/playbooks/` 七件与 `loops/loop-protocol.md` 长期并存两套口径（回执 25 行 vs 40 行、fail 3 轮 vs 1 次、租约/五角色等已退役机制）。

根因不是文件写错，是**没有任何机制保证「一条判据一个家」**：横幅注释不是退役机制，原则条文不是校验。

**决定：**

- **D1 一源多投影。** `agents/kai-*.md` 是唯一正本，绝不改成某家格式。宿主差异一律落 `adapters/<宿主>.json`（`tier_models`、`access`→权限落法、`spawn_deny`、`emit_to`、`format`），由 `scripts/agent-emit.py` 生成宿主原生 agent 文件，`--check` 报漂移。依据：同一件事六家六种写法（Claude Code `tools` 列表、OpenCode `permission` 对象、Codex `sandbox_mode`、Copilot `tools`、Cursor `tools`、san `mode`），单字段打不了天下；且 Claude Code 明确忽略不认识的字段，权限必须投影、不能靠"写了就管用"。
- **D2 判据归属 + canon 门禁。** 一类判据只住一个家，归属表正本＝`AGENTS.md`；机器判据正本＝`docs/canon.json`（退役词黑名单 ＋ 判据键唯一家），doctor 的 `canon-dup` 项执行。声明某词已退役的那一行用 `canon:allow-retired` 豁免。
- **D3 frontmatter 只用规范字段。** 顶层只许 `name`／`description`／`version`／`license`／`compatibility`／`metadata`（对齐 Agent Skills 开放标准）；自有语义 `role`／`access`／`tier`／`spawn`／`output` 一律进 `metadata` —— 那是规范规定的唯一合法扩展位。**不采纳** `allowed-tools`（实验字段、"预授权"语义，与"权限声明"不同）、不采纳 A2A Agent Card（跨网络进程发现协议，本层是同进程 spawn）、不采纳 OAF 的 `vendorKey/slug/tags`（仍是 draft）。也不采纳「description 写 PROACTIVELY/MUST BE USED」这类高压词：本仓已知病是过度派发，触发条件要写准而不是写响。
- **D4 六人格 + 单向依赖。** 撤销 `kai-archivist`，其能力降为 `kai-explorer` 的 `large-source` 模式（它是技巧不是性格，且依赖多数宿主没有的 1M 宽窗）；新增能力先加 `mode`，不加人格文件。项目层可指人格层，`agents/kai-*.md` **不许**反指 `loops/`、`docs/`、`skills/`，doctor 的 `agents-contract` 项强制。

**代价：** 多一层 `adapters/<宿主>.json` 与一个生成脚本；宿主格式演进时要改投影表而不是改 prompt。这是接受的：改一处投影表，六个人格同时生效；反过来（每份人格各写六份宿主体）会出现六份需要同步的副本。

**不做：** 不改 ADR-0003/0004/0005/0006（它们是正本，本身没病；六档词表 G/W "保留不派"的裁决照旧）；不给 `skills/` 施加「顶层只许标准字段」约束（现有八字段属仓内扩展，另案处理）。

## 演变注

- 2026-10-24：**D1 的「一源多投影」机制退役**——删 `adapters/<宿主>.json`、`scripts/agent-emit.py`
  与无校验器的 `agents/agents.schema.json`，宿主落法改为 [`adapters/README.md`](../../adapters/README.md)
  方法论（探测四步／六家对照／三级降级／缺件登记／装完自证）。依据：宿主会变，投影表是第二份要同步的副本；
  装机 agent 现场探测比抄表可靠。见 [0008](0008-persona-model-config-and-host-adaptation.md) D5。
- 2026-10-24：**D3 的 `metadata` 五字段收窄为只剩 `access`**（`role`／`tier`／`spawn`／`output` 全部删除），
  六人格改裸名（去 `kai-` 前缀）。见 0008 D1／D4。D2 的判据归属门禁与 D4 的单向依赖保留，门禁扩到 19 项（0.14.0 再加四项，共 23 项）。
