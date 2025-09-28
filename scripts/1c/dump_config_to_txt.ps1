[CmdletBinding(DefaultParameterSetName = 'File')]
param(
    [Parameter(ParameterSetName = 'File', Mandatory = $true)]
    [string]$FileInfobasePath,

    [Parameter(ParameterSetName = 'Server', Mandatory = $true)]
    [string]$ServerInfobase,

    [string]$DesignerPath = '1cv8',

    [string]$DumpDirectory,

    [string]$LogFile,

    [string]$User,

    [string]$Password,

    [string[]]$AdditionalDesignerArguments = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path -Path (Join-Path -Path $PSScriptRoot -ChildPath '..\..')).Path
if (-not $DumpDirectory) {
    $DumpDirectory = Join-Path -Path $repoRoot -ChildPath '1c/config_dump_txt'
}
if (-not $LogFile) {
    $LogFile = Join-Path -Path $repoRoot -ChildPath 'build/1c/dump_config_to_txt.log'
}

$dumpDirectoryItem = New-Item -ItemType Directory -Path $DumpDirectory -Force
$null = New-Item -ItemType Directory -Path (Split-Path -Path $LogFile -Parent) -Force

$transcriptStarted = $false
try {
    Start-Transcript -Path $LogFile -Append | Out-Null
    $transcriptStarted = $true

    $arguments = @('DESIGNER')
    switch ($PSCmdlet.ParameterSetName) {
        'File' {
            $resolvedFile = Resolve-Path -Path $FileInfobasePath
            $arguments += @('/F', $resolvedFile.Path)
        }
        'Server' {
            $arguments += @('/S', $ServerInfobase)
        }
    }

    if ($User) {
        $arguments += @('/N', $User)
    }
    if ($Password) {
        $arguments += @('/P', $Password)
    }

    $dumpPath = (Resolve-Path -Path $dumpDirectoryItem.FullName).Path
    $arguments += @('/DumpConfigToFiles', $dumpPath, '-Format', 'Plain')
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
