# 宿主适配器契约（执行侧）

> `adapters/*.md` 管的是「**怎么把技能装到宿主**」；本文管的是「**怎么让宿主跑 worker**」。
> 两件事分开写，谁换宿主谁读本文。

## 1. 适配器是什么

一个 `.py` 文件，导出 `ADAPTER`（类或实例），实现五个方法。内核只认这五个方法，
不认你是 Claude Code、Qoder、Codex、OpenCode 还是别的什么。

```python
class Adapter:
    name = "<宿主名>"

    def probe(self) -> dict:
        """能不能用，以及能力申报。不许猜，能跑就跑一下。"""

    def spawn(self, brief, cwd, session_dir, tier="medium", timeout=1800,
              read_only=False, resume=None) -> dict:
        """起一个一次性子会话。返回 handle（至少含 pid / proc / dir）。"""

    def wait(self, handle, timeout) -> int: ...
    def read(self, handle) -> str: ...
    def kill(self, handle) -> None: ...
```

- `spawn` 是**一次性**语义：写 brief 进去（stdin 或文件），跑完退出。没有交互回合。
- `read(handle)` 只许依赖 `handle["dir"]`：`travel report` 恢复会话时手里只剩目录，
  进程对象早没了。`harness verify` 会专门用 `{"dir": …}` 调一次来验这条。
- `read` 返回的文本里必须含有报告（见 §4）；日志另存 `stdout.log` / `stderr.log` 也行，
  但 `read` 要能把报告读出来。
- `resume=<会话 id>` 表示续接同一个宿主会话（对话模式用）；做不到就申报 `resume: false`，
  内核会退化成每次新会话，不假装记得。
- `read_only=True` 表示门卫审查：这个模式下**不许写盘**。做不到就如实申报（见 §3）。

## 2. 放哪

按下面的顺序找，第一个命中的即用；也可以显式 `--adapter <名>` 指定，
或设 `TRAVEL_ADAPTER=<名>`、在 `.coding/config.json` 写 `{"adapter": "<名>"}`。

| 顺序 | 位置 | 谁放 |
|---|---|---|
| 1 | `<项目根>/.coding/adapters/<名>.py` | 项目自己，已进 `.gitignore` |
| 2 | `<KAI_AGENT_DATA_ROOT>/kai-mode/adapters/<名>.py` | 整机共用 |
| 3 | `~/.kai-mode/adapters/<名>.py` | 没设上面那个变量时的兜底 |

同目录里的其它 `.py`（含 `_util.py` 这类以下划线开头的）**不会被加载，也不会进 import 路径**：
辅助模块没被登记、没被哈希，借它执行代码等于绕过信任。所以适配器是**单文件**。
文件名的身份就是适配器名，`state.json` 里存的是它——**改名等于换适配器**，旧 run 的会话会找不到。

**适配器不进框架仓。** 框架仓只放这份契约和三个内建适配器（`claude-cli` / `mock` / `generic`）；
宿主的适配器代码是每台机器现场生成的产物，写在上面三处之一。宿主代码进仓会把框架仓钉死在
某一个宿主上——而这套东西要能装到任何宿主。

## 3. 能力申报（必须诚实）

`probe()` 返回：

```json
{"ok": true, "version": "<宿主版本>", "maxConcurrent": 4,
 "supportsTools": true, "structuredOutput": true, "resume": false}
```

| 字段 | 含义 | 漏报的后果 |
|---|---|---|
| `supportsTools` | 有没有**硬机制**拒绝危险工具（白名单／沙箱／权限对象） | 报 `true` 但其实没有 ⇒ 铁律「子会话不发货」被绕开，`harness verify` 判失败 |
| `structuredOutput` | 能不能稳定产出 JSON 报告 | 报 `true` 但产出自由文本 ⇒ 报告解析失败，任务被误判 partial |
| `resume` | 中断后能否续到同一子会话 | 报 `true` 但续不了 ⇒ 内核重跑，白烧 token |

**默认按最弱算**：不写 `supportsTools` 就当 `false`。`false` 的适配器仍可用于只读审查和建议，
但 `travel spawn` 会打警告——因为那种模式下「worker 只能靠提示词自觉」。

