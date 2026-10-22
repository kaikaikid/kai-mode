#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给航班信息板装「零 token 定时刷新」——走操作系统自己的闹钟，不经过任何 AI。

为什么不是让 agent 定时刷（对比 set-kai-mode 的塔台定时器）：
  塔台定时器靠宿主的定时口（qoder_cron 之类），每轮要拉起一个 AI 会话读 SKILL.md，
  token 是持续成本，而且换一家宿主就得重配一遍。
  本脚本走的是**操作系统级调度**（Windows 任务计划 / POSIX crontab），
  到点直接执行该板的适配脚本（纯 Python、确定性、不联网也能跑），
  谁在跑、甚至没有任何 agent 在跑都一样刷 ⇒ **跨 agent 适用、零 token**。

用法：
  python install_refresh_timer.py --repo-root <项目仓根> [--board <板名> | --all]
                                  [--every 30] [--python <解释器>] [--apply]
  python install_refresh_timer.py --repo-root <项目仓根> [--board <板名> | --all] --list
  python install_refresh_timer.py --repo-root <项目仓根> [--board <板名> | --all] --remove

参数：
  --repo-root   项目仓根（板库＝<仓根>/.design/航班信息/HTML/<板名>/）
  --board       板名；不给 --all 时必填其一
  --all         扫板库里所有板，逐块装 / 查 / 停
  --every       周期（分钟，默认 30；Windows 1–1439，POSIX 会换算成 */N）
  --python      钉死解释器绝对路径（默认＝当前 sys.executable；不写它就不会变）
  --apply       真装 / 真停；**不给它就只干跑打印**，跟本仓其它装机脚本一个脾气
  --list        查在不在册 ＋ 上次刷新多久前（只读）
  --remove      停掉并删除该板的定时任务

产出：
  <板目录>/refresh_<板名>.timer.bat   刷新壳（CRLF；%~dp0 相对定位，不写死机器路径）
  <板目录>/refresh.log                最近一次刷新的输出（覆盖写，不长个）

退出码：0＝成了；2＝用法或找不到板；3＝系统命令不干；4＝不支持的系统。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

try:  # 只有 Windows 有这套注册表；别的平台协议这条路走不通，如实说
    import winreg
except ImportError:
    winreg = None

TASK_PREFIX = "flight-info"
PROTOCOL = "flight-info"
DEFAULT_EVERY = 30
LIB_REL = os.path.join(".design", "航班信息", "HTML")


def manifest_path() -> Path:
    """机器级小账本：板名 → 该板的刷新壳路径（协议分发时查它）。"""
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or "."
    return Path(base) / ".kai-mode" / "flight-info-boards.json"


