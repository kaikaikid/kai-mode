# 幂等与缓存键（v1）

> 依据设计 §5（08.1 §24.1）。v1 不落缓存库，只**计算并打印**缓存键；命中判定由调用方传入 `--cache-index` 完成。

## 缓存键组成

```
sha256(image) + subfield_set + ontology_version + criteria_version
+ record_schema_version + model_id + model_revision + prompt_hash
+ skill_version + pipeline_version
```

v1 实现取可获得的字段拼接后取 sha256：

```
key = sha256("|".join([
  image_sha256,            # 必填；缺则用 asset_id 代替并 warn
  ",".join(sorted(subfield_set)),
  ontology_version,
  criteria_version,
  record_schema_version,
  model_id,
  model_revision,
  prompt_hash,
  skill_version,
  pipeline_version,
]))
```

## 三条硬规矩

1. **同键命中输出 `skipped` 而非 `processed`**，且必须**打印键的组成**（每个字段原值），让人能解释为什么跳过。
2. **重试生成新的 `extraction_run`**，不覆盖旧运行（v1 只体现在 `run_id` 每次新生成，不写历史）。
3. **改名／移动不触发重跑**；只有**内容**（`image_sha256`）变化才变键。

## v1 边界

- 不建缓存表、不写缓存文件：`--cache-index` 是一个可选的 JSON（`{key: run_id}`），只读。
- 缺 `image_sha256` 时用 `asset_id` 兜底并在 `findings` 里记 `C-001` warn（见 run-contract 编号表；v1 若未用到可不产生）。
