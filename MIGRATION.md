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

- 技能正本：`skills/<名>/SKILL.md`，一个技能一目录（ADR-0137 版）；**技能清单以仓根 `registry.json` 为准**（本文件不再手写名单）。
  其中航班信息（2026-10-22 新增：板生成器，单文件只用标准库）同日升级为板工坊（板配置＋脚手架＋模板；板库落在各项目仓 `.design/航班信息/HTML/`）。
  装机正本 `skills/set-kai-mode/scripts/magpie-sync.py`（2026-10-22 本仓副本加布局档；与项目仓正本待重新对齐同哈希）。
- **本仓自持技能注册表 `registry.json`**（schema `kai-mode-registry/1`）：技能清单的**单一事实源**；
  装机清单从它派生（取 `install: auto` 的条目），老根目录（没有 `registry.json` 的）回落内置清单。
- **仓级校验入口 `scripts/doctor.py`**：`python scripts/doctor.py [--root <仓根>] [--with-tests] [--json]`；
  一条命令验注册表 / 契约 / 链接 / 绝对路径 / 行尾 / 版本 / 测试。
- **0.4.0 新增两个面**：装配技能 `set-航班信息`（`skills/set-航班信息/`；给单个项目仓装一块板，
  默认不动中央库，`--install` 才装）＋ doctor 第 13 项 `install-sync`（中央库副本与本仓逐字对账、
  核对装机来源是不是本仓）。技能清单仍以仓根 `registry.json` 为准（现 9 条，装机清单 9 条待 `apply`）。
- 技能目录契约 `docs/skill-layout.md` ＋ 骨架模板 `templates/skill/SKILL.md`；版本变更记录 `CHANGELOG.md`。
- 单票闭环协议 v5：`loops/loop-protocol.md`。
- `adapters/` 三份按现役模型改写（塔台 30 分钟定时＋按铃子会话；opencode/codex 备胎与执行三职）。
- `templates/kai-mode.project.json` schema 2（日表/轮巡/名额 2×2/限额/审批/审计；去掉 shifts/activation/lease/token）。
- `README.md` 按四角色体系重写；`VERSION` 0.1.1 → 0.2.0（注册表 / doctor 这一轮升到 **0.3.0**）。
- 技能内 ADR 引用一律「项目仓 `docs/artifacts/adrs/` 正本，本仓只引用不复制」；项目专用路径（`kai-vass-v2/`、票号、job id）不进本仓。

## 仍在项目仓（**镜像，非装机正本**）

- **宿主装配已切到本仓**（2026-10-22）：`magpie-sync apply --root <本仓> --library <中央库>` ⇒ 8 个宿主（`.claude`／`.cline`／`.codex`／`.cursor`／`.dsh`／`.qoder-cn`／`.workbuddy`／`.workbuddy-ai`）装齐 8 个技能，新增 `航班信息`；`library.json` 追加 11 个平台条目；库里陈年 `__pycache__` 已清。装机正本＝本仓 `registry.json` 的 `install:auto` 条目。
- ⚠ **项目仓那份 `magpie-sync.py` 是同脚本的旧副本**（无装机来源标记逻辑）：它若被再跑，会把中央库刷回项目仓版本（7 个旧技能）—— 须与本仓对齐或停用（余下步骤第 5 条）。
- **中央库现在记住自己是从哪个仓装来的**：真 `apply` 会在库根写 `<库根>/.kai-mode-source.json`（记 `root`＝本次正本根）。**从中央库那份脚本跑**（宿主侧装机步就是跑它）时，正本根回到本仓，不会被 cwd 里的项目仓顶掉；标记缺失／损坏／那个仓没了 ⇒ 退回老路（跳过库根，按脚本位置／cwd 反查），不硬失败。
  ⇒ 但**项目仓那份旧脚本没有这段逻辑**：它被再跑仍会刷回项目仓版本（上面那条 ⚠ 依然成立）。
- 门禁与运行时脚本（`scripts/scope-check.py`、`loop-gate.py`、`ready.py`、`env-doctor.py`、`skill-attest.py` 等）在项目仓。
- ADR 正本（ADR-0130/0137 等）在项目仓；本仓只引用。

## 切换顺序（余下步骤）

1. **先自证**：在本仓跑 `python scripts/doctor.py --with-tests`，全绿（注册表 / 契约 / 链接 / 绝对路径 / 行尾 / 版本 / 测试）再动 root；
   然后两仓逐文件 SHA-256 对账，确认无行为差。
2. 项目仓用一张真票验证本仓技能与项目仓正本无行为差（逐文件 SHA-256 对账）。
3. 把 `magpie-sync.py` 的 root 指到本仓。**已做（2026-10-22）**：magpie-sync 加布局档，
   框架仓自身可作正本根；随后 `apply --root <本仓>` 实装，8 宿主装齐 8 技能（含新增 `航班信息`），
   `check` 三面全绿、注册档追加 11 个平台条目。
   原缺口（2026-10-22 实测）：脚本把项目仓布局写死（`FAMILIES` 八条全是 `.ai/skills/...` 相对路径，
   正本根按脚本位置上溯找 `.ai/skills` 锚），在本仓跑 `--selftest` 会报「正本根读不出」；现两种布局都认。
4. 项目 `.ai/kai-mode.project.json` 按 `templates/` schema 2 落地；项目剧本按本仓参考剧本改写（保留项目命令与路径）。
5. 试点一个轮巡周期后，项目仓 `.ai/skills/` 降级为镜像或移除；旧正本至少保留一个试点周期。

## 纪律

- **技能装机以本仓为准**（`registry.json` 派生，`install:auto` 才装）；**机场体系裁决仍以项目仓 ADR 为准**。
  本仓技能最初是从项目仓单向拷入的 staging，此后两仓不一致时，**装机面以本仓为准**、项目仓那份降为镜像；
  禁止在两处各改一份。
- 不在本仓写项目专用路径、票号、job id；它们属于项目配置与本机文件。
- 切换时先建新任务并自证，再停旧任务；旧 job id 至少保留一个试点周期。
- **加技能＝放目录 ＋ 注册表加一行 ＋ doctor 过**（`registry.json` 一行是唯一的清单登记面）；
  技能清单**不在 README / MIGRATION 手工枚举** —— 那会变成两处事实，加技能必漏。
