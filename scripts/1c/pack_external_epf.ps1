[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$ConnectionArgs,

    [Parameter()]
    [string]$SourceDirectory,

    [Parameter()]
    [string]$OutputFile,

    [Parameter()]
    [string]$DesignerExecutable = '1cv8',

    [switch]$Overwrite
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..' '..')).Path

$buildRoot = Join-Path $repoRoot 'build'
$buildDir = Join-Path $buildRoot '1c'
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}
$logPath = Join-Path $buildDir 'pack_kmp4.log'
if (Test-Path $logPath) {
    Remove-Item $logPath -Force
}

if (-not $PSBoundParameters.ContainsKey('SourceDirectory')) {
    $externalRoot = Join-Path (Join-Path $repoRoot '1c') 'external'
    $kmp4Root = Join-Path $externalRoot 'kmp4_delivery_report'
    $SourceDirectory = Join-Path $kmp4Root 'src'
}
if (-not $PSBoundParameters.ContainsKey('OutputFile')) {
    $OutputFile = Join-Path $buildDir 'kmp4_delivery_report.epf'
}

Start-Transcript -Path $logPath -Append | Out-Null
try {
    if (-not (Test-Path $SourceDirectory)) {
        throw "Source directory not found: $SourceDirectory"
    }
    $resolvedSource = (Resolve-Path $SourceDirectory).Path

    $outputParent = Split-Path -Parent $OutputFile
    if (-not [string]::IsNullOrWhiteSpace($outputParent) -and -not (Test-Path $outputParent)) {
        New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
    }
    $resolvedOutput = [System.IO.Path]::GetFullPath($OutputFile)

    if (Test-Path $resolvedOutput) {
        if ($Overwrite.IsPresent) {
            Remove-Item $resolvedOutput -Force
        } else {
            throw "Output file already exists. Use -Overwrite to replace: $resolvedOutput"
        }
    }

    if (-not $ConnectionArgs -or $ConnectionArgs.Count -eq 0) {
        throw 'At least one connection argument must be supplied (e.g. /F, /S).'
    }

    $designerArguments = @('DESIGNER') + $ConnectionArgs + @('/LoadExternalDataProcessorOrReportFromFiles', $resolvedSource, $resolvedOutput)
    Write-Host "Invoking '$DesignerExecutable' with arguments:`n $($designerArguments -join ' ')"

    $process = Start-Process -FilePath $DesignerExecutable -ArgumentList $designerArguments -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "1cv8 exited with code $($process.ExitCode)"
    }

    Write-Host "External report packaged successfully. Output: $resolvedOutput"
}
finally {
    try {
        Stop-Transcript | Out-Null
    } catch {
        Write-Warning $_
    }
}
