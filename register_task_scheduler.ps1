<#
.SYNOPSIS
    Registra la tarea programada diaria en Windows 11 (11:00 AM y 06:00 PM) para actualizar
    automáticamente los precios en playa de INFOMAR - IMARPE.
    Incluye StartWhenAvailable para ejecutar la tarea apenas se encienda la laptop si estuvo apagada.
#>

$ErrorActionPreference = "Stop"

$TaskName = "IMARPE_INFOMAR_Precios_Diarios"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ProjectDir "run_extractor.bat"

if (-not (Test-Path $BatPath)) {
    throw "No se encontró el archivo $BatPath"
}

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ProjectDir
$TriggerMorning = New-ScheduledTaskTrigger -Daily -At 11:00AM
$TriggerEvening = New-ScheduledTaskTrigger -Daily -At 6:00PM

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -NetworkOnly `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerMorning, $TriggerEvening) `
    -Settings $Settings `
    -Description "Extracción diaria nacional de precios en playa y especies por puerto desde INFOMAR (IMARPE Perú)." `
    -Force | Out-Null

Write-Host "Tarea programada '$TaskName' registrada exitosamente (11:00 AM y 06:00 PM diario)." -ForegroundColor Green
Write-Host "Para probarla de inmediato ejecuta: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
