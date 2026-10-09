@echo off
rem dcc-env: put the dcc-patcher launcher on PATH in THIS cmd window, setting it up first if needed.
rem   dcc-env stock | patched | <build file name>   also choose what `claude` runs in THIS window
rem   dcc-env default                               go back to the persistent choice (dcc-patcher use)
rem pip installs it beside dcc-patcher.exe. No setlocal: the PATH and DCC_MODE changes have to outlive this script.
set "DCC_ENV=1"
dcc-patcher install-shim --if-needed
set "DCC_ENV_CODE=%ERRORLEVEL%"
set "DCC_ENV="
if not "%DCC_ENV_CODE%"=="0" (set "DCC_ENV_CODE=" & exit /b 1)
set "DCC_ENV_CODE="
for /f "delims=" %%i in ('dcc-patcher shellenv cmd --folder') do set "PATH=%%i;%PATH%"
if not "%~1"=="" (
    if /i "%~1"=="default" (set "DCC_MODE=") else (set "DCC_MODE=%~1")
)
dcc-patcher status --brief
