# Fallout: New Vegas session watcher (Dan, 2026-11-14).
#
# Waits quietly for FalloutNV.exe. While it runs, records its memory every 10 s. When it exits,
# saves that session's logs into Documents\My Games\FalloutNV\SessionLogs\<start time>\ with a
# summary.txt, so a crash's evidence is never overwritten by the next launch. Keeps the newest 30.
#
# Runs at sign-in from a hidden shortcut in the Startup folder ("FNV Session Watcher"). One copy
# at a time. To stop it for good: delete that shortcut (and end the powershell process).
#
# summary.txt answers the usual first questions: how long the session ran, whether it crashed
# (crash-logger file written this session, or a Windows "Application Error" for FalloutNV.exe),
# peak memory against the 32-bit 4 GB ceiling, and what the game was doing last (save/load).

param([string]$TestStart)   # test: summarize the session that started at this time, then exit

$ErrorActionPreference = 'SilentlyContinue'
$game    = 'C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas'
$outRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\FalloutNV\SessionLogs'
$keep    = 30
$sample  = 10

$mutex = New-Object System.Threading.Mutex($false, 'Global\FNVSessionWatcher')
if (-not $TestStart -and -not $mutex.WaitOne(0)) { exit }   # already running

New-Item -ItemType Directory -Force $outRoot | Out-Null

