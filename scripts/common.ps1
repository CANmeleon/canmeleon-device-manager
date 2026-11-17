Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'

function Invoke-CheckedPython {
    param([string[]]$Arguments)
    & $VenvPython @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed ($LASTEXITCODE): $($Arguments[0])" }
}

function Assert-Download {
    param([string]$Path, [string]$Sha256, [long]$Size)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing file: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -ne $Size) { throw "Size mismatch: $Path" }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Sha256) { throw "SHA-256 mismatch: $Path" }
}

function Get-PinnedDownload {
    param([string[]]$Urls, [string]$Path, [string]$Sha256, [long]$Size)
    if (Test-Path -LiteralPath $Path) {
        try { Assert-Download $Path $Sha256 $Size; return } catch { Write-Warning $_ }
    }
    $partial = "$Path.partial"
    $failures = @()
    foreach ($url in $Urls) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $partial -UseBasicParsing -TimeoutSec 180
            Assert-Download $partial $Sha256 $Size
            Move-Item -LiteralPath $partial -Destination $Path -Force
            return
        } catch { $failures += "$url : $($_.Exception.Message)" }
    }
    throw ($failures -join "`n")
}
