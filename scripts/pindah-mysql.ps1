param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $project '.venv\Scripts\python.exe'
$portText = & $python -c "import sys; from pathlib import Path; from dotenv import dotenv_values; print(dotenv_values(Path(sys.argv[1]) / '.env').get('PORT') or '5000')" $project
if ($LASTEXITCODE -ne 0 -or $portText -notmatch '^\d+$') { throw 'Tidak dapat membaca PORT dari konfigurasi.' }
$appPort = [int]$portText

function Get-AppListeners {
    @(Get-NetTCPConnection -LocalPort $appPort -State Listen -ErrorAction SilentlyContinue)
}

$servers = @()
$parents = @()
foreach ($ownerId in (Get-AppListeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
    $server = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $ownerId)
    $parent = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $server.ParentProcessId)
    if ($server.CommandLine -notmatch '\brun\.py\b' -or
        ($server.ExecutablePath -ne $python -and $parent.ExecutablePath -ne $python)) {
        throw "Port $appPort dipakai proses yang identitasnya tidak sesuai. Hentikan server PSB sendiri sebelum migrasi."
    }
    $servers += $server.ProcessId
    if ($parent.ExecutablePath -eq $python -and $parent.CommandLine -match '\brun\.py\b') {
        $parents += $parent.ProcessId
    }
}
$workers = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match [regex]::Escape($python) -and
    $_.CommandLine -match 'manage\.py"?\s+(worker|reminders)\b'
})

$restart = $false
try {
    $restart = $true
    foreach ($processId in (@($servers) + @($parents) + @($workers.ProcessId) | Select-Object -Unique)) {
        if ($processId -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
            Write-Host "Menghentikan proses PSB $processId..."
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Wait-Process -Id $processId -Timeout 5 -ErrorAction SilentlyContinue
        }
    }
    # Tunggu Windows selesai melepas socket setelah proses dihentikan.
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        $remaining = @(Get-AppListeners)
        if ($remaining.Count -eq 0) { break }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($remaining.Count -gt 0) {
        $restart = $false
        throw "Port $appPort masih dipakai. Migrasi dibatalkan dan server tambahan tidak dijalankan."
    }
    Write-Host "Server sudah berhenti dan port $appPort sudah bebas."
    if ($CheckOnly) {
        Write-Host 'Pemeriksaan penghentian berhasil; database tidak diubah.'
    } else {
        & $python (Join-Path $PSScriptRoot 'migrate_mysql.py')
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Migrasi belum selesai. Baca pesan kesalahan di atas sebelum mencoba lagi.'
        }
    }
} finally {
    if ($restart -and @(Get-AppListeners).Count -eq 0) {
        $process = Start-Process -FilePath $python -ArgumentList 'run.py' -WorkingDirectory $project -WindowStyle Hidden -RedirectStandardOutput (Join-Path $project 'instance/server.stdout.log') -RedirectStandardError (Join-Path $project 'instance/server.stderr.log') -PassThru
        $process.Id | Set-Content (Join-Path $project 'instance/server.pid')
        Write-Host 'Server dijalankan kembali. Periksa hasil migrasi di atas.'
    }
}
