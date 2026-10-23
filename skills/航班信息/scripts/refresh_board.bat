@echo off
REM 刷新指定的一块航班信息板。
REM 用法：refresh_board.bat <项目仓根> <板名> [板库根]
REM 板库根＝板配置 output.root（相对项目仓根）；不给第三参就按 .design 布局扫一遍，
REM 还找不到 ⇒ 报缺件退出 2（本脚本不写死板库路径，框架仓旧裁决）。
REM 退出码＝生成器退出码；退出码 0 只表示「板已生成」，数据好坏看 board.json 的 sources 字段。
setlocal
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
set "REPO_ROOT=%~1"
set "BOARD=%~2"
set "SCRIPT="
if not "%~3"=="" set "SCRIPT=%~3\%BOARD%\render_%BOARD%.py"
if defined SCRIPT if exist "%SCRIPT%" goto :run
for /f "delims=" %%f in ('dir /b /s "%REPO_ROOT%\.design\*\HTML\%BOARD%\render_%BOARD%.py" 2^>nul') do set "SCRIPT=%%f"
if not exist "%SCRIPT%" goto :missing
:run
where python >nul 2>&1
if errorlevel 1 goto :use_py
python "%SCRIPT%" --repo-root "%REPO_ROOT%" --quiet
goto :done
:use_py
py -3 "%SCRIPT%" --repo-root "%REPO_ROOT%" --quiet
goto :done
:usage
echo 用法：refresh_board.bat ^<项目仓根^> ^<板名^> [板库根]
echo 板库根＝板配置 output.root；不给就在仓里按 .design 布局扫
exit /b 2
:missing
echo 找不到该板的适配脚本：板库根没给（板配置 output.root），扫也没扫到
echo 补法：refresh_board.bat %REPO_ROOT% %BOARD% ^<板库根^>
exit /b 2
:done
exit /b %ERRORLEVEL%
