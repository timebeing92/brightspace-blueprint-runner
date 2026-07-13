# One-terminal launcher for the Brightspace blueprint bundle runner.
# Windows (PowerShell 5.1+ or PowerShell 7):
#     powershell -NoProfile -ExecutionPolicy Bypass -File blueprint_wizard.ps1
# or double-click "Blueprint Wizard.bat".
# NOTE: no Set-Location — the wizard resolves its own files absolutely, and
# staying in the caller's directory lets relative --export paths work.
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$MinVersion = [Version]"3.11"
$AssumeYes = ($args -contains "--yes") -or ($args -contains "-y")

function Read-YesNo([string]$Prompt, [bool]$Default = $false) {
    if ($AssumeYes) { return $true }
    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $reply = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($reply)) { return $Default }
    return $reply -match "^(y|yes)$"
}

function Test-Python([string[]]$Command) {
    # Probe the interpreter's version; also filters out the Microsoft Store
    # "python" alias, which fails this probe instead of running it.
    try {
        $probeArgs = @()
        if ($Command.Count -gt 1) { $probeArgs = @($Command[1..($Command.Count - 1)]) }
        $probeArgs += @("-c", "import sys; print('.'.join(map(str, sys.version_info[:2])))")
        $probe = & $Command[0] @probeArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe) {
            return ([Version]("$probe".Trim()) -ge $MinVersion)
        }
    } catch { }
    return $false
}

function Find-Python {
    $candidates = @()
    if ($env:PYTHON) { $candidates += ,@($env:PYTHON) }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in "-3.13", "-3.12", "-3.11", "-3") {
            $candidates += ,@("py", $ver)
        }
    }
    foreach ($cmd in "python3", "python") {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) { $candidates += ,@($cmd) }
    }
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate) { return $candidate }
    }
    return $null
}

function Install-Python {
    Write-Host "Python $MinVersion+ was not found."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "winget was not found. Install Python 3.11+ from https://www.python.org/downloads/ (check 'Add python.exe to PATH'), then rerun this launcher."
        return $false
    }
    if (-not (Read-YesNo "Install Python with winget now?" $true)) { return $false }
    winget install --id Python.Python.3.12 -e --source winget
    return ($LASTEXITCODE -eq 0)
}

$Python = Find-Python
if (-not $Python) {
    if (Install-Python) {
        # A fresh install updates PATH for new shells, not this one; the py
        # launcher usually appears immediately, so try once more.
        $Python = Find-Python
    }
    if (-not $Python) {
        Write-Host "Python 3.11+ is still not on PATH in this window." -ForegroundColor Yellow
        Write-Host "Open a NEW terminal (so PATH refreshes) and rerun this launcher."
        exit 1
    }
}

$PythonCmd = $Python[0]
$PythonArgs = @()
if ($Python.Count -gt 1) { $PythonArgs = @($Python[1..($Python.Count - 1)]) }

& $PythonCmd @PythonArgs (Join-Path $Here "scripts\blueprint_wizard.py") @args
exit $LASTEXITCODE
