' refresh.vbs — 人工「刷新」按钮的无黑窗入口（Windows）。
' 由板页面里的按钮调用；双击也能跑。只起一个静默 WScript 进程，不弹黑窗口。
' 它去跑 refresh_if_dirty.py --force（强制重新生成，无视脏标记）。
' 重新读页面这件事交给按钮自己（location.reload，file:// 下即重读磁盘）。
'
' 可选参数 1：延迟秒数。git 钩子的「尾随补刷」用它——先 WScript.Sleep 再刷。
' 为什么延迟要放在 vbs 里、不用 sh 的 `sleep`：`sleep.exe` 是**控制台**程序，
' 在无控制台的父进程（GUI 里的 git）下会给自己开一个控制台窗口＝黑窗；
' wscript 是 GUI 子系统，Sleep 期间不占任何窗口（用户 2026-10-27 明令）。
Set sh = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

delaySec = 0
If WScript.Arguments.Count > 0 Then
  If IsNumeric(WScript.Arguments(0)) Then delaySec = CLng(WScript.Arguments(0))
End If
If delaySec > 0 Then WScript.Sleep delaySec * 1000

' 本文件所在目录＝板目录；板配置在板目录/board.config.json
boardDir = FSO.GetParentFolderName(WScript.ScriptFullName)
cfg = FSO.BuildPath(boardDir, "board.config.json")

' 仓库根：板目录通常是 <output.root>/<板名>，往上两级；但板目录也可能直接在仓根，
' 所以优先 <output.root>/<板名> 之外，再退回板目录父目录。这里用更稳的判定：
' 仓根由调用方以环境变量 REPO_ROOT 传入；没有就用板目录往上找 .git。
' ExpandEnvironmentStrings 对未定义的变量原样返回 "%REPO_ROOT%"（不返回空串），
' 所以除了判空，还要把这种没展开的占位符当「没传」处理。
Dim repoRoot : repoRoot = sh.ExpandEnvironmentStrings("%REPO_ROOT%")
If InStr(repoRoot, "%") > 0 Then repoRoot = ""
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

' 本文件被安装器复制到板目录后，向上两级算出来是仓根而不是技能根，路径必然落空。
' 那时改从同目录的 refresh_task.bat（安装器写的是绝对路径）里抠出脚本路径。
If Not FSO.FileExists(py) Then
  Dim batPath : batPath = FSO.BuildPath(boardDir, "refresh_task.bat")
  If FSO.FileExists(batPath) Then
    Dim tf, ln, p, q1, q2
    Set tf = FSO.OpenTextFile(batPath, 1)
    Do While Not tf.AtEndOfStream
      ln = tf.ReadLine
      p = InStr(ln, ".py")
      If p > 0 Then
        q2 = InStr(p, ln, """")            ' .py 之后的收尾引号
        If q2 > 0 Then q1 = InStrRev(ln, """", q2 - 1)   ' 收尾引号之前的开引号
        If q1 > 0 And q2 > q1 Then py = Mid(ln, q1 + 1, q2 - q1 - 1)
        Exit Do
      End If
    Loop
    tf.Close
  End If
End If

' 找 python：优先仓库自带解释器（KAI_BACKEND_PYTHON），否则 PATH 里的 python。
Dim pyExe : pyExe = "python"
Dim kaiEnv : kaiEnv = sh.ExpandEnvironmentStrings("%KAI_BACKEND_PYTHON%")
If kaiEnv <> "" And FSO.FileExists(kaiEnv) Then pyExe = """" & kaiEnv & """"

cmd = pyExe & " """ & py & """ --repo-root """ & repoRoot _
      & """ --config """ & cfg & """ --force --quiet"
sh.Run cmd, 0, True

WScript.Quit 0