def load_manifest() -> dict:
    try:
        return json.loads(manifest_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_manifest(data: dict) -> None:
    p = manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if data:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        try:
            p.unlink()
        except OSError:
            pass


def _launcher() -> str:
    """注册表里记的启动器：有 pythonw 就用它（不弹黑窗），没有就用当前解释器。"""
    exe = Path(sys.executable)
    if os.name == "nt":
        cand = exe.with_name("pythonw.exe")
        if cand.is_file():
            return str(cand)
    return str(exe)


def _board_from_url(url: str) -> str:
    """flight-info://refresh/<板名> ⇒ <板名>（中文会被浏览器编码，这里解回来）。"""
    raw = urllib.parse.urlparse(url or "")
    parts = [p for p in (raw.netloc + "/" + raw.path).split("/") if p]
    parts = [p for p in parts if p.lower() != "refresh"]
    return urllib.parse.unquote(parts[-1]) if parts else ""


def register_protocol(board: str, bat: Path, apply: bool) -> tuple[int, str]:
    """把「页面刷新按钮」跟刷新脚本绑起来：注册一个自定义 URL 协议。"""
    if winreg is None:
        return 4, "这个平台没有 Windows 注册表，装不了协议（页面按钮只能退回「重读旧文件」）"
    cmd = '"%s" "%s" --dispatch "%%1"' % (_launcher(), Path(__file__).resolve())
    url = "%s://refresh/%s" % (PROTOCOL, board)
    if not apply:
        return 0, ("干跑（加 --apply 才真装）\n  协议：%s\n  command：%s\n  账本：%s → %s"
                   % (url, cmd, manifest_path(), bat))
    data = load_manifest()
    data[board] = str(bat)
    try:
        save_manifest(data)
    except OSError as exc:
        return 3, "账本写不出：%s" % exc
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                "Software\\Classes\\%s" % PROTOCOL, 0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:航班信息板刷新")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                                "Software\\Classes\\%s\\shell\\open\\command" % PROTOCOL,
                                0, winreg.KEY_WRITE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
    except OSError as exc:
        return 3, "注册表写不进：%s" % exc
    return 0, "已注册 %s —— 页面「刷新」按钮现在会真去生成一次（浏览器头一回可能问一句要不要打开，勾不再询问即可）" % url


def unregister_protocol(board: str, apply: bool) -> tuple[int, str]:
    if winreg is None:
        return 4, "这个平台没有 Windows 注册表"
    if not apply:
        return 0, "干跑（加 --apply 才真卸）\n  把「%s」从账本里去掉；账本空了连协议一起删" % board
    data = load_manifest()
    data.pop(board, None)
    try:
        save_manifest(data)
    except OSError as exc:
        return 3, "账本写不出：%s" % exc
    if data:
        return 0, "已卸「%s」；还有别的板在用，协议留着" % board
    for sub in ("shell\\open\\command", "shell\\open", "shell", ""):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             ("Software\\Classes\\%s\\%s" % (PROTOCOL, sub)).rstrip("\\"))
        except OSError:
            pass
    return 0, "已卸「%s」；没有板用了，协议一并删掉" % board


def hook_text(kind: str) -> str:
    """项目仓 .githooks/post-commit 或 post-merge 的正文（LF，bash）。

    四条都是实测踩出来的，别改回去：
      ① 不能同步硬刷 —— 联网的板刷一次要几十秒，同步会把 commit 卡死；
      ② 不能 `(cmd ... &)` 丢后台 —— 钩子一退出子进程就被回收，板根本没刷；
      ③ 要 60 秒去抖 —— 连续多次 commit 不该每次都刷；
      ④ 没定时任务就只提示 —— fail-open 到底，宁可少刷一次也不卡提交。
    """
    if kind == "post-merge":
        return (
            "#!/usr/bin/env bash\n"
            "# post-merge — 合并 / pull 后刷一次航班信息板\n"
            "# 补的正是「别人在别处提交、你 pull 下来」这一格：定时和本机 commit 钩子都管不到它。\n"
            "# 实现委托给 post-commit（同一套 fail-open 规矩），不复制第二份判据。\n"
            "set -uo pipefail\n\n"
            'HOOK="$(cd "$(dirname "$0")" && pwd)/post-commit"\n'
            '[ -x "$HOOK" ] || exit 0\n'
            'exec "$HOOK"\n'
        )
    return (
        "#!/usr/bin/env bash\n"
        "# post-commit — 提交后刷一次航班信息板（事件驱动：真变了才刷，不用等闹钟）\n"
        "# 由 kai-mode 板工坊落：skills/航班信息/scripts/install_refresh_timer.py --install-hook\n"
        "# 与塔台定时器（宿主定时口、要 token）无关：git 钩子只认「这个仓发生了一次 commit」，\n"
        "# 不认是谁提交的 —— AI 交、人手动交，都一样触发 ⇒ 跨 agent、零 token。\n"
        "#\n"
        "# 哲学（跟本仓 pre-commit 一套）：钩子只当发令员 —— fail-open、绝不阻塞 git。\n"
        "#   exit 0 永远：刷失败、没装板、刚刷过、没装定时任务，一律静默放行。\n"
        "# 别改回去的三条：\n"
        "#   ① 不能同步硬刷 —— 联网的板刷一次几十秒，同步会把 commit 卡死；\n"
        "#   ② 不能 (cmd ... &) 丢后台 —— 钩子一退出子进程就被回收，板根本没刷；\n"
        "#   ③ 要 60 秒去抖 —— 连续多次 commit 不该每次都刷一遍。\n"
        "set -uo pipefail\n\n"
        'ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0\n'
        '[ -n "$ROOT" ] || exit 0\n\n'
        'BOARD_LIB="$ROOT/.design/航班信息/HTML"\n'
        '[ -d "$BOARD_LIB" ] || exit 0\n\n'
        "shopt -s nullglob\n"
        'for BAT in "$BOARD_LIB"/*/refresh_*.timer.bat; do\n'
        '  [ -f "$BAT" ] || continue\n'
        '  STAMP="$(dirname "$BAT")/refresh.log"\n'
        '  if [ -f "$STAMP" ]; then\n'
        "    AGE=$(( $(date +%s) - $(date -r \"$STAMP\" +%s 2>/dev/null || echo 0) ))\n"
        '    [ "$AGE" -lt 60 ] && continue\n'
        "  fi\n\n"
        '  BOARD="$(basename "$(dirname "$BAT")")"\n'
        "  # ① 优先：叫醒已装的定时任务（异步，不阻塞 commit）。Git Bash 下开关要 // 双写。\n"
        '  if [ -n "$BOARD" ] && command -v schtasks >/dev/null 2>&1; then\n'
        '    schtasks //Run //TN "%s-$BOARD" >/dev/null 2>&1 && continue\n'
        "  fi\n"
        "  # 没定时任务 ⇒ 只提示，绝不硬刷（硬刷几十秒会把 commit 卡死）\n"
        '  echo "航班信息板：没装定时任务，跳过刷新（装：install_refresh_timer.py --repo-root'
        ' <仓根> --all --every 5 --apply）" >&2\n'
        "done\n\n"
        "exit 0\n" % TASK_PREFIX
    )


