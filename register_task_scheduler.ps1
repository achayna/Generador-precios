<#
.SYNOPSIS
    Registra la tarea programada en Windows 11 (4 corridas diarias: 08:30, 11:30, 14:30 y 18:00)
    para extraer precios desde IP peruana y publicar automáticamente output/ en GitHub.
#>

$ErrorActionPreference = "Stop"

$TaskName = "IMARPE_INFOMAR_Precios_Diarios"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ProjectDir "run_extractor.bat"

if (-not (Test-Path $BatPath)) {
    throw "No se encontró el archivo $BatPath"
}

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ProjectDir
$Triggers = @(
    (New-ScheduledTaskTrigger -Daily -At 08:30AM),
    (New-ScheduledTaskTrigger -Daily -At 11:30AM),
    (New-ScheduledTaskTrigger -Daily -At 02:30PM),
    (New-ScheduledTaskTrigger -Daily -At 06:00PM)
)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Triggers `
    -Settings $Settings `
    -Description "Extracción y publicación GitHub 4x/día (08:30, 11:30, 14:30, 18:00) de precios en playa INFOMAR - IMARPE." `
    -Force | Out-Null

Write-Host "Tarea '$TaskName' registrada con éxito (08:30, 11:30, 14:30 y 18:00 diario -> auto-push GitHub)." -ForegroundColor Green