function Save-Session($start, $samples, $proc) {
    $end  = Get-Date
    $dir  = Join-Path $outRoot $start.ToString('yyyy-MM-dd_HHmmss')
    New-Item -ItemType Directory -Force $dir | Out-Null
    Start-Sleep -Seconds 5   # let the crash logger and the game finish writing

    $samples | Export-Csv (Join-Path $dir 'memory.csv') -NoTypeInformation

    # logs written this session
    $files = 'nvse.log','falloutnv_error.log','falloutnv_havok.log','CobbCrashLogger.log','CrashLogger.log','ScanNullFix.log',
             'FalloutNV_d3d9.log','FalloutNV_dxgi.log','nvse_steam_loader.log','mcm.log','ShowOffNVSE.log'
    foreach ($f in $files) {
        $p = Join-Path $game $f
        if ((Test-Path $p) -and (Get-Item $p).LastWriteTime -ge $start.AddMinutes(-1)) {
            if ((Get-Item $p).Length -gt 5MB) { Get-Content $p -Tail 20000 | Set-Content (Join-Path $dir $f) }
            else { Copy-Item $p $dir }
        }
    }
    foreach ($sub in 'Crash Logs','CrashLogs','Data\NVSE\Plugins\CrashLogs','logs') {
        $p = Join-Path $game $sub
        if (Test-Path $p) {
            Get-ChildItem $p -File | Where-Object { $_.LastWriteTime -ge $start.AddMinutes(-1) } |
                ForEach-Object { Copy-Item $_.FullName (Join-Path $dir ((($sub -replace '[\\ ]','_') + '_' + $_.Name))) }
        }
    }
    Copy-Item (Join-Path $env:LOCALAPPDATA 'FalloutNV\plugins.txt') $dir

    # crashed?
    $crashLog = Join-Path $game 'CobbCrashLogger.log'
    $loggerCrash = (Test-Path $crashLog) -and (Get-Item $crashLog).LastWriteTime -ge $start -and
                   ((Get-Content $crashLog -Raw) -match 'Exception')
    # Yvile's Crash Logger writes 'Crash Logs\CrashLogger.<time>.log' (older loggers: CrashLogs)
    $newCrashFiles = @(Get-ChildItem (Join-Path $game 'Crash Logs'), (Join-Path $game 'CrashLogs') -File |
                       Where-Object { $_.LastWriteTime -ge $start })
    $winErr = Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=$start} |
              Where-Object { $_.Message -match 'FalloutNV.exe' } | Select-Object -First 1
    $crashed = $loggerCrash -or $newCrashFiles.Count -gt 0 -or $winErr

    $peakPriv = ($samples | Measure-Object private_mb -Maximum).Maximum
    $peakVirt = ($samples | Measure-Object virtual_mb -Maximum).Maximum
    $peakWS   = ($samples | Measure-Object working_set_mb -Maximum).Maximum
    $last     = $samples | Select-Object -Last 1
    $nvse     = Join-Path $game 'nvse.log'
    $lastIO   = Select-String -Path $nvse -Pattern 'DoLoadGameHook|DoSaveGameHook|DoPreLoadGameHook' | Select-Object -Last 3
    $loads    = @(Select-String -Path $nvse -Pattern 'DoLoadGameHook').Count

    $s = @()
    $s += "Fallout: New Vegas session $($start.ToString('yyyy-MM-dd HH:mm:ss')) -> $($end.ToString('HH:mm:ss'))  ($([int]($end-$start).TotalMinutes) min)"
    $s += "Exit: " + $(if ($crashed) { 'CRASH' } else { 'normal (no crash recorded)' })
    if ($loggerCrash)      { $s += "  crash logger: " + ((Get-Content $crashLog | Select-String 'Exception|GAME CRASHED AT' | ForEach-Object { $_.Line.Trim() }) -join ' / ') }
    foreach ($cf in $newCrashFiles) {
        $s += "  crash log: $($cf.Name)"
        $s += (Get-Content $cf.FullName -TotalCount 40 | Select-String '^Exception:|^Thread:' | ForEach-Object { '    ' + $_.Line.Trim() })
        if ((Get-Content $cf.FullName -Raw) -match 'LdrShutdownProcess') { $s += '    (crashed while the game was closing: harmless)' }
    }
    if ($winErr)           { $s += "  Windows: " + (($winErr.Message -split "`n" | Select-Object -First 5 | ForEach-Object { $_.Trim() }) -join ' | ') }
    $s += ""
    $s += "Memory (32-bit game, hard ceiling 4096 MB of address space):"
    if ($samples.Count -eq 0) { $s += "  not recorded (the watcher wasn't running during this session)" }
    else { $s += "  peak virtual (address space) $peakVirt MB   peak private $peakPriv MB   peak working set $peakWS MB" }
    if ($last) { $s += "  last sample at $($last.time): virtual $($last.virtual_mb) MB, private $($last.private_mb) MB" }
    if ($peakVirt -gt 3700) { $s += "  WARNING: address space came within ~400 MB of the ceiling: out-of-memory is a likely cause." }
    $s += ""
    $s += "Saves loaded this session: $loads"
    $s += "Last save/load events in nvse.log:"
    $lastIO | ForEach-Object { $s += "  " + $_.Line.Trim() }
    $s | Set-Content (Join-Path $dir 'summary.txt')

    # keep the newest $keep sessions
    Get-ChildItem $outRoot -Directory | Sort-Object Name -Descending | Select-Object -Skip $keep |
        Remove-Item -Recurse -Force
}

if ($TestStart) {
    $outRoot = Join-Path $outRoot '_test'
    Save-Session ([datetime]$TestStart) @() $null
    exit
}

while ($true) {
    $proc = Get-Process FalloutNV | Select-Object -First 1
    if (-not $proc) { Start-Sleep -Seconds 15; continue }

    $start = $proc.StartTime
    $samples = New-Object System.Collections.Generic.List[object]
    while (-not $proc.HasExited) {
        $proc.Refresh()
        if ($proc.HasExited) { break }
        $samples.Add([pscustomobject]@{
            time           = (Get-Date).ToString('HH:mm:ss')
            working_set_mb = [int]($proc.WorkingSet64 / 1MB)
            private_mb     = [int]($proc.PrivateMemorySize64 / 1MB)
            virtual_mb     = [int]($proc.VirtualMemorySize64 / 1MB)
            handles        = $proc.HandleCount
        })
        Start-Sleep -Seconds $sample
    }
    Save-Session $start $samples $proc
}