def install_hook(repo_root: Path, apply: bool) -> tuple[int, str]:
    """给项目仓挂 post-commit / post-merge 两枚钩子（不碰既有钩子）。"""
    hooks = repo_root / ".githooks"
    if not hooks.is_dir():
        return 2, "这个仓没有 .githooks/（先 `git config core.hooksPath .githooks`）"
    lines = []
    worst = 0
    for kind in ("post-commit", "post-merge"):
        p = hooks / kind
        if p.exists():
            lines.append("  %s：已存在，不动它（要重写先自己删）" % kind)
            continue
        if not apply:
            lines.append("  将写 %s（%d 字节）" % (kind, len(hook_text(kind))))
            continue
        try:
            p.write_bytes(hook_text(kind).encode("utf-8"))  # 明确 LF，CRLF 会让 bash 钩子炸
            os.chmod(p, 0o755)
            lines.append("  已写 %s 并给执行权限" % kind)
        except OSError as exc:
            worst = max(worst, 3)
            lines.append("  %s 写不出：%s" % (kind, exc))
    head = "干跑（加 --apply 才真装）" if not apply else "钩子就位"
    return worst, head + "\n" + "\n".join(lines)


def _python_from_bat(bat: Path) -> str | None:
    """从刷新壳里抠出钉死的那个解释器（壳是自包含的，python 路径只写在那儿）。"""
    try:
        text = bat.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'"([^"]*[Pp]ython[^"]*\.exe)"', text)
    return m.group(1) if m else None


