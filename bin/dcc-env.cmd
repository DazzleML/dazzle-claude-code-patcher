@echo off
rem dcc-env: put the dcc-patcher launcher on PATH in THIS cmd window, setting it up first if needed.
rem   dcc-env stock | patched | <build file name>   also choose what `claude` runs in THIS window
rem   dcc-env default                               go back to the persistent choice (dcc-patcher use)
rem   dcc-env -h | --help | /?                      say all this, change nothing
rem   dcc-env -V | --version                        this script's version and dcc-patcher's
rem pip installs it beside dcc-patcher.exe. No setlocal: the PATH and DCC_MODE changes have to outlive this script.
if /i "%~1"=="-h" goto help
if /i "%~1"=="--help" goto help
if "%~1"=="/?" goto help
if "%~1"=="-V" goto version
if /i "%~1"=="--version" goto version
set "DCC_ENV_ARG=%~1"
if "%DCC_ENV_ARG:~0,1%"=="-" goto badopt
set "DCC_ENV_ARG="
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
goto :eof

:badopt
set "DCC_ENV_ARG="
echo dcc-env: unknown option %1 (dcc-env --help lists the choices) 1>&2
exit /b 2

:version
rem setlocal is safe here: -V changes nothing, so nothing has to outlive the script
setlocal
set "DCC_ENV_V=0.2.12"
echo dcc-env %DCC_ENV_V%
set "DCC_P="
for /f "tokens=2" %%v in ('dcc-patcher -V 2^>nul') do set "DCC_P=%%v"
if not defined DCC_P (echo dcc-patcher: not found on PATH& exit /b 1)
echo dcc-patcher %DCC_P%
if not "%DCC_P%"=="%DCC_ENV_V%" echo these differ: dcc-patcher update --fix brings them in step
exit /b 0

:help
echo usage: dcc-env [stock ^| patched ^| ^<build file name^> ^| default]
echo(
echo Puts the dcc-patcher launchers on PATH in this cmd window (setting them up
echo first if needed), then says what `claude` runs here.
echo(
echo   dcc-env                    set up or repair this window; keep the current choice
echo   dcc-env stock              `claude` runs the official Claude Code in this window
echo   dcc-env patched            `claude` runs the current patched build in this window
echo   dcc-env ^<build file name^>  `claude` runs that saved build in this window
echo   dcc-env default            back to the persistent choice
echo   dcc-env -h, --help         this help
echo   dcc-env -V, --version      this script's version and dcc-patcher's
echo(
echo A choice made here lasts until the window closes. For every shell, from the
echo next start: dcc-patcher use stock^|patched^|^<build^>. Which one wins, and the
echo builds folder: dcc-patcher status.
exit /b 0
