[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Run scripts/setup.ps1 first.' }
Invoke-CheckedPython @((Join-Path $RepoRoot 'oem_main.py'))