def dispatch(url: str) -> int:
    """被系统拉起时干的事：按 URL 里的板名找到刷新壳，跑一次，**全程不许弹黑窗**。

    无窗口三件套，少一样就翻车：
      ① 直接启动解释器跑生成器，而不是 `cmd /c xxx.bat` —— 控制台程序被 GUI 进程拉起时
         系统会补一个控制台窗口，弹的就是它；用 CREATE_NO_WINDOW 压住。
      ② stdin 必须钉 DEVNULL —— 被调用方是 pythonw（GUI 进程、无控制台）时，
         子进程会继承一个无效 stdin，里面的 git / gh 读它就挂住（实测卡 125 秒退 -1）。
         DEVNULL 是**可继承的有效句柄**，生成器的子进程也跟着沾光。
      ③ stdout/stderr 我们自己接管写 refresh.log —— pythonw 下 print 是静默的，不接管就没日志。
    """
    board = _board_from_url(url)
    bat = load_manifest().get(board)
    if not bat or not Path(bat).is_file():
        print("没这块板的刷新壳：%s（先跑 install_refresh_timer.py --register-protocol --apply）" % board)
        return 2

    bat_path = Path(bat)
    board_dir = bat_path.parent
    render = board_dir / ("render_%s.py" % board)
    py = _python_from_bat(bat_path)
    log = board_dir / "refresh.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    if py and render.is_file():
        cmd = [py, str(render), "--quiet"]
    else:  # 抠不出解释器就退回刷新壳（可能会闪一下窗，但至少能刷）
        cmd = (["cmd", "/c", str(bat_path)] if os.name == "nt"
               else [str(bat_path)])
    try:
        with open(log, "w", encoding="utf-8") as f:
            p = subprocess.run(cmd, cwd=str(board_dir), stdin=subprocess.DEVNULL,
                               stdout=f, stderr=subprocess.STDOUT, creationflags=flags)
    except (OSError, ValueError) as exc:
        print("跑不动刷新壳：%s" % exc)
        return 3
    return p.returncode


def lib_root(repo_root: Path) -> Path:
    return repo_root / LIB_REL


def find_boards(repo_root: Path, name: str | None) -> list[tuple[str, Path, Path]]:
    """扫板库：返回 [(板名, 板目录, 适配脚本)]。板名空 ⇒ 全扫。"""
    root = lib_root(repo_root)
    out: list[tuple[str, Path, Path]] = []
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if name and d.name != name:
            continue
        script = d / ("render_%s.py" % d.name)
        if script.is_file():
            out.append((d.name, d, script))
    return out


def task_name(board: str) -> str:
    return "%s-%s" % (TASK_PREFIX, board)


def _tag(board: str) -> str:
    return hashlib.md5(board.encode("utf-8")).hexdigest()[:8]


def task_xml(board: str, real_bat: Path, every: int) -> tuple[Path, str]:
    """把任务写成 XML 再导入 —— 中文板库路径走 Unicode，不过命令行这一关。

    踩过的坑（本机实证）：`/TR` 里塞 `.design\\航班信息\\...` 这种中文路径 ＋ `cmd /c "..."` 的引号嵌套，
    schtasks 直接报「系统找不到指定的文件」；改塞纯 ASCII 包装脚本也不行 ——
    包装里的中文按 GBK 写，cmd 当前代码页不是 936 时照样读成乱码、0 秒返回且板没刷。
    XML 导入绕开命令行解析，是唯一走得通的路。
    """
    start = time.strftime("%Y-%m-%dT%H:%M:%S")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo>\n"
        "    <Description>航班信息板定时刷新（零 token、跨 agent）</Description>\n"
        "  </RegistrationInfo>\n"
        "  <Triggers>\n"
        "    <TimeTrigger>\n"
        "      <StartBoundary>%s</StartBoundary>\n"
        "      <Enabled>true</Enabled>\n"
        "      <Repetition>\n"
        "        <Interval>PT%dM</Interval>\n"
        "        <StopAtDurationEnd>false</StopAtDurationEnd>\n"
        "      </Repetition>\n"
        "    </TimeTrigger>\n"
        "  </Triggers>\n"
        '  <Principals>\n    <Principal id="Author">\n'
        "      <LogonType>InteractiveToken</LogonType>\n"
        "      <RunLevel>LeastPrivilege</RunLevel>\n"
        "    </Principal>\n  </Principals>\n"
        "  <Settings>\n"
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n"
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        "    <StartWhenAvailable>true</StartWhenAvailable>\n"
        "    <AllowStartOnDemand>true</AllowStartOnDemand>\n"
        "    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>\n"
        "    <Enabled>true</Enabled>\n"
        "    <!-- Hidden=true：任务隐藏运行，不然每 5 分钟闪一个黑窗 -->\n"
        "    <Hidden>true</Hidden>\n"
        "  </Settings>\n"
        '  <Actions Context="Author">\n    <Exec>\n'
        "      <Command>%s</Command>\n"
        "    </Exec>\n  </Actions>\n"
        "</Task>\n" % (start, every, real_bat)
    )
    tmp = Path(tempfile.gettempdir()) / ("flight-info-%s.xml" % _tag(board))
    tmp.write_text(xml, encoding="utf-8")
    return tmp, xml


