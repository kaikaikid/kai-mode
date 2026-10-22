> 状态（2026-10-22 同步）：按项目仓 ADR-0137 残留表保留；文中租约/班次/按铃/五角色等已退役机制以 ADR-0137 为准（日表＋Issue＋分支三件记录面、塔台独占 push）。

# 任务合同与 Definition of Ready / Done

> 一张票只有在**合同完整**时才允许进入 `ready`。合同住 GitHub Issue 正文；运行态只存票号与合同哈希，不复制正文。
> 目的：让一个没有聊天上下文的新执行器，只看票面就能确定“做什么、能改哪、怎么算过、什么时候停”。

## 一、合同十字段（缺一不可）

| # | 字段 | 要求 | 反例 |
|---|---|---|---|
| 1 | 目标 | 一句话说清要改变什么；不写实现方案 | “优化一下” |
| 2 | 验收标准 | 逐条可判，每条有证据形态 | “体验更好” |
| 3 | 允许修改范围 | 逐枚文件或目录；不用整片“后端/前端” | `backend/**` |
| 4 | 禁止修改范围 | 明确不能碰的文件/目录 | 省略 |
| 5 | 前置依赖 | 票号/外部条件；没有写“无” | 留空 |
| 6 | 验证命令 | 可复跑的命令与期望读数 | “跑一下测试” |
| 7 | 风险等级 | `low` / `medium` / `high` | 不标 |
| 8 | 所需审批 | `none` / `user` / `security` / `release` | 不标 |
| 9 | 交付证据 | commit、测试输出、截图、验收文件路径 | “代码已提交” |
| 10 | 超时与终止条件 | 单次/单票上限、最多尝试、什么情况停 | 不写 |

**合同哈希：** 票进入 `claimed` 时，把 Issue 正文（规范化后）的 SHA-256 写进 `task-state-<票>.json` 的 `contract_sha256`。执行中票面被改 ⇒ 哈希不匹配 ⇒ Group 停手写 `blocked`，由 Tower 重新确认合同并决定是否重发租约。**不许边飞边改目标。**

## 二、Definition of Ready（进 `ready` 前逐条过）

- [ ] 十字段齐全，且验收标准至少 1 条可机检
- [ ] 允许修改范围是逐枚路径，且与当前在制租约不重叠
- [ ] 依赖全部关闭并已验证，或明确写“无依赖”
- [ ] 风险等级与审批要求已标；高风险已有用户批准记录
- [ ] 验证命令在本机可跑，解释器/环境已写明
- [ ] 票面没有“等另一个票做完再说”这类死锚（锚点必须活着）

**任一不过 ⇒ 不进 Ready。** Tower 补合同或退回 Backlog，不许用“先飞起来再说”绕过。

## 三、Definition of Done（进 `closed` 前逐条过）

- [ ] 所有 AC 有证据；`acceptance.verdict=pass` 且 `unverified=[]`
- [ ] 改动只在租约内；越界 = 红，不放行
- [ ] 收尾门/pre-push 门通过；⑤ 回归按项目口径跑过
- [ ] 提交已落地（`direct` 模式：在 dev；`pr` 模式：已合并）
- [ ] 票面留了验收文件路径、门读数、落地 sha
- [ ] 工作树已回收或按规则点名保留；没有未提交内容被删
- [ ] 后续工作已开票或明确写“无后续”

**不准用“Issue 已关闭”代替 Done。** 关闭只是状态，Done 要证据链完整。

## 四、风险等级

| 等级 | 典型内容 | 默认执行 | 默认审批 |
|---|---|---|---|
| `low` | 文档、测试、局部实现、可逆改动 | 自动执行 + 自动出货 | `none` |
| `medium` | 跨模块修改、内部接口调整、复杂重构 | 自动执行 + 门禁后出货 | `none`（试点期）；稳定后可加抽查 |
| `high` | 数据库迁移、公开 API 契约、权限/安全边界、生产发布、不可逆数据操作 | 只做研究与实现，**不自动落地** | `user` 或 `security`，按项目配置 |

风险等级只能由 Tower/用户改；执行体不得在执行中自行降级。**AI 不得修改审批策略再用新策略批准自己的工作。**

## 五、Issue 正文模板（与 `.github/ISSUE_TEMPLATE/task.yml` 对齐）

````markdown
## 目标
（一句话）

## 验收标准
- [ ] AC1：...
- [ ] AC2：...

## 允许修改
- path/to/file
- path/to/dir/

## 禁止修改
- path/to/protected

## 前置依赖
无 / #NNNN / 外部条件

## 验证命令
```bash
python -m pytest path/to/test.py -q   # 期望：N passed
```

## 风险与审批
- 风险：low / medium / high
- 审批：none / user / security / release

## 交付证据
- commit：
- 测试输出：
- 验收文件：
- 截图/日志：

## 超时与终止
- 单次尝试 ≤ 30 分钟；单票 ≤ 60 分钟
- 最多 3 次尝试；同一错误 2 次即停
- 阻塞条件：...
````

## 六、运行态引用（不复制正文）

```json
{
  "schema": 1,
  "ticket": 1854,
  "state": "claimed",
  "contract_sha256": "<issue body 规范化后的 sha256>",
  "risk": "medium",
  "approval_required": false,
  "deadline": "2026-10-21T18:30:00+08:00",
  "attempt": 1,
  "max_attempts": 3,
  "owner": "group-a",
  "lease_id": "lease-1854-1",
  "branch": "exec/1854-...",
  "checkpoint": ".git/kai-scope/checkpoint-1854-a1.json",
  "updated_at": "2026-10-21T17:00:00+08:00"
}
```

`backlog` 时 `contract_sha256`/`risk`/`lease_id`/`branch`/`deadline` 可为 `null`；进入 `claimed` 前必须落值（合同哈希、风险、租约、分支、截止时间）。字段细节见 `schemas/task.schema.json`。
