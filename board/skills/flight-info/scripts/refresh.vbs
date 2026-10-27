' refresh.vbs — 人工「刷新」按钮的无黑窗入口（Windows）。
' 由板页面里的按钮调用；双击也能跑。只起一个静默 WScript 进程，不弹黑窗口。
' 它去跑 refresh_if_dirty.py --force（强制重新生成，无视脏标记）。
' 重新读页面这件事交给按钮自己（location.reload，file:// 下即重读磁盘）。
Set Wsh = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' 本文件所在目录＝板目录；板配置在板目录/board.config.json
boardDir = FSO.GetParentFolderName(WScript.ScriptFullName)
cfg = FSO.BuildPath(boardDir, "board.config.json")

' 仓库根：板目录通常是 <output.root>/<板名>，往上两级；但板目录也可能直接在仓根，
' 所以优先 <output.root>/<板名> 之外，再退回板目录父目录。这里用更稳的判定：
' 仓根由调用方以环境变量 REPO_ROOT 传入；没有就用板目录往上找 .git。
Dim repoRoot : repoRoot = Wsh.ExpandEnvironmentStrings("%REPO_ROOT%")
If repoRoot = "" Then
  Dim probe : probe = boardDir
  Do While probe <> "" And Not FSO.FolderExists(FSO.BuildPath(probe, ".git"))
    probe = FSO.GetParentFolderName(probe)
  Loop
  If probe = "" Then probe = FSO.GetParentFolderName(boardDir)
  repoRoot = probe
End If

' 技能仓根：向上两级（scripts/refresh.vbs → scripts → 技能根）
skillRoot = FSO.GetParentFolderName(FSO.GetParentFolderName(WScript.ScriptFullName))
py = skillRoot & "\scripts\refresh_if_dirty.py"

' 找 python：优先仓库自带解释器（KAI_BACKEND_PYTHON），否则 PATH 里的 python。
Dim pyExe : pyExe = "python"
Dim kaiEnv : kaiEnv = Wsh.ExpandEnvironmentStrings("%KAI_BACKEND_PYTHON%")
If kaiEnv <> "" And FSO.FileExists(kaiEnv) Then pyExe = """" & kaiEnv & """"

cmd = pyExe & " """ & py & """ --repo-root """ & repoRoot _
      & """ --config """ & cfg & """ --force --quiet"
Wsh.Run cmd, 0, True

WScript.Quit 0
