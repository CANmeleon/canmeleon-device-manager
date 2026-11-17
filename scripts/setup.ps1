[CmdletBinding()]
param([string]$RuntimeZip = '', [switch]$EnvironmentOnly)
. (Join-Path $PSScriptRoot 'common.ps1')
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$toolsDir = Join-Path $RepoRoot '.tools'
$cacheDir = Join-Path $RepoRoot '.cache'
New-Item -ItemType Directory -Force -Path $toolsDir,$cacheDir | Out-Null
$pythonRoot = Join-Path $toolsDir 'python-3.12.10'
$python = Join-Path $pythonRoot 'tools\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $archive = Join-Path $cacheDir 'python.3.12.10.nupkg'
    Get-PinnedDownload @('https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg') $archive '0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8' 14515433
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $pythonRoot)
}
& $python -c "import sys,struct; assert sys.version_info[:3]==(3,12,10) and struct.calcsize('P')==8"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12.10 x64 validation failed.' }
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & $python -m venv (Join-Path $RepoRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
Invoke-CheckedPython @('-c',"import sys,struct; assert sys.version_info[:3]==(3,12,10) and struct.calcsize('P')==8")
Invoke-CheckedPython @('-m','pip','install','--disable-pip-version-check','pip==25.0.1','setuptools==75.8.2','wheel==0.45.1')
Invoke-CheckedPython @('-m','pip','install','--disable-pip-version-check','--no-build-isolation','-r',(Join-Path $RepoRoot 'requirements.lock'))
if (-not $EnvironmentOnly) {
    $argsList = @((Join-Path $PSScriptRoot 'prepare_runtime.py'))
    if ($RuntimeZip) { $argsList += @('--archive',([IO.Path]::GetFullPath($RuntimeZip))) }
    Invoke-CheckedPython $argsList
}
Write-Host 'Environment ready. Run scripts/run.ps1.'
