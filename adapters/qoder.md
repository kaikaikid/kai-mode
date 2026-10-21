# Qoder 适配器：只按铃子会话

> 2026-10-21 实测：定时执行会话（`independent`/`merged`）**没有** `qoder_cron`；同一会话**有** `create_chat_session`；它开出的普通子会话**有** `qoder_cron`。因此 Qoder 的按铃路径是“角色 → 子会话 → run 目标班”。

## 能力判据（现测，别抄）

```bash
# 在目标角色的执行会话里测，不在主会话里测
mcp_list(keyword="cron")        # 预期 0 条（定时执行会话）
mcp_get("mcp__builtin__create_chat_session")  # 预期可用
```

子会话里再测一次 `mcp_list(keyword="cron")`；有 `qoder_cron` 才走本适配器。没有 ⇒ 按 `adapters/opencode.md` 或 `adapters/codex.md` 起角色；仍不行 ⇒ `no-launcher`。

## 形状

```text
角色（定时执行会话，无 qoder_cron）
  └─ 写 handoff-<from>-<to>.json（≤500B）
     └─ create_chat_session(固定“只按铃”prompt)
        └─ 子会话（有 qoder_cron）
           ├─ 校验 handoff schema/必带字段/目标注册档
           ├─ 校验 commits 存在且可达；Ground 还要 verdict=pass、unverified=[]
           ├─ 目标在岗 ⇒ already-running，不按
           ├─ qoder_cron run(jobId) 一次
           └─ 写 activation-receipt-<ts>.json 后结束
```

## 固定 prompt（逐字带上，不许自由发挥）

```text
你是启动器，只按铃＋验门，不干活；最多 3 次工具调用。
1) 读 <handoff 文件>；校验 schema 与必带字段（schema/from/to/tickets/commits/branch/acceptance/at/seq）；缺一 ⇒ activation-failed，结束。
2) 目标必须是 <项目根>/.git/kai-scope/shift-runners.local.json 的 shifts 键之一；jobId 从该档读，读不到 ⇒ missing-jobid，结束。
3) 每个 commit 必须存在且在当前分支可达（git cat-file -e <sha>^{commit}；git merge-base --is-ancestor <sha> <branch>）；不过 ⇒ activation-failed。
4) 若目标=ground：读 acceptance.path 摘要，verdict 必须 pass 且 unverified 为空；不过 ⇒ activation-failed，不按。
5) 检查 .ai/scope/on-duty-<目标>.json：holder 非空且心跳新鲜 ⇒ already-running，结束。
6) qoder_cron run(jobId) 一次；写 activation-receipt-<ts>.json（handoff_sha256、目标、jobId、run id、结果、失败原因），结束。
硬边界：不改产品文件、不建树、不 push、不再 create_chat_session、不建/删任务；不读票面/验收全文。
```

## 回执

```json
{"schema":1,"handoff_sha256":"...","target":"ground","job_id":"...","run_id":"...","result":"dispatched|already-running|activation-failed|missing-jobid|no-launcher","reason":"...","at":"..."}
```

## 幂等与边界

- 目标在岗不按；同一 handoff 发两次只起一次（令牌/心跳判活）。
- 白名单＝注册档 `shifts` 键；jobId 只从注册档读，不猜。
- 子会话只按铃；发现它在改产品文件 ⇒ 本次交接判红。
- 代际上限 1：子会话不许再开子会话。
- 失败不静默；由低频 Coordinator 兜底。

## 成本

- 每次按铃有子会话固定入场开销；**批量**（2–5 张一按）、目标在岗不按、≤3 次工具调用，是主要省法。
- 子会话不读票面/验收全文；只看 handoff＋注册档＋令牌＋验收摘要。
- 若按铃频率高到子会话开销不可接受，再评估常驻激活器（用户另拍）。
