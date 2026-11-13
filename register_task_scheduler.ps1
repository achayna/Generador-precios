<#
.SYNOPSIS
    Registra la tarea programada IMARPE_INFOMAR_Precios_Diarios en Windows 11:
      - Horarios diarios: 08:35, 10:00, 11:30, 14:30 y 18:00
      - Al iniciar sesión (AtLogOn) + recuperación automática (StartWhenAvailable)
      - Sincroniza con origin/main (git pull --rebase) y publica output/ en GitHub.
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
    (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME),
    (New-ScheduledTaskTrigger -Daily -At 08:35AM),
    (New-ScheduledTaskTrigger -Daily -At 10:00AM),
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
    -Description "Extracción y publicación GitHub (08:35, 10:00, 11:30, 14:30, 18:00 + AtLogOn) de precios en playa INFOMAR - IMARPE." `
    -Force | Out-Null

Write-Host "Tarea '$TaskName' registrada con éxito (08:35, 10:00, 11:30, 14:30, 18:00 + AtLogOn -> auto-push GitHub)." -ForegroundColor Green
