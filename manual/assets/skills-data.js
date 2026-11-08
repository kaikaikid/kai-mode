/* 自动生成：python scripts/manual-gen.py；不要手改。 */
window.KAI_SKILLS = [
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "bridge",
    "oneLine": "康娜（主 AI 人格，通用职业名「协调调度」）的方法正文与默认入口——不是另一个角色。",
    "trigger": "/bridge、/舰桥、/warp <任务>、/jump <任务>（曲速-N-任务、跃迁-N-任务 简写也认）；",
    "command": "/bridge",
    "version": "0.5.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "harness-audit",
    "oneLine": "给技能和文档做体检，找重叠、过期和该退役的东西。",
    "trigger": "说「体检」；手动安装",
    "command": "手动技能",
    "version": "0.2.1"
  },
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "kai-handoff",
    "oneLine": "把当前会话压成一份交接文档，下一棒能接着跑。",
    "trigger": "/handoff；说「写交接」",
    "command": "/handoff",
    "version": "0.3.6"
  },
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "principles",
    "oneLine": "七条原则合集：一次一问、只问可见与红线、能测就别问、一个语义一个家、缺件登记、仪式随规模、输出挑载体。",
    "trigger": "自动带入",
    "command": "",
    "version": "1.0.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "set-kai-mode",
    "oneLine": "安装与体检：先看缺什么，只装缺的。",
    "trigger": "/set-kai-mode；说「装一下」",
    "command": "/set-kai-mode",
    "version": "6.3.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "staff",
    "oneLine": "总入口：把一句话需求拆成票，再交给对应角色。",
    "trigger": "由舰桥调用；说「先规划」「想清楚再做」",
    "command": "/staff",
    "version": "4.2.0"
  },
  {
    "group": "舰桥与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "upgrade-kai-mode",
    "oneLine": "把已经装好的 kai-mode 升到新版：先出清单，再备份、回写、验收。",
    "trigger": "/upgrade-kai-mode；说「升级 kai-mode」",
    "command": "/upgrade-kai-mode",
    "version": "0.2.1"
  },
  {
    "group": "支持能力",
    "plugin": "看板",
    "pluginId": "board",
    "skill": "flight-info",
    "oneLine": "看板：把票、日表、交接和 Issue 汇总成一页。",
    "trigger": "/航班信息；说「看现在在飞什么」",
    "command": "/refresh",
    "version": "1.6.0"
  },
  {
    "group": "支持能力",
    "plugin": "想法池",
    "pluginId": "intake",
    "skill": "kai-boom-idea-log",
    "oneLine": "记想法：全文收进想法池，不开票。",
    "trigger": "说「记个想法」；/idea",
    "command": "/idea",
    "version": "0.1.4"
  },
  {
    "group": "支持能力",
    "plugin": "事故与运维",
    "pluginId": "ops",
    "skill": "incident-response",
    "oneLine": "事故处置：先分级止损，再复盘补票。",
    "trigger": "/incident；说「出事了」",
    "command": "/incident",
    "version": "0.1.0"
  },
  {
    "group": "支持能力",
    "plugin": "事故与运维",
    "pluginId": "ops",
    "skill": "runbook",
    "oneLine": "把重复操作写成能照着跑的步骤。",
    "trigger": "/runbook；说「写个 runbook」",
    "command": "/runbook",
    "version": "0.1.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "director",
    "oneLine": "导演：分镜、剪辑、配音，管成片节奏。",
    "trigger": "/director；说「导演」",
    "command": "/director",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "final-review",
    "oneLine": "终审：独立验收，只判不修，出 pass/fail。",
    "trigger": "/review；说「终审」",
    "command": "/final-review",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "lead-artist",
    "oneLine": "主美：风格板、角色、版面、成稿。",
    "trigger": "/artist；说「主美」",
    "command": "/lead-artist",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "lead-writer",
    "oneLine": "主笔：故事、剧本、台词、文案。",
    "trigger": "/writer；说「主笔」",
    "command": "/lead-writer",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "marketing",
    "oneLine": "宣发：物料、渠道、投放与数据回收。",
    "trigger": "/marketing；说「宣发」",
    "command": "/marketing",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "producer",
    "oneLine": "企划：立项、排期、预算、指派负责人。",
    "trigger": "/producer；说「企划」",
    "command": "/producer",
    "version": "2.0.0"
  },
  {
    "group": "舰队执行内核",
    "plugin": "执行内核",
    "pluginId": "engine",
    "skill": "fleet",
    "oneLine": "舰队执行内核（由康娜调度）：一个 issue 一个 run（舰船），主会话规划与验收，宿主自己的子代理执行；",
    "trigger": "由舰桥触发 /warp 或 /jump",
    "command": "",
    "version": "0.8.0"
  },
  {
    "group": "舰队执行内核",
    "plugin": "执行内核",
    "pluginId": "engine",
    "skill": "pk",
    "oneLine": "通用对比分析 PK：对项目/图像/文章等多对象做维度化对比，输出图表与结论。",
    "trigger": "/pk、/PK、/对比，或用户说「PK」「对比」「比一比」「PK 一下」",
    "command": "",
    "version": "0.1.1"
  }
];
