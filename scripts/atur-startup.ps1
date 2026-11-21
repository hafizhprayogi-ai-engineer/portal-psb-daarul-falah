param([switch]$Disable)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskName = 'PSB Daarul Falah - Portal dan Sheets'
if ($Disable) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host 'Peluncuran otomatis dinonaktifkan. Proses yang sedang berjalan tidak dihentikan.'
    return
}
$python = Join-Path $project '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Python virtual environment tidak ditemukan.' }
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + (Join-Path $project 'scripts\startup_portal.py') + '"') -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = 'PT20S'
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2)
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Menjalankan portal PSB dan sinkronisasi Sheets setelah login Windows. Tanpa password tersimpan dan tanpa akses administrator pada proses aplikasi.'
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host 'Peluncuran otomatis aktif 20 detik setelah login Windows.'
