# dcc-env: put the dcc-patcher launcher on PATH in THIS PowerShell, setting it up first if needed.
#   dcc-env stock | patched | <build file name>   also choose what `claude` runs in THIS PowerShell
#   dcc-env default                               go back to the persistent choice (dcc-patcher use)
# pip installs it beside dcc-patcher.exe. $env:Path and $env:DCC_MODE belong to the whole PowerShell
# process, so the changes outlive this script. Needs an execution policy that runs local scripts
# (RemoteSigned or looser); otherwise use: dcc-patcher shellenv powershell | Invoke-Expression
param([string]$Mode = '')
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
