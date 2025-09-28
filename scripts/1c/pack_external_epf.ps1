[CmdletBinding()]
param(
    [string]$SourceDirectory,

    [string]$OutputFile,

    [string]$DesignerPath = '1cv8',

    [string]$LogFile,

    [string]$User,

    [string]$Password,

    [switch]$AsReport,

    [string[]]$AdditionalDesignerArguments = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path -Path (Join-Path -Path $PSScriptRoot -ChildPath '..\..')).Path
if (-not $SourceDirectory) {
    $SourceDirectory = Join-Path -Path $repoRoot -ChildPath '1c/external/kmp4_delivery_report/src'
}
if (-not $OutputFile) {
    $OutputFile = Join-Path -Path $repoRoot -ChildPath 'build/1c/kmp4_delivery_report.epf'
}
if (-not $LogFile) {
    $LogFile = Join-Path -Path $repoRoot -ChildPath 'build/1c/pack_kmp4.log'
}

$buildDirectory = Join-Path -Path $repoRoot -ChildPath 'build/1c'
$null = New-Item -ItemType Directory -Path $buildDirectory -Force

$resolvedSource = Resolve-Path -Path $SourceDirectory
$absoluteOutput = [System.IO.Path]::GetFullPath($OutputFile)
$null = New-Item -ItemType Directory -Path (Split-Path -Path $absoluteOutput -Parent) -Force
$null = New-Item -ItemType Directory -Path (Split-Path -Path $LogFile -Parent) -Force

$transcriptStarted = $false
try {
    Start-Transcript -Path $LogFile -Append | Out-Null
    $transcriptStarted = $true

    $arguments = @('DESIGNER')
    if ($User) {
        $arguments += @('/N', $User)
    }
    if ($Password) {
        $arguments += @('/P', $Password)
    }

    $arguments += @(
        '/LoadExternalDataProcessorOrReportFromFiles',
        $resolvedSource.Path,
        $absoluteOutput
    )

    if ($AsReport.IsPresent) {
        $arguments += '-ExternalReport'
    }
    else {
        $arguments += '-ExternalDataProcessor'
    }

    if ($AdditionalDesignerArguments.Count -gt 0) {
        $arguments += $AdditionalDesignerArguments
    }

    Write-Host "Invoking $DesignerPath $($arguments -join ' ')"
    & $DesignerPath @arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "1cv8 exited with code $exitCode"
    }
}
finally {
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
}
