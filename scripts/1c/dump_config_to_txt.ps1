[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$ConnectionArgs,

    [Parameter()]
    [string]$OutputDirectory,

    [Parameter()]
    [string]$DesignerExecutable = '1cv8',

    [switch]$CleanOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..' '..')).Path

if (-not $PSBoundParameters.ContainsKey('OutputDirectory')) {
    $OutputDirectory = Join-Path (Join-Path $repoRoot '1c') 'config_dump_txt'
}

$buildRoot = Join-Path $repoRoot 'build'
$buildDir = Join-Path $buildRoot '1c'
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}
$logPath = Join-Path $buildDir 'dump_config_to_txt.log'
if (Test-Path $logPath) {
    Remove-Item $logPath -Force
}

Start-Transcript -Path $logPath -Append | Out-Null
try {
    if (-not (Test-Path $OutputDirectory)) {
        New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    }
    $resolvedOutput = (Resolve-Path $OutputDirectory).Path

    if ($CleanOutput.IsPresent) {
        Write-Host "Cleaning existing dump at $resolvedOutput"
        Get-ChildItem -Path $resolvedOutput -Force | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
    }

    if (-not $ConnectionArgs -or $ConnectionArgs.Count -eq 0) {
        throw 'At least one connection argument must be supplied (e.g. /F, /S).'
    }

    $designerArguments = @('DESIGNER') + $ConnectionArgs + @('/DumpConfigToFiles', $resolvedOutput)
    Write-Host "Invoking '$DesignerExecutable' with arguments:`n $($designerArguments -join ' ')"

    $process = Start-Process -FilePath $DesignerExecutable -ArgumentList $designerArguments -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "1cv8 exited with code $($process.ExitCode)"
    }

    Write-Host "Configuration dump completed successfully. Output: $resolvedOutput"
}
finally {
    try {
        Stop-Transcript | Out-Null
    } catch {
        Write-Warning $_
    }
}
