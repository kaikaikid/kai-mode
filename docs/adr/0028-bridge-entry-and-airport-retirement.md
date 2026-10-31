# 0028 舰桥成为唯一入口，机场体系整体下线

## Status

**accepted** —— 2026-10-31 用户拍板「我只跟 Bridge｜舰桥 交谈，取代 /coding；舰桥权限最高，能处理脏文件；
忘了触发就默认舰桥；舰桥可触发 /jump 开工」，并明确「起码砍掉 V1 的工程模块，机场体系下线」。
框架侧同日落地；宿主安装面随后同步。

## Context

- **用户不会走流程**：V1 的票、日表、车道、哨兵、塔台定时器对用户是不可见内部件；用户只想要一个能听懂话、
  能把发货杂活干完的对话面。
- **V2 已有执行内核**：一个 issue 一个 run、任务图、worktree、门卫审查、G2 发货都已脚本化；
  缺的是「人话入口」与「脏文件处置」。
- **V1 与 V2 并存会抢同一个出口**：塔台定时器会在 run 在飞时合并/push，V2 的 G2 也会发货；
  两套记录面（日表 vs state.json）互相不认识。
- **脏文件是实际卡点**：V2 发货要求主树无已跟踪改动，而用户的项目主树经常有未提交件。

## Decision

### D1 唯一入口：`bridge`

- 新增 `core/skills/bridge/SKILL.md`，中文名「舰桥」，口令 `/bridge`、`/舰桥`。
- 用户没显式点名其它技能、也没打斜杠命令时，**默认进入舰桥**。
  机械落点：项目 `CLAUDE.md` / `AGENTS.md` 的「默认入口＝舰桥」段（由 `set-kai-mode` 第 3 步写入）。
- 舰桥是唯一对话面与发货口；权限最高，但仍受四条红线约束（花钱 / 对外真发布 / 不可逆 / 删未提交内容）。

### D2 `/coding` 降为内核控制面，`/jump` 由舰桥触发

- `v2/skills/coding/SKILL.md` 不再是用户入口；`coding` 命令只做状态推进、派工、验收、发货。
- 用户说「开工 / 做吧 / 继续」或打 `/jump` 时，舰桥执行 `coding jump <任务>`；
  加急用 `coding PRI-jump`。自动批 G0/G1/G2，只在红线、异常、可见 UI 取舍时停。

### D3 脏文件：可逆处置，绝不删除

- 新增 `coding dirty [--json]`：把主树脏件分成 **record**（`.coding/`、`.ai/`、`handoff/`、日志/DB/缓存）
  与 **product**；只有 product 阻塞发货。
- 新增 `coding park [-m 理由]`：把无关 product 改动收进命名 stash，回执落 `.coding/parked/<时间>.json`
  （stash ref ＋ 恢复命令）；`coding unpark [ref]` 放回（apply，不 drop）。
- 禁止：`git checkout --`、`git restore`、`git clean`、`git stash drop`、强推。
- 若脏件就是本次任务本身，用 `coding adopt <issue>` 接管为 baseline，而不是收起。

### D4 机场体系下线

- 删除 `airport/` 插件（commands、六岗位技能、loop 协议、塔台脚本、日表/车道/令牌/定时器）。
- `pk` 不属于机场角色，迁到 `methods/skills/pk`。
- 配置实例升 **schema 5**，删除：`ship_mode`、`paths.day_tables_dir`、`paths.day_table_pattern`、
  `paths.lanes`、`tower_cron`、`issue.verdict_marker`、`registry.skills.loop_dir`、
  `gates.captain_preflight`、`gates.scope_check`、`gates.close_gate`；新增 `gates.finish_cmd`。
- `marketplace.json` 删 `airport` 插件；`install-profiles.json` 的 core/full 重排；
  `canon.json` 删以 airport 为正本的判据键；doctor 的 airport 扫描面一并清退。
- 宿主安装面：V1 技能移到中央库 `.retired/<时间>/` 并摘掉各宿主符号链接；不再安装任何唤醒定时器。

## Consequences

- **好**：用户只有一个对话面；发货不再需要理解票与排班；脏文件有机械、可逆的处置；
  V1/V2 抢出口的问题消失；配置面少 10 个键。
- **代价**：V1 的成熟判据（判词形状、机器门、热修门槛、merge-tree 预演、自动推送三条件）随插件删除；
  已把仍适用的部分写进 `bridge` 与 `v2/skills/coding`，其余留在 git 历史与 ADR。
- **迁移**：已装 V1 的宿主按 `set-kai-mode` 第 2 步 `--retire` 清单处理；项目配置实例按 schema 5 迁移腿逐键 diff。
- **不做**：不恢复日表/车道/塔台定时器；不保留 V1 命令别名（用户只需要舰桥）。
