# 0031 飞书桥：用 CLI 长连接做远端收发面，不用公网回调

## Status

**accepted** —— 2026-11-01 用户拍板「按照这个方案做，机器人建群的事留给安装的 agent 自己装，
你只写方案，通过 set-kai-mode 初始化新设置」。
设计正本：[`docs/design/2026-11-01-feishu-bridge.md`](../design/2026-11-01-feishu-bridge.md)。

## Context

- 用户日常在飞书里；希望「发一句话就能派活、做完能收到消息、要拍板能点按钮」，
  不想每次回到电脑前敲命令。
- 之前的立场是「V2 的输入是 issue/任务文本，不做聊天入口」（ADR-0029 的「不做」清单里点了 Feishu）。
  现在需求变了：单人单机，需要一个**远程入口**。
- 公网回调在内网 Windows 机器上部署成本高（穿透 / 证书 / 白名单）。
- 本机已装 `lark-cli` 1.0.93，应用已绑定、bot 身份就绪；实测 `lark-cli event consume`
  起本地 bus daemon 并建立 **Feishu WebSocket**（`feishu-websocket: connected`），
  事件以 NDJSON 出、可直接落文件；出站命令支持交互卡片与幂等键。
- 现有底座够用：`travel serve` 已有受控写端点（gate/stop/drive，带 token、同源与 Host 校验），
  `state.json` 是 run 的真相，宿主适配器（ADR-0030）能起一次性会话。

## Decision

### D1 通道用 lark-cli 的 WebSocket 长连接

不做公网回调 URL、不做轮询飞书：事件由 lark-cli 的 bus daemon 推送，桥只是消费它的 NDJSON。
出站用 `im +messages-send` / `+messages-reply`（交互卡片 + 幂等键）。**零额外基础设施**。

### D2 桥不是第二个舰桥

飞书桥只做三件事：**收指令、发状态、收按钮**。不推进 phase、不 spawn/review/accept、不验收。
所有写操作只经 `travel` 命令或 `travel serve` 的既有端点；桥里不出现 `state.save(`，
源码检查作为机械门。

### D3 脚本承担一切确定性工作，AI 只在需要判断时醒一次

收件、去重、鉴权、分诊、卡片渲染、回调、重试全部是脚本，**零 token**。
唤醒 AI 的条件只有：白名单真人的消息需要规划/起草/自由问答。一次唤醒 = 一次宿主适配器 spawn，
串行单飞、带冷却/超时/预算。状态变化、定时器、未授权消息、机器人入群事件一律不唤醒。

### D4 默认全拒

白名单（open_id / chat_id）默认空 = 谁都不认；没有「安装即放开」。
卡片 token 不是身份凭证，只用于更新卡片；动作另带 HMAC 与一次性 nonce。
未授权消息不外发、不执行，只留审计（默认只存正文哈希）。

### D5 配置住机器级，不动项目实例 schema

`<KAI_AGENT_DATA_ROOT>/kai-mode/feishu.json` 存 app 绑定、白名单、默认群、serve 地址与 token 变量名；
项目级 `.coding/feishu.json` 可选，决定「这个仓接不接、发哪个群」。
**不改** `templates/kai-mode.project.json`、不升 schema——open_id / chat_id / token 是机器事实，
写进 tracked 的项目实例既是错误位置，也要连带动 init-project、check-instance 与所有旧实例迁移。

### D6 建群/拉机器人归安装阶段

`set-kai-mode` 的缺口扫描加第 11 项「飞书桥」、安装步骤加第 7 步「飞书桥（可选）」：
由安装 agent 探测、建群（`im +chat-create --as bot`，bot 即创建者）、或在既有群由群主拉入，
然后写配置、做有界收发自检、按三格登记缺件。**运行时桥不碰群成员**。

### D7 GitHub 默认不查

本地 `.coding/runs/` 已经是 run 的完整事实；`gh` 只在开票、关票这类真需要时调用一次。
不做 GitHub 轮询。

## Consequences

- 用户在飞书就能派活、看进度、点按钮拍板；等待与播报全程不花 token。
- 不引入公网暴露面：入站靠出站长连接，服务仍只听 127.0.0.1。
- 多一个常驻进程（`feishu-bridge`），Windows 需 `pythonw`/计划任务保持静默。
- 新增攻击面集中在「谁能驱动舰队」：靠默认拒绝 + 白名单 + 限速 + 审计收敛；
  飞书正文一律不可信，消息里的指令不能直接触发发货这类红线动作。
- 卡片按钮 30 分钟后失效是外部约束，设计上用「过期就补发新卡」兜底，不追求原地更新。

## Alternatives

- **自定义机器人 webhook 单向通知**：半天能出效果，但收不到指令、点不了按钮——不满足需求。
- **HTTP 回调**：功能等价，但需要公网地址/穿透，在内网 Windows 上运维成本明显更高。
- **桥内直接写 `state.json`**：最省事，但会绕过锁、校验与门禁，等于把两套写入口并列——
  与 ADR-0029 的「唯一真相源」冲突，否决。
