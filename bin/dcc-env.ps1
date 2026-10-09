# dcc-env: put the dcc-patcher launcher on PATH in THIS PowerShell, setting it up first if needed.
# pip installs it beside dcc-patcher.exe. $env:Path belongs to the whole PowerShell process, so the
# change outlives this script. Needs an execution policy that runs local scripts (RemoteSigned or
# looser); otherwise use: dcc-patcher shellenv powershell | Invoke-Expression
$env:DCC_ENV = '1'
dcc-patcher install-shim --if-needed
$dccCode = $LASTEXITCODE
Remove-Item Env:\DCC_ENV -ErrorAction SilentlyContinue
if ($dccCode -ne 0) { return }
$dccFolder = dcc-patcher shellenv powershell --folder
if ($dccFolder) { $env:Path = "$dccFolder;" + $env:Path }
dcc-patcher status --brief
