[CmdletBinding()]
param([string]$RuntimeZip = '', [string]$PackageDir = '', [string]$Iscc = '', [string]$OutputDir = '')
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $PackageDir) {
    & (Join-Path $PSScriptRoot 'build.ps1') -RuntimeZip $RuntimeZip
    $PackageDir = (Get-Content -LiteralPath (Join-Path $RepoRoot 'dist\package-path.txt') -Raw -Encoding UTF8).Trim()
}
Invoke-CheckedPython @((Join-Path $PSScriptRoot 'verify_package.py'),'--package',$PackageDir)
if (-not $Iscc) {
    foreach ($candidate in @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),(Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'))) {
        if (Test-Path -LiteralPath $candidate) { $Iscc = $candidate; break }
    }
}
if (-not $Iscc) { throw 'Install Inno Setup 6.7.3 (winget install --id JRSoftware.InnoSetup --version 6.7.3) or pass -Iscc.' }
$compilerVersion = (Get-Item -LiteralPath $Iscc).VersionInfo.FileVersion
if ($compilerVersion -eq '0.0.0.0') {
    $compilerDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $Iscc)).TrimEnd('\')
    foreach ($registryRoot in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
        if (-not (Test-Path $registryRoot)) { continue }
        foreach ($key in Get-ChildItem $registryRoot) {
            $entry = Get-ItemProperty $key.PSPath
            $locationProperty = $entry.PSObject.Properties['InstallLocation']
            $versionProperty = $entry.PSObject.Properties['DisplayVersion']
            if ($null -ne $locationProperty -and $null -ne $versionProperty -and
                ([string]$locationProperty.Value).TrimEnd('\') -eq $compilerDirectory) {
                $compilerVersion = [string]$versionProperty.Value
            }
        }
    }
}
if ($compilerVersion -notlike '6.7.3*') { throw "Expected Inno Setup 6.7.3, found $compilerVersion" }
if (-not $OutputDir) { $OutputDir = Join-Path $RepoRoot 'dist' }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$brand = Get-Content -LiteralPath (Join-Path $RepoRoot 'oem\branding.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$lock = Get-Content -LiteralPath (Join-Path $PackageDir 'cdm-runtime.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($value in @($brand.name,$brand.publisher,$brand.product_id,$brand.app_id)) {
    if ($value -match '["\r\n]') { throw 'Invalid installer branding text.' }
}
$env:OEM_SOURCE = [IO.Path]::GetFullPath($PackageDir)
$env:OEM_OUTPUT = [IO.Path]::GetFullPath($OutputDir)
$env:OEM_VERSION = $lock.version
$env:OEM_NAME = $brand.name
$env:OEM_PUBLISHER = $brand.publisher
$env:OEM_PRODUCT_ID = $brand.product_id
$env:OEM_APP_ID = $brand.app_id
$env:OEM_ICON = Join-Path $PackageDir ('oem\' + $brand.icon)
& $Iscc (Join-Path $PSScriptRoot 'oem.iss')
if ($LASTEXITCODE -ne 0) { throw 'OEM installer build failed.' }
$installer = Join-Path $OutputDir "CANmeleon-OEM-demo-$($lock.version)-setup-x64.exe"
if ((Get-Item -LiteralPath $installer).Length -ge 100000000) { throw 'Installer exceeds the current release size gate; do not publish.' }
$record = @{version=$lock.version;file=[IO.Path]::GetFileName($installer);size=(Get-Item -LiteralPath $installer).Length;
    sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant();signature_policy='sha256-only';unsigned_installer=$true}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'oem-installer-build.json') -Encoding UTF8
Write-Host "Built installer: $installer"
