# 运行输出契约（v1）

> 正本依据：`C-flywheel-skill-design.md` §4。三个 v1 子命令**必须吐同一形状**。

## JSON 形状

```json
{
  "run_id": "dna-20261114-001",
  "stage": "validate",
  "round_id": "round-001",
  "inputs": {
    "ontology_version": "3.9",
    "record_schema_version": "1.2",
    "criteria_version": "04.1@2026-11-14",
    "prompt_version": "06.1@forbidden",
    "skill_version": "dna-flywheel@0.1.0",
    "pipeline_version": "n/a"
  },
  "counts": {
    "added": 0,
    "processed": 0,
    "skipped": 0,
    "duplicate_candidates": 0,
    "failed": 0,
    "needs_review": 0
  },
  "findings": [
    {
      "code": "V-003",
      "level": "block",
      "asset_id": "asset_xxx",
      "subfield": "technique",
      "message": "引用了 retired allele_id: technique-005",
      "evidence_ref": "03.1#technique-005"
    }
  ],
  "artifacts": [],
  "blocked_reason": null
}
```

## 硬规则

1. `counts` **六个数必须有**，缺项写 `0`，**不写 null**。
2. `findings` 每条**必须带 `code`**（稳定编号）与 `evidence_ref`（能回溯到正本位置）。
3. `stage` 只用七个枚举值：`collect / ingest / annotate / validate / review-assist / evaluate / reflux`，不用自由文本。
4. 人读段落**只复述** `inputs` / `counts` / `findings` 三个块，不另加判断。
5. `blocked_reason` 非 null ⇒ 该轮**不通过**；「跑完」不等于「通过」。

## 稳定编号（v1 已用）

| code | level | 含义 |
|---|---|---|
| `V-001` | block | `allele_id` 在本体中不存在 |
| `V-002` | warn | `subfield_key` 与所属基因座不一致 |
| `V-003` | block | 引用了 **retired** `allele_id` |
| `V-004` | block | 记录缺 `asset_id`（违反「只存 asset_id 引用」） |
| `V-005` | warn | 记录引用了结果标签（`result_labels`）当基因位 |
| `E-001` | warn | 评估样本数为 0，指标不可算 |
| `E-002` | block | gold 与 pred 的样本键集不一致 |
| `R-001` | warn | 回流提案缺审批人，按「待批」输出 |

新增编号只追加、不复用旧号。
