# 迁移状态（2026-10-22）

## 设计基线

- 机场体系唯一现行裁决＝项目仓 **ADR-0137**（四角色＋30 分钟塔台轮巡，2026-10-21 用户逐轮拍板）。
  它收编并部分取代 ADR-0131/0132/0133/0135/0136；残留表（哪些裁决保留/退役）见该 ADR「取代明细」一节。
- V1.0 吸收的**仍活**部分：任务合同/DoR/DoD、执行三职、可靠性（去 TTL/租约）、审批矩阵、审计、AI 全判不抽样
  ——落在本仓 `playbooks/` 与 `schemas/`，各文件头部有状态注。
- V1.0 吸收的**已退役**部分（11 态运行态、检查点文件、六阶段顺序、五角色、租约、班次、handoff 按铃）
  已从本仓删除（`loops.md`、`state-machine.md`、`playbooks/shifts/`、`handoff/status/queue/checkpoint` schema），
  git 历史（≤ `fdea9c9`）可捞。

## 本仓库已同步（2026-10-22）

- 七个技能正本（ADR-0137 版）：`skills/{kai-mode,set-kai-mode,loop,地勤,塔台,机长,副机长}/SKILL.md`
  ＋ `skills/set-kai-mode/scripts/magpie-sync.py`（与项目仓正本逐字节同哈希）。
- 单票闭环协议 v5：`loops/loop-protocol.md`。
- `adapters/` 三份按现役模型改写（塔台 30 分钟定时＋按铃子会话；opencode/codex 备胎与执行三职）。
- `templates/kai-mode.project.json` schema 2（日表/轮巡/名额 2×2/限额/审批/审计；去掉 shifts/activation/lease/token）。
- `README.md` 按四角色体系重写；`VERSION` 0.1.1 → 0.2.0。
- 技能内 ADR 引用一律「项目仓 `docs/artifacts/adrs/` 正本，本仓只引用不复制」；项目专用路径（`kai-vass-v2/`、票号、job id）不进本仓。

## 仍在项目仓（**直播源，未切换**）

- 宿主装配仍从项目仓 `.ai/skills/` 走 `magpie-sync.py`（root 未指到本仓）。
- 门禁与运行时脚本（`scripts/scope-check.py`、`loop-gate.py`、`ready.py`、`env-doctor.py`、`skill-attest.py` 等）在项目仓。
- ADR 正本（ADR-0130/0137 等）在项目仓；本仓只引用。

## 切换顺序（余下步骤）

1. 项目仓用一张真票验证本仓技能与项目仓正本无行为差（逐文件 SHA-256 对账）。
2. 把 `magpie-sync.py` 的 root 指到本仓。**缺口（2026-10-22 实测）**：脚本把项目仓布局写死
   （`MAGPIE_SKILLS` 七条全是 `.ai/skills/...` 相对路径，正本根按脚本位置上溯找 `.ai/skills` 锚），
   在本仓跑 `--selftest` 会报「正本根读不出」。切换时需给脚本加布局档（本仓 `skills/<名>`）
   或参数化 root，改完两仓脚本逐字节同哈希后再切。
3. 项目 `.ai/kai-mode.project.json` 按 `templates/` schema 2 落地；项目剧本按本仓参考剧本改写（保留项目命令与路径）。
4. 试点一个轮巡周期后，项目仓 `.ai/skills/` 降级为镜像或移除；旧正本至少保留一个试点周期。

## 纪律

- **切换前，项目仓副本是唯一直播源**；本仓同名文件只是 staging。本轮同步是**从项目仓单向拷入**；
  此后两仓不一致时，以项目仓正本为准、本仓重拷，禁止在两处各改一份。
- 不在本仓写项目专用路径、票号、job id；它们属于项目配置与本机文件。
- 切换时先建新任务并自证，再停旧任务；旧 job id 至少保留一个试点周期。
