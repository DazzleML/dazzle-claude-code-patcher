# dcc-env: put the dcc-patcher launcher on PATH in THIS PowerShell, setting it up first if needed.
#   dcc-env stock | patched | <build file name>   also choose what `claude` runs in THIS PowerShell
#   dcc-env default                               go back to the persistent choice (dcc-patcher use)
#   dcc-env -h | --help                           say all this, change nothing
#   dcc-env -V | --version                        this script's version and dcc-patcher's
# pip installs it beside dcc-patcher.exe. $env:Path and $env:DCC_MODE belong to the whole PowerShell
# process, so the changes outlive this script. Needs an execution policy that runs local scripts
# (RemoteSigned or looser); otherwise use: dcc-patcher shellenv powershell | Invoke-Expression
# No param() block: with one, PowerShell would refuse -h as an unknown parameter before this runs.
$Mode = if ($args.Count) { [string]$args[0] } else { '' }
if ($Mode -in '-h', '--help') {
    @'
usage: dcc-env [stock | patched | <build file name> | default]

Puts the dcc-patcher launchers on PATH in this PowerShell (setting them up
first if needed), then says what `claude` runs here.

  dcc-env                    set up or repair this shell; keep the current choice
  dcc-env stock              `claude` runs the official Claude Code in this shell
  dcc-env patched            `claude` runs the current patched build in this shell
  dcc-env <build file name>  `claude` runs that saved build in this shell
  dcc-env default            back to the persistent choice
  dcc-env -h, --help         this help
  dcc-env -V, --version      this script's version and dcc-patcher's

A choice made here lasts until the shell closes. For every shell, from the
next start: dcc-patcher use stock|patched|<build>. Which one wins, and the
builds folder: dcc-patcher status.
'@
    return
}
if ($Mode -ceq '-V' -or $Mode -eq '--version') {
    $DCC_ENV_V = '0.2.7'
    "dcc-env $DCC_ENV_V"
    $p = (dcc-patcher -V 2>$null) -replace '^dcc-patcher\s+', ''
    if (-not $p) { 'dcc-patcher: not found on PATH'; exit 1 }
    "dcc-patcher $p"
    if ($p -ne $DCC_ENV_V) { 'these differ: dcc-patcher update --fix brings them in step' }
    return
}
if ($Mode.StartsWith('-')) {
    [Console]::Error.WriteLine("dcc-env: unknown option $Mode (dcc-env --help lists the choices)")
    exit 2
}
$env:DCC_ENV = '1'
dcc-patcher install-shim --if-needed
$dccCode = $LASTEXITCODE
Remove-Item Env:\DCC_ENV -ErrorAction SilentlyContinue
if ($dccCode -ne 0) { return }
$dccFolder = dcc-patcher shellenv powershell --folder
if ($dccFolder) { $env:Path = "$dccFolder;" + $env:Path }
if ($Mode) {
    if ($Mode -eq 'default') { Remove-Item Env:\DCC_MODE -ErrorAction SilentlyContinue }
    else { $env:DCC_MODE = $Mode }
}
dcc-patcher status --brief
