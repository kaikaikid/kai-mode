# 卸载 V1（下线腿）

> 旧体系已整体下线（裁决记在框架仓 ADR 目录）；本腿把宿主安装面上的 V1 残留清干净。
> 判据住脚本、不住正文：`scripts/uninstall-v1.py`；本节只写流程位与验收。

**什么时候走**：缺口扫描第 10 项探到 V1 残留；或用户明确说「卸载 V1」。

**四步（探 → 退 → 核 → 回执）**：

```bash
S=core/skills/set-kai-mode/scripts/uninstall-v1.py
python $S --repo <项目仓>          # ① 只读探测：七个 V1 技能 × 库/注册档/宿主链接/实体目录，外加定时任务与项目实例残留
python $S --apply                  # ② 退役（用户点头后才跑）：写前整包备份 → 库目录移 .retired → 摘宿主链接 → 清注册档
python $S --repo <项目仓>          # ③ 复核：应为全「—」；有残留按缺件三格登记
python $S --json                   # ④ 机器读（探测或 --apply 的回执）
```

**脚本做**：备份中央库；把 `ace`/`copilot`/`ground-crew`/`loop`/`pilot`/`second-officer`/`tower` 的
库目录移进 `<库根>/.retired/<时间>/`、摘掉各宿主指向它们的符号链接、从 `library.json` 的
`skills[]` 与 `applied[*].skills` 删条目；产出回执 JSON。

**脚本不做（要人拍，回执里逐条列）**：

- 宿主落点里的**实体目录**（非符号链接的拷贝，如 `.codex/skills`）——只报告；要清就整目录移进备份位，不删。
- 宿主定时任务／automation——只报告；停用或移走由用户执行。 <!-- canon:allow-retired -->
- 项目配置实例的 V1 键（`ship_mode`、`day_tables*`、`lanes`、`tower_cron`、三键门禁）——只报告； <!-- canon:allow-retired -->
  迁移走「配置实例」节的 schema 迁移腿，逐键 diff，不静默删字段。

**验收**：① 复核全「—」；② 回执里有 `retired` 清单与备份路径；③ 残留项（实体目录／定时任务／实例键）
逐条写进缺件登记，不许写成「已清零」。
