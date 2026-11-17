[CmdletBinding()]
param([string]$RuntimeZip = '')
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Run scripts/setup.ps1 first.' }
$prepare = @((Join-Path $PSScriptRoot 'prepare_runtime.py'))
if ($RuntimeZip) { $prepare += @('--archive',([IO.Path]::GetFullPath($RuntimeZip))) }
Invoke-CheckedPython $prepare
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$output = Join-Path $RepoRoot "build\$stamp"
$compileRoot = $RepoRoot
$compileOutput = $output
$compilePython = $VenvPython
$stage = $null
# Dependency Walker used by Nuitka cannot read non-ASCII library paths.
# Compile an isolated copy in an ASCII scratch directory, then return the result.
if ($RepoRoot -match '[^\x00-\x7F]') {
    $stageBase = if ($env:CDM_OEM_BUILD_ROOT) { $env:CDM_OEM_BUILD_ROOT } else { Join-Path ([IO.Path]::GetTempPath()) 'cdm-oem-build' }
    $stageBase = [IO.Path]::GetFullPath($stageBase)
    if ($stageBase -match '[^\x00-\x7F]') { throw 'Set CDM_OEM_BUILD_ROOT to a writable ASCII path for the C compiler scratch directory.' }
    $stage = Join-Path $stageBase ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'oem'),(Join-Path $RepoRoot 'oem_main.py') -Destination $stage -Recurse
    $basePython = (& $VenvPython -c 'import json,sys; print(json.dumps(sys.base_prefix))') | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the pinned Python runtime.' }
    Copy-Item -LiteralPath $basePython -Destination (Join-Path $stage 'python') -Recurse
    & (Join-Path $stage 'python\python.exe') -m venv --without-pip (Join-Path $stage '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create compiler scratch environment.' }
    Get-ChildItem -LiteralPath (Join-Path $RepoRoot '.venv\Lib\site-packages') -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stage '.venv\Lib\site-packages') -Recurse
    }
    $compileRoot = $stage
    $compileOutput = Join-Path $stage 'output'
    $compilePython = Join-Path $stage '.venv\Scripts\python.exe'
}
$brand = Get-Content -LiteralPath (Join-Path $RepoRoot 'oem\branding.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$lock = Get-Content -LiteralPath (Join-Path $RepoRoot 'cdm-runtime.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$arguments = @('-m','nuitka','--standalone','--enable-plugin=pyside6','--assume-yes-for-downloads',
    '--windows-console-mode=disable','--output-filename=CDM_OEM.exe',"--output-dir=$compileOutput",
    "--windows-icon-from-ico=$(Join-Path $compileRoot ('oem\' + $brand.icon))",
    "--product-name=$($brand.name)","--file-version=$($lock.version)","--product-version=$($lock.version)",
    (Join-Path $compileRoot 'oem_main.py'))
& $compilePython @arguments
if ($LASTEXITCODE -ne 0) { throw "Nuitka build failed. Compiler scratch directory: $stage" }
$package = Join-Path $output 'oem_main.dist'
if ($stage) {
    New-Item -ItemType Directory -Force $output | Out-Null
    Copy-Item -LiteralPath (Join-Path $compileOutput 'oem_main.dist') -Destination $package -Recurse
    $resolvedStage = (Resolve-Path -LiteralPath $stage).Path
    if (-not $resolvedStage.StartsWith($stageBase.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe compiler scratch cleanup path.' }
    Remove-Item -LiteralPath $resolvedStage -Recurse -Force
}
$resources = Join-Path $package 'oem'
New-Item -ItemType Directory -Force -Path $resources,(Join-Path $package 'runtime') | Out-Null
foreach ($asset in @('branding.json',$brand.logo,$brand.icon)) {
    $assetTarget = Join-Path $resources $asset
    New-Item -ItemType Directory -Force (Split-Path -Parent $assetTarget) | Out-Null
    Copy-Item -LiteralPath (Join-Path $RepoRoot ('oem\' + $asset)) -Destination $assetTarget
}
Copy-Item -LiteralPath (Join-Path $RepoRoot 'cdm-runtime.lock.json') -Destination $package
Copy-Item -LiteralPath (Join-Path $RepoRoot '.runtime\cdm') -Destination (Join-Path $package 'runtime\cdm') -Recurse
Copy-Item -LiteralPath (Join-Path $RepoRoot 'LICENSE'),(Join-Path $RepoRoot 'THIRD_PARTY_NOTICES.md') -Destination $package
Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs') -Destination (Join-Path $package 'docs') -Recurse
Copy-Item -LiteralPath (Join-Path $RepoRoot 'licenses') -Destination (Join-Path $package 'licenses') -Recurse
$thirdPartyRoot = Join-Path $package 'licenses\distributions'
New-Item -ItemType Directory -Force $thirdPartyRoot | Out-Null
foreach ($distribution in Get-ChildItem (Join-Path $RepoRoot '.venv\Lib\site-packages') -Directory -Filter '*.dist-info') {
    if ($distribution.Name -match '^(pyside6|shiboken6)') {
        Copy-Item -LiteralPath $distribution.FullName -Destination (Join-Path $thirdPartyRoot $distribution.Name) -Recurse
    }
}
$pythonLicense = Join-Path $RepoRoot '.tools\python-3.12.10\tools\LICENSE.txt'
if (Test-Path -LiteralPath $pythonLicense) { Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $package 'licenses\Python-LICENSE.txt') }
Invoke-CheckedPython @((Join-Path $PSScriptRoot 'verify_package.py'),'--package',$package)
New-Item -ItemType Directory -Force (Join-Path $RepoRoot 'dist') | Out-Null
[IO.File]::WriteAllText((Join-Path $RepoRoot 'dist\package-path.txt'),$package,[Text.UTF8Encoding]::new($false))
Write-Host "Built package: $package"