def wrapper_cmd(board: str, real_bat: Path) -> Path:
    """兜底用：纯 ASCII 包装脚本（XML 那条路走不通时试它）。"""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE") or "."
    d = Path(base) / "kai-mode" / "flight-info-timers"
    d.mkdir(parents=True, exist_ok=True)
    p = d / ("flight-info-%s.cmd" % _tag(board))
    # chcp 65001 ＋ UTF-8 写：cmd 代码页不固定，靠切换兜住中文
    p.write_bytes(('@echo off\r\nchcp 65001 >nul\r\ncall "%s"\r\nexit /b 0\r\n' % real_bat)
                  .encode("utf-8"))
    return p


def timer_bat_text(board: str, py: str) -> str:
    """刷新壳（CRLF）。用 %~dp0 相对定位 ⇒ 里面没有一条机器绝对路径。"""
    return (
        "@echo off\r\n"
        "REM 零 token 刷新：由操作系统定时器直接调，不经过任何 AI。\r\n"
        "REM 生成器自己从脚本所在目录往上探项目仓根，所以这里不用传 --repo-root。\r\n"
        "REM 退出码＝生成器退出码；0 只表示「板已生成」，数据好坏看 board.json 的 sources。\r\n"
        '"%s" "%%~dp0render_%s.py" --quiet > "%%~dp0refresh.log" 2>&1\r\n'
        "exit /b %%ERRORLEVEL%%\r\n" % (py, board)
    )


def age_text(board_dir: Path) -> str:
    """上次刷新多久前（读机读面的 generated_ts；读不到就说没数）。"""
    try:
        data = json.loads((board_dir / "board.json").read_text(encoding="utf-8"))
        ts = int(data.get("generated_ts") or 0)
    except Exception:
        return "上次刷新：读不到 board.json"
    if not ts:
        return "上次刷新：board.json 里没时刻"
    mins = max(0, int((time.time() - ts) / 60))
    if mins < 60:
        return "上次刷新：%d 分钟前" % mins
    if mins < 60 * 24:
        return "上次刷新：%.1f 小时前" % (mins / 60)
    return "上次刷新：%.1f 天前" % (mins / 60 / 24)


