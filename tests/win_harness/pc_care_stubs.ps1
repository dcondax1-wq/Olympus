# Windows stubs for tests/test_pc_care.py: dot-sourced before scripts/pc_care.ps1 runs under pwsh on Linux. It builds on the fake
# Windows of tests/win_harness/pc_tune_world.ps1 (changes really land in the JSON world $env:LE_T_WORLD: registry, services, power
# plans, scheduled tasks) and adds what PC Care reads or sets: powercfg /query + the DC values, the CIM classes of the health
# check (boot time, memory, battery, thermal zone), Get-Counter, and a UAC Start-Process that really runs the elevated child.
. (Join-Path $PSScriptRoot 'pc_tune_world.ps1')

# ---------------------------------------------------------------- power: AC and DC values + /query (the world's own powercfg lacks both)
function global:powercfg {
    $a = @($args); $w = _W; $global:LASTEXITCODE = 0
    if (-not $w.power.ContainsKey('dc')) { $w.power['dc'] = @{} }
    switch ($a[0]) {
        '/getactivescheme' { "Power Scheme GUID: $($w.power.active)  (active)" }
        '/list' { foreach ($s in $w.power.schemes) { "Power Scheme GUID: $s  (x)" } }
        '/duplicatescheme' {
            if ($w.power.canDup -notcontains $a[1]) { $global:LASTEXITCODE = 1; 'Unable to perform operation.'; return }
            $w.power.schemes += $a[2]
            foreach ($k in @($w.power.ac.Keys)) { if ($k.StartsWith("$($a[1])|")) { $w.power.ac["$($a[2])|" + $k.Substring($a[1].Length + 1)] = $w.power.ac[$k] } }
            _WSave $w; _Chg "powercfg duplicate $($a[1]) $($a[2])"
        }
        '/changename' { _Chg "powercfg changename" }
        '/setacvalueindex' {
            if ($w.power.unsupported -contains $a[3]) { $global:LASTEXITCODE = 1; return }
            $w.power.ac["$($a[1])|$($a[2])|$($a[3])"] = [int]$a[4]; _WSave $w; _Chg "powercfg ac $($a[3])=$($a[4])"
        }
        '/setdcvalueindex' {
            if ($w.power.unsupported -contains $a[3]) { $global:LASTEXITCODE = 1; return }
            $w.power.dc["$($a[1])|$($a[2])|$($a[3])"] = [int]$a[4]; _WSave $w; _Chg "powercfg dc $($a[3])=$($a[4])"
        }
        '/setactive' { if ($w.power.schemes -notcontains $a[1]) { $global:LASTEXITCODE = 1; return }; $w.power.active = $a[1]; _WSave $w; _Chg "powercfg active $($a[1])" }
        '/delete' {
            $w.power.schemes = @($w.power.schemes | Where-Object { $_ -ne $a[1] })
            foreach ($k in @($w.power.ac.Keys)) { if ($k.StartsWith("$($a[1])|")) { $w.power.ac.Remove($k) } }
            foreach ($k in @($w.power.dc.Keys)) { if ($k.StartsWith("$($a[1])|")) { $w.power.dc.Remove($k) } }
            _WSave $w; _Chg "powercfg delete $($a[1])"
        }
        '/query' {
            $k = "$($a[1])|$($a[2])|$($a[3])"
            $acv = $null; $dcv = $null
            if ($w.power.ac.ContainsKey($k)) { $acv = [int]$w.power.ac[$k] } elseif ($w.power.ContainsKey('defaults') -and $w.power.defaults.ContainsKey($a[3])) { $acv = [int]$w.power.defaults[$a[3]].ac }
            if ($w.power.dc.ContainsKey($k)) { $dcv = [int]$w.power.dc[$k] } elseif ($w.power.ContainsKey('defaults') -and $w.power.defaults.ContainsKey($a[3])) { $dcv = [int]$w.power.defaults[$a[3]].dc }
            if ($null -eq $acv -and $null -eq $dcv) { $global:LASTEXITCODE = 1; return }
            "  Power Setting GUID: $($a[3])"
            "    Current AC Power Setting Index: 0x{0:x8}" -f $acv
            "    Current DC Power Setting Index: 0x{0:x8}" -f $dcv
        }
        default { $global:LASTEXITCODE = 1 }
    }
}

