# 阶段判定与门点（v1）

> 依据设计 §3／§6。七个阶段是**职责**，不是流水线状态机；v1 只实现后三个纯文件阶段。

## 七阶段与门点

| 阶段 | 门点（能进下一步的条件） | v1 |
|---|---|---|
| `collect` | 覆盖看板给出样本缺口 → 产出找图任务表单 | 桩 |
| `ingest` | 指纹去重后每条素材有唯一 `asset_id` | 桩 |
| `annotate` | AI 候选带 `evidence_ref`，且未标 `locked` | 桩 |
| `validate` | **零 `block`** 才能进 evaluate；有 block 即 `blocked_reason` 非 null | ✅ |
| `review-assist` | 人工复核完成，`locked` 只由人给出 | 桩 |
| `evaluate` | 指标达 `round_manifest` 阈值（阈值**不在技能内**） | ✅ |
| `reflux` | 提案带审批结果，落 08.2／08.3，**不写 03.1／04.1／05.1／09.1** | ✅ |

## 判定口径（v1 实现）

- `validate`：任一 `findings[].level == "block"` ⇒ `blocked_reason` 填首个 block 的 code＋message；`counts.failed` 记被阻断记录数，`counts.needs_review` 记只有 warn 的记录数，`counts.processed` 记零 finding 的记录数。
- `evaluate`：`gold`／`pred` 键集不一致 ⇒ `E-002` block；样本为 0 ⇒ `E-001` warn 且不产出指标。
- `reflux`：只产提案，`artifacts` 里给提案的**内容摘要**（不写正本）；缺审批人 ⇒ `R-001` warn。

## 三条不许越的线

1. **「跑完」≠「通过」**：命令正常退出（exit 0）只表示跑完；是否通过看 `blocked_reason` 是否为 null。
2. **阈值不内置**：`--manifest` 未给时按「只报读数、不判达标」处理，并在人读段明说。
3. **不写正本**：任何阶段都不得写 03.1／04.1／05.1／09.1；reflux 默认只打印。