def run(cmd: list[str]) -> tuple[int, str]:
    """跑系统命令。调不动（没装 / 被安全策略挡）也要如实说，不许崩栈。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    except (OSError, ValueError) as exc:
        return 127, "调不动 %s：%s（机器没这个命令，或被安全策略挡了）" % (cmd[0], exc)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ---------- Windows：任务计划程序 ----------

def win_install(board: str, board_dir: Path, py: str, every: int, apply: bool) -> tuple[int, str]:
    bat = board_dir / ("refresh_%s.timer.bat" % board)
    try:
        xml_path, _ = task_xml(board, bat, every)
        wrapper = wrapper_cmd(board, bat)
    except OSError as exc:
        return 3, "临时件写不出：%s" % exc
    tr = str(wrapper) if " " not in str(wrapper) else '"%s"' % wrapper
    plans = (
        ("XML 导入（首选：中文路径走 Unicode，不过命令行）",
         ["schtasks", "/Create", "/TN", task_name(board), "/XML", str(xml_path), "/F"]),
        ("命令行（兜底：纯 ASCII 包装层）",
         ["schtasks", "/Create", "/TN", task_name(board), "/TR", tr,
          "/SC", "MINUTE", "/MO", str(every), "/F"]),
    )
    if not apply:
        lines = ["干跑（加 --apply 才真装）", "  刷新壳：%s" % bat,
                 "  方式一 %s" % " ".join(plans[0][1]), "  方式二 %s" % " ".join(plans[1][1])]
        return 0, "\n".join(lines)
    try:
        bat.write_text(timer_bat_text(board, py), encoding="utf-8", newline="")
    except OSError as exc:
        return 3, "刷新壳写不出：%s" % exc
    tried = []
    for label, cmd in plans:
        rc, out = run(cmd)
        if rc == 0:
            return 0, "已装：%s（每 %d 分钟）· %s" % (task_name(board), every, label)
        tried.append("  %s：rc=%d %s" % (label, rc, out.strip()[:200]))
    return 3, ("schtasks 两条路都没建成（中文路径是常见元凶，见 XML 说明）：\n%s\n"
               "  探针：schtasks /Create /TN \"kai-probe\" /TR "
               "C:\\Windows\\System32\\notepad.exe /SC MINUTE /MO 60 /F\n"
               "  · 探针也失败 ⇒ 这台机器的 schtasks 用不了（多半被安全策略挡），"
               "只能靠人工 / 页面按钮 / git 钩子\n"
               "  · 探针成功 ⇒ 把上面失败原文贴回来" % "\n".join(tried))


def win_state(board: str) -> str:
    rc, out = run(["schtasks", "/Query", "/TN", task_name(board)])
    if rc == 127:
        return "查不了（%s）" % out.strip()
    if rc != 0:
        return "未装"
    rc2, out2 = run(["schtasks", "/Query", "/TN", task_name(board), "/FO", "LIST", "/V"])
    keep = []
    for line in (out2 or out).splitlines():
        low = line.strip().lower()
        if any(k in low for k in ("下次运行时间", "next run time", "上次运行时间",
                                  "last run time", "状态", "status", "计划任务", "taskname")):
            keep.append(line.strip())
    return "已装；" + (" ｜ ".join(keep) if keep else "（读不到明细）")


def win_remove(board: str, apply: bool) -> tuple[int, str]:
    cmd = ["schtasks", "/Delete", "/TN", task_name(board), "/F"]
    if not apply:
        return 0, "干跑（加 --apply 才真停）\n  命令：%s" % " ".join(cmd)
    rc, out = run(cmd)
    if rc != 0:
        return 3, "schtasks 删任务失败（rc=%d）：%s" % (rc, out.strip())
    return 0, "已停并删除：%s" % task_name(board)


# ---------- POSIX：crontab ----------

def posix_line(board: str, script: Path, py: str, every: int) -> str:
    log = script.parent / "refresh.log"
    return '*/%d * * * * "%s" "%s" --quiet > "%s" 2>&1 # %s-%s' % (
        every, py, script, log, TASK_PREFIX, board)


def posix_install(board: str, script: Path, py: str, every: int, apply: bool) -> tuple[int, str]:
    rc, cur = run(["crontab", "-l"])
    base = cur if rc == 0 else ""
    rest = [ln for ln in base.splitlines()
            if ("# %s-%s" % (TASK_PREFIX, board)) not in ln]
    line = posix_line(board, script, py, every)
    if not apply:
        return 0, "干跑（加 --apply 才真装）\n  crontab 行：%s" % line
    new = "\n".join(rest + [line]).strip() + "\n"
    rc2, out2 = run(["crontab", "-"])
    if rc2 != 0:
        # crontab - 从 stdin 读，上面这种调法不通时退回写文件
        p = subprocess.run(["crontab"], input=new, capture_output=True, text=True)
        if p.returncode != 0:
            return 3, "crontab 写入失败：%s" % (p.stderr or out2).strip()
    return 0, "已装：%s（每 %d 分钟）\n  crontab 行：%s" % (task_name(board), every, line)


def posix_state(board: str) -> str:
    rc, cur = run(["crontab", "-l"])
    if rc == 127:
        return "查不了（%s）" % cur.strip()
    if rc != 0:
        return "未装（读不到 crontab）"
    for ln in cur.splitlines():
        if ("# %s-%s" % (TASK_PREFIX, board)) in ln:
            return "已装；%s" % ln.strip()
    return "未装"


def posix_remove(board: str, apply: bool) -> tuple[int, str]:
    rc, cur = run(["crontab", "-l"])
    if rc != 0:
        return 3, "读不到 crontab"
    rest = [ln for ln in cur.splitlines()
            if ("# %s-%s" % (TASK_PREFIX, board)) not in ln]
    if not apply:
        return 0, "干跑（加 --apply 才真停）\n  去掉标记 # %s-%s 的那一行" % (TASK_PREFIX, board)
    new = "\n".join(rest).strip() + "\n"
    p = subprocess.run(["crontab"], input=new, capture_output=True, text=True)
    if p.returncode != 0:
        return 3, "crontab 写入失败：%s" % (p.stderr or "").strip()
    return 0, "已停并删除：%s" % task_name(board)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="给航班信息板装零 token 定时刷新（走操作系统闹钟）")
    # 不能 required：--dispatch 是被系统按协议拉起的，只有 URL、没有仓根，
    # required 会让 argparse 直接报错退出（实测：按钮点了没反应就是这个）。
    ap.add_argument("--repo-root", default=None, help="项目仓根")
    ap.add_argument("--board", default=None, help="板名；与 --all 二选一")
    ap.add_argument("--all", action="store_true", help="扫板库里所有板")
    ap.add_argument("--every", type=int, default=DEFAULT_EVERY, help="周期（分钟，默认 30）")
    ap.add_argument("--python", default=sys.executable, help="钉死解释器绝对路径")
    ap.add_argument("--apply", action="store_true", help="真装 / 真停；不给就只干跑")
    ap.add_argument("--list", action="store_true", help="查状态（只读）")
    ap.add_argument("--remove", action="store_true", help="停掉并删除定时任务")
    ap.add_argument("--register-protocol", action="store_true",
                    help="把页面「刷新」按钮绑到刷新脚本（注册 flight-info:// 协议）")
    ap.add_argument("--unregister-protocol", action="store_true", help="解绑页面按钮")
    ap.add_argument("--install-hook", action="store_true",
                    help="给项目仓挂 post-commit / post-merge（事件驱动；不碰既有钩子）")
    ap.add_argument("--dispatch", default=None, metavar="URL",
                    help="内部用：协议被拉起时由系统调用，别手敲")
    args = ap.parse_args(argv)

    if args.dispatch is not None:
        return dispatch(args.dispatch)

    if not args.repo_root:
        print("要给哪个仓：--repo-root <项目仓根>", file=sys.stderr)
        return 2

    if not args.board and not args.all:
        print("要给哪块板：--board <板名> 或 --all", file=sys.stderr)
        return 2
    if args.every < 1:
        print("周期得是正整数分钟", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    boards = find_boards(repo_root, None if args.all else args.board)
    if not boards:
        print("板库里没找到板：%s（先跑 set-航班信息 装一块）" % lib_root(repo_root),
              file=sys.stderr)
        return 2

    if os.name == "nt":
        inst, state, rem = win_install, win_state, win_remove
    elif os.name == "posix":
        inst, state, rem = posix_install, posix_state, posix_remove
    else:
        print("不支持的系统：%s" % os.name, file=sys.stderr)
        return 4

    if args.install_hook:
        rc, msg = install_hook(repo_root, args.apply)
        print("── 事件驱动钩子 %s" % repo_root)
        print("  %s" % msg)
        return rc

    worst = 0
    for name, board_dir, script in boards:
        print("── 板「%s」 %s" % (name, age_text(board_dir)))
        if args.list:
            print("  定时：%s" % state(name))
            continue
        if args.register_protocol:
            bat = board_dir / ("refresh_%s.timer.bat" % name)
            if args.apply and not bat.exists():
                try:  # 没装过定时器也要先把刷新壳落好，协议才有的调
                    bat.write_text(timer_bat_text(name, args.python), encoding="utf-8", newline="")
                except OSError as exc:
                    print("  刷新壳写不出：%s" % exc)
                    worst = max(worst, 3)
                    continue
            rc, msg = register_protocol(name, bat, args.apply)
        elif args.unregister_protocol:
            rc, msg = unregister_protocol(name, args.apply)
        elif args.remove:
            rc, msg = rem(name, args.apply)
        else:
            rc, msg = inst(name, board_dir if os.name == "nt" else script,
                           args.python, args.every, args.apply)
        print("  %s" % msg)
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    sys.exit(main())