## 4. 报告契约

子会话最后必须留下一段 JSON（前后可以有说明文字，内核会逐位置提取）：

```json
{"result": "done|partial|blocked",
 "files_changed": ["path — 改了什么"],
 "commit": "<HEAD sha，没有改动则为空>",
 "verification": ["命令 -> 结果"],
 "open_questions": ["..."],
 "notes": "<=100 字"}
```

门卫（`read_only=True`）的报告用：

```json
{"result": "done", "verdict": "accept|return",
 "defects": ["..."], "reason": "...", "files_changed": [], "verification": []}
```

## 5. 验收：`travel harness verify <名>` → `travel harness trust <名>`

写完不算数，跑通才算数。`verify` 用固定用例真跑三轮，全过才写绿色回执：

| 用例 | 怎么判 | 不过意味着 |
|---|---|---|
| 能写 | brief 要求新建 `probe.txt` 内容 `OK` | `spawn` / `wait` 不通 |
| 能报 | 报告里有 `result` 且确实提到 `probe.txt`（空壳 `{"result":"done"}`、解析不出来的信封都不算） | 报告契约没落地，`travel report` 收不到东西 |
| 能读 | 换一个**新实例**、只给 `{"dir": …}` 也能取回含 `probe.txt` 的报告（非空字符串不算） | 验收过了、收报告时崩 |
| 能不写 | `read_only=True` 那一轮结束后，整个工作目录不许有任何改动 | 申报 `supportsTools: true` 的判**失败**；报 `false` 的只记警告 |

结果落在 `<适配器同目录>/<名>.verify.json`，含时间、结论、适配器文件 sha256 与宿主版本。
`travel harness check` 会拿它对照两件事：**文件哈希变了**（适配器改过）或
**宿主版本变了**（宿主升级过），任一命中就标 `stale` / `host_changed_since_verify`，要重验。

`trust` 把「名字 + 该文件的绝对路径 + sha256」记进 `<数据根>/kai-mode/adapters/trusted.json`。
**没登记过的适配器文件不会被 import**——克隆来的仓库带着 `.coding/adapters/x.py` 也不会在你机器上
执行；同名同内容但换了路径（比如别处 clone 下来的）同样不算数。文件一改，登记自动失效，
要重新 `verify` + `trust`。

## 6. 自举：新宿主怎么接进来

当前 AI 自己就是那个宿主，它最清楚自己的 CLI 怎么一次性执行。步骤：

1. `travel harness check` —— 看当前解析到哪个适配器、适配器目录在哪；
2. 没有自己的适配器 ⇒ 按本文写一个 `<名>.py`，放到 §2 的第一个目录；
3. `travel harness verify <名>` —— 不过就改，改到过；
4. `travel harness trust <名>` —— 把这个文件的 sha256 登记进本机信任表（**人看过再登记**）；
5. 在 `<项目根>/.coding/config.json` 写 `{"adapter": "<名>"}`，或在环境里设
   `TRAVEL_ADAPTER=<名>`；
6. 在项目 `adapters/` 说明里补一行（宿主名、CLI 入口、已知限制）——那是对**人**的说明，
   和这里的代码适配器是两件事。

## 7. 安全

- 适配器是**任意代码**，内核会 import 它。只在 §2 三个目录里加载，文件名首字符必须是
  字母或数字（`[A-Za-z0-9][A-Za-z0-9._-]*`），不接受路径分隔符，不做远程下载。
- **没 `trust` 过的文件不会被 import**，`harness check` 也只算哈希、不执行它。
  克隆来的仓库里带着 `.coding/adapters/x.py`，在你登记之前等于一块石头。
- 适配器必须是**单文件**：同目录的辅助 `.py` 不进 import 路径（它们没登记、没哈希）。
- `verify` 只证明「能跑」，不是安全审计：登记前请人读一遍那个文件。
- 宿主升级后适配器可能失效；`check` 里 `stale` / `host_changed_since_verify` 任一为真就重验。
- 一个适配器写坏了，最坏情况是 worker 不产出——那会在 `travel report` 里被 diff 对账判 partial，
  不会静默算成功。**不要**为了让流程往下走而放宽报告校验。
