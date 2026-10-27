# 0023 二副（第二副机长）车道：第四位机长，同权同流程

## Status

accepted —— 2026-10-27 用户令：「再开一个 二副（第二副机长）的角色，作为第四位机长，跟主副机长一样的权益、限制，排班表得加上他的，一样的设计规范，航班信息也得补上他的；issue 的标签除了 ace 也把其他三个机长的标签作为规范补上」。

## Context

- [0003](0003-airport-rebuild-four-roles.md) 把机长／副机长定为同一条 loop 的两条正常车道；[0020](0020-ace-pilot-expedited-lane.md) 增加的是**加急**车道，不能当正常产能用。
- 正常车道只有两条，日表是给机长的任务菜单；用户需要第三条正常机长道来并行推进，并要求它**不新增权限、不改流程**。
- 看板与 Issue 标签此前只认 `main`／`deputy`／`ace` 三条日表车道；新增车道必须同时进入排班、航班信息与标签规范，否则票会掉出可见面。

## Decision

### D1 岗位与车道标识

| 项 | 取值 |
|---|---|
| 技能 | `second-officer`（正本 `airport/skills/second-officer/SKILL.md`） |
| 口令 | `/second-officer`；中文别名「二副」「第二副机长」 |
| 车道 id | `second` |
| 日表 | 项目配置 `paths.day_tables_dir` ＋ `day_table_pattern` 展开的 `YYYY-MM-DD-second.md` |
| 工作树 | `lane-second` |
| 预检 | `--lane second` |

二副与副机长是**并列**关系，不是替补：各读各表、各算各的名额、各写各的票。

### D2 权益与限制完全同机长

不新增任何权限。围栏、自决、取舍裁决、等待梯、两态收尾、续跑指针、审查独立、单写手、红线与恢复顺序全部照机长技能；协议 §一 的 worker 预算按车道独立计——主、副、二副各 3 个，合计 9 个；王牌车道仍按自己的 1 张默认口径，不并入这 9 个。名额数值只住协议 §一，本 ADR 不另立第二份判据。

### D3 塔台排班：三张正常日表

- 塔台是 `-main.md` / `-deputy.md` / `-second.md` 的唯一写者；`-ace.md` 仍只由王牌写。
- 分配规则不变：先亲和（前置、同一交付链、同一文件域），均衡只在互不相关的票之间做；一张票只能进一张表；同一文件域不并列在飞。
- 三张表都按协议 §零 的行数区间补满；库存不足就留短并在日报写明，不凑数开票。
- 目标车道由标签显式指定时优先于亲和与均衡（D6）。

### D4 记录面与发货边界不变

- 日表只由塔台写；票状态只由 Issue 评论产生；代码只进分支。
- 塔台仍独占合并、push 与关票；二副不 push、不合并、不关票、不写产品代码。
- 角色之间不互相唤醒（[0010](0010-role-wake-fence.md)）；二副只由人工或宿主口令唤醒。

### D5 航班信息板补第四条车道

- 日表源默认包含 `*-second.md`。
- 车道顺序固定为 `main` → `deputy` → `second` → `ace`（书写顺序即页面左右顺序，主道优先）。
- `role_labels` 增 `second: "二副"`；加急区仍只认 `ace`。

### D6 Issue 车道标签成为规范

四条车道各有一个排队标签，字符串固定：

| 标签 | 车道 | 含义 |
|---|---|---|
| `main-queue` | main | 指定由机长道排班 |
| `deputy-queue` | deputy | 指定由副机长道排班 |
| `second-queue` | second | 指定由二副道排班 |
| `ace-queue` | ace | 王牌加急队列（不进塔台后备池） |

- 正本住 `docs/agents/triage-labels.md`；地勤是打标者，塔台只读标签、不改标签。
- 无车道标签＝按塔台正常后备池与亲和规则分配。
- `main-queue` / `deputy-queue` / `second-queue` 是**显式钉车道**：塔台必须把票排进对应车道，不得改排别道；若票已被排进另一张表，塔台删行并转入指定车道。
- `ace-queue` 语义不变：塔台排除，王牌按自己的车道消费。
- 标签不存在时由地勤按规范 create 一次，不在技能里各写一份字符串。

## Consequences

- 正常机长产能由两道变三道；主树合并点仍是塔台一处，push 权没有扩散。
- 塔台的排班与看板渲染要多维护一张表；三张表都补满时在飞票与 worker 用量上升，靠协议 §一 的触面互斥与 [0022](0022-touchset-based-inflight-cap.md) 的共享状态黑名单兜底。
- 三张表可能出现同一票候选冲突；「一张票只进一张表」与显式车道标签给出唯一解。
- 不新增任何自动唤醒；二副本停摆时与其他机长同样等塔台改日表，不互相接管。

## 验证

- `python scripts/doctor.py --with-tests` 全绿。
- 看板测试覆盖 `-second.md` 识别与车道顺序 `main/deputy/second/ace`。
- `airport/skills/loop/scripts/worktree.py`、`airport/skills/pilot/scripts/card.py`、`scripts/init-project.py` 的车道枚举都含 `second`。
- 仓库标签实际存在：`main-queue` / `deputy-queue` / `second-queue` / `ace-queue`。
- 活口文本里搜 `main|deputy` 的穷举处，不再漏 `second`。
