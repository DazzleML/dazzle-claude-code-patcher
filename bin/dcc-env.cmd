@echo off
rem dcc-env: put the dcc-patcher launcher on PATH in THIS cmd window, setting it up first if needed.
rem pip installs it beside dcc-patcher.exe. No setlocal: the PATH change has to outlive this script.
set "DCC_ENV=1"
dcc-patcher install-shim --if-needed
set "DCC_ENV_CODE=%ERRORLEVEL%"
set "DCC_ENV="
if not "%DCC_ENV_CODE%"=="0" (set "DCC_ENV_CODE=" & exit /b 1)
set "DCC_ENV_CODE="
for /f "delims=" %%i in ('dcc-patcher shellenv cmd --folder') do set "PATH=%%i;%PATH%"
dcc-patcher status --brief