# ---------------------------------------------------------------- CIM for the health check and the facts
function global:Get-CimInstance {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$ClassName, [string]$Filter, [string]$Namespace)
    $w = _W
    switch ($ClassName) {
        'Win32_ComputerSystem' { [pscustomobject]@{ Manufacturer = 'x'; Model = $w.pc.model; PCSystemType = $w.pc.type; TotalPhysicalMemory = [double]$w.pc.ramGB * 1GB; AutomaticManagedPagefile = [bool]$w.pf.auto } }
        'Win32_PageFileSetting' { if (-not $w.pf.auto) { [pscustomobject]@{ Name = 'C:\pagefile.sys'; InitialSize = 1024; MaximumSize = [int]$w.pf.max } } }
        'Win32_Processor' { [pscustomobject]@{ Name = 'cpu'; NumberOfCores = 2; NumberOfLogicalProcessors = 4; MaxClockSpeed = 1498; LoadPercentage = 50 } }
        'Win32_OperatingSystem' {
            $h = if ($w.ContainsKey('health')) { $w.health } else { @{} }
            $up = if ($h.ContainsKey('uptimeDays')) { [double]$h.uptimeDays } else { 2.0 }
            $used = if ($h.ContainsKey('ramUsedPct')) { [double]$h.ramUsedPct } else { 50.0 }
            [pscustomobject]@{ TotalVisibleMemorySize = 4000000.0; FreePhysicalMemory = 4000000.0 * (1 - $used / 100.0); LastBootUpTime = (Get-Date).AddDays(-$up) }
        }
        'Win32_Battery' {
            if ($w.ContainsKey('battery') -and $w.battery) { [pscustomobject]@{ EstimatedChargeRemaining = [int]$w.battery.pct; BatteryStatus = $(if ($w.battery.plugged) { 2 } else { 1 }) } }
        }
        'MSAcpi_ThermalZoneTemperature' {
            if ($w.ContainsKey('health') -and $w.health.ContainsKey('tempC') -and $null -ne $w.health.tempC) { [pscustomobject]@{ CurrentTemperature = ([double]$w.health.tempC + 273.15) * 10.0 } }
            else { throw 'Not supported' }
        }
        default { throw "harness: Get-CimInstance $ClassName not stubbed" }
    }
}
function global:Get-Counter {
    [CmdletBinding()] param([string[]]$Counter)
    $w = _W
    if ($Counter[0] -like '*Processor Performance*') {
        if ($w.ContainsKey('health') -and $w.health.ContainsKey('perfPct')) { return [pscustomobject]@{ CounterSamples = @([pscustomobject]@{ CookedValue = [double]$w.health.perfPct }) } }
    }
    throw 'harness: counter not available'
}

# ---------------------------------------------------------------- UAC: the elevated child really runs (same pwsh + stubs); LE_T_UAC=no declines
function global:Start-Process {
    [CmdletBinding()] param([Parameter(Position = 0)]$FilePath, $ArgumentList, $Verb, [switch]$PassThru, [switch]$Wait)
    [Console]::WriteLine("HARNESS-UAC $FilePath $Verb")
    if ($env:LE_T_UAC -eq 'no') { throw 'The operation was canceled by the user' }
    $a = @($ArgumentList | ForEach-Object { "$_".Trim('"') })
    $env:LE_T_ELEVATED = '1'
    $out = & $env:LE_T_PWSH -NoProfile -NoLogo -NonInteractive -Command ". '$env:LE_T_STUBS'; & '$($a[4])' $($a[5..($a.Count - 1)] | ForEach-Object { if ($_ -like '-*') { $_ } else { "'$_'" } })" 2>&1
    $code = $LASTEXITCODE
    $env:LE_T_ELEVATED = '0'
    foreach ($l in $out) { [Console]::WriteLine("CHILD| $l") }
    return [pscustomobject]@{ ExitCode = $code }
}
