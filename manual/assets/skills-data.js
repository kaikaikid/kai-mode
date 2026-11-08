/* 自动生成：python scripts/manual-gen.py；不要手改。 */
window.KAI_SKILLS = [
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "bridge",
    "oneLine": "康娜的方法正文与默认入口：接单、判断、清场、施工、发货、回报。",
    "trigger": "默认入口；/bridge；说「开工」「发货」「清理脏文件」",
    "command": "/bridge",
    "version": "0.6.0"
  },
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "harness-audit",
    "oneLine": "给技能和文档做体检，找重叠、过期和该退役的东西。",
    "trigger": "说「体检」；手动安装",
    "command": "手动技能",
    "version": "0.2.1"
  },
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "kai-handoff",
    "oneLine": "把当前会话压成一份交接文档，下一棒能接着跑。",
    "trigger": "/handoff；说「写交接」",
    "command": "/handoff",
    "version": "0.3.6"
  },
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "principles",
    "oneLine": "七条原则合集：一次一问、只问可见与红线、能测就别问、一个语义一个家、缺件登记、仪式随规模、输出挑载体。",
    "trigger": "自动带入",
    "command": "",
    "version": "1.0.0"
  },
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "set-kai-mode",
    "oneLine": "安装与体检：先看缺什么，只装缺的。",
    "trigger": "/set-kai-mode；说「装一下」",
    "command": "/set-kai-mode",
    "version": "7.0.0"
  },
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "staff",
    "oneLine": "参谋部：把模糊需求收敛成规划表与拆票草案。",
    "trigger": "由康娜调用；说「先规划」「想清楚再做」",
    "command": "/staff",
    "version": "4.2.0"
  },
  {
    "group": "酒馆冒险团与安装",
    "plugin": "酒馆冒险团与安装",
    "pluginId": "core",
    "skill": "upgrade-kai-mode",
    "oneLine": "把已经装好的 kai-mode 升到新版：先出清单，再备份、回写、验收。",
    "trigger": "/upgrade-kai-mode；说「升级 kai-mode」",
    "command": "/upgrade-kai-mode",
    "version": "0.2.1"
  },
  {
    "group": "看板",
    "plugin": "看板",
    "pluginId": "board",
    "skill": "flight-info",
    "oneLine": "任务看板：把票、run、交接汇总成一页，给人和 AI 各一份。",
    "trigger": "/flight-info；说「看看板」「现在到哪了」",
    "command": "/refresh",
    "version": "1.6.0"
  },
  {
    "group": "想法池",
    "plugin": "想法池",
    "pluginId": "intake",
    "skill": "kai-boom-idea-log",
    "oneLine": "记想法：全文收进想法池，不开票。",
    "trigger": "说「记个想法」；/idea",
    "command": "/idea",
    "version": "0.1.4"
  },
  {
    "group": "事故与运维",
    "plugin": "事故与运维",
    "pluginId": "ops",
    "skill": "incident-response",
    "oneLine": "事故处置：先分级止损，再复盘补票。",
    "trigger": "/incident；说「出事了」",
    "command": "/incident",
    "version": "0.1.0"
  },
  {
    "group": "事故与运维",
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
    "oneLine": "武器｜分镜成片：分镜、节奏、声音、成片。",
    "trigger": "/director；说「分镜」「剪辑」「成片」",
    "command": "/director",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "final-review",
    "oneLine": "武器｜交付终审：独立验收，只判不修，出 pass/fail。",
    "trigger": "/review；说「终审」「验收」",
    "command": "/final-review",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "lead-artist",
    "oneLine": "武器｜视觉成稿：风格板、角色、色彩、版面、成稿。",
    "trigger": "/artist；说「画」「风格板」「配色」",
    "command": "/lead-artist",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "lead-writer",
    "oneLine": "武器｜剧本文案：故事骨架、剧本、台词、文案、字幕。",
    "trigger": "/writer；说「写稿」「改文案」",
    "command": "/lead-writer",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "marketing",
    "oneLine": "武器｜物料投放：包装成能到达受众的物料，排渠道、回收数据。",
    "trigger": "/marketing；说「宣发」「投放」",
    "command": "/marketing",
    "version": "2.0.0"
  },
  {
    "group": "武器集",
    "plugin": "武器集",
    "pluginId": "studio",
    "skill": "producer",
    "oneLine": "武器｜立项排期：把创作委托拆成阶段、排期与验收标准。",
    "trigger": "/producer；说「立项」「排期」",
    "command": "/producer",
    "version": "2.0.0"
  },
  {
    "group": "执行内核",
    "plugin": "执行内核",
    "pluginId": "engine",
    "skill": "fleet",
    "oneLine": "执行内核：一张票一个 run，宿主子代理施工，门点验收。",
    "trigger": "由康娜调用；说「开个 run」「跑起来」",
    "command": "",
    "version": "0.9.0"
  },
  {
    "group": "执行内核",
    "plugin": "执行内核",
    "pluginId": "engine",
    "skill": "pk",
    "oneLine": "通用对比分析：多对象维度化对比，出图表与结论。",
    "trigger": "/pk；说「对比」「比一比」",
    "command": "",
    "version": "0.1.1"
  }
];
