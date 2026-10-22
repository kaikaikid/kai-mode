@echo off
REM 刷新指定的一块航班信息板。
REM 用法：refresh_board.bat <项目仓根> <板名>
REM 例：refresh_board.bat D:\repo airport
REM 板在 <项目仓根>\.design\航班信息\HTML\<板名>\ 下；本脚本调同目录的适配脚本。
REM 退出码＝生成器退出码；退出码 0 只表示「板已生成」，数据好坏看 board.json 的 sources 字段。
setlocal
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
set "REPO_ROOT=%~1"
set "BOARD=%~2"
set "SCRIPT=%REPO_ROOT%\.design\航班信息\HTML\%BOARD%\render_%BOARD%.py"
if exist "%SCRIPT%" goto :run
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
echo 用法：refresh_board.bat ^<项目仓根^> ^<板名^>
echo 例：refresh_board.bat D:\repo airport
exit /b 2
:missing
echo 找不到该板的适配脚本：%SCRIPT%
exit /b 2
:done
exit /b %ERRORLEVEL%
