# A fake Windows for tests/test_clean_pc.py's deep-tune runs (scripts/pc_tune.ps1 apply / -Undo / -Maintenance under pwsh on
# Linux). Unlike clean_pc_stubs.ps1 the changes really land, in a JSON "world" file ($env:LE_T_WORLD): registry values,
# services, power plans, Defender exclusions, compressed memory, the page file, network card settings, scheduled tasks.
# So the test can prove: apply changes the world, -Undo puts it back exactly, -DryRun / trading hours leave it alone.
# Every write also prints "HARNESS-CHANGE ..." (the dry-run tests look for none). Functions beat cmdlets of the same name.
if ($env:LE_T_STRICT -eq '1') { Set-StrictMode -Version 2 }

function global:_W { return (Get-Content -LiteralPath $env:LE_T_WORLD -Raw | ConvertFrom-Json -AsHashtable) }
function global:_WSave($W) { Set-Content -LiteralPath $env:LE_T_WORLD -Value ($W | ConvertTo-Json -Depth 8) }
function global:_Chg([string]$T) { [Console]::WriteLine("HARNESS-CHANGE $T") }
function global:_T-IsReg([string]$P) { return ($P -match '^(HKLM|HKCU):') }

# ---------------------------------------------------------------- registry
function global:Test-Path {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath, [Microsoft.PowerShell.Commands.TestPathType]$PathType = 'Any')
    $p = $Path; if ($LiteralPath) { $p = $LiteralPath }
    if (_T-IsReg $p) { return $true }
    Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
function global:New-Item {
    [CmdletBinding()] param([Parameter(Position = 0)][string[]]$Path, [string]$ItemType, [switch]$Force)
    if ($Path -and (_T-IsReg $Path[0])) { return }
    Microsoft.PowerShell.Management\New-Item @PSBoundParameters
}
function global:Get-ItemProperty {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath, [string]$Name)
    $p = $Path; if ($LiteralPath) { $p = $LiteralPath }
    if (-not (_T-IsReg $p)) { return (Microsoft.PowerShell.Management\Get-ItemProperty @PSBoundParameters) }
    $w = _W
    if (-not $Name) {           # every value of the key
        $o = [ordered]@{}
        foreach ($k in $w.reg.Keys) { $kk, $nn = $k.Split('|'); if ($kk -eq $p) { $o[$nn] = $w.reg[$k].v } }
        if ($o.Count -eq 0) { throw "Cannot find path $p" }
        return [pscustomobject]$o
    }
    $k = "$p|$Name"
    if (-not $w.reg.ContainsKey($k)) { throw "Property $Name does not exist at path $p." }
    $o = [ordered]@{}; $o[$Name] = $w.reg[$k].v; return [pscustomobject]$o
}
function global:Get-Item {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath, [switch]$Force)
    $p = $Path; if ($LiteralPath) { $p = $LiteralPath }
    if (-not (_T-IsReg $p)) { return (Microsoft.PowerShell.Management\Get-Item @PSBoundParameters) }
    $o = [pscustomobject]@{ Key = $p }
    $o | Add-Member -MemberType ScriptMethod -Name GetValueKind -Value { param($n) $w = _W; return $w.reg["$($this.Key)|$n"].t }
    return $o
}
function global:New-ItemProperty {
    [CmdletBinding()] param([string]$Path, [string]$LiteralPath, [string]$Name, [object]$Value, [string]$PropertyType, [switch]$Force)
    $p = $Path; if ($LiteralPath) { $p = $LiteralPath }
    $w = _W; $w.reg["$p|$Name"] = @{ v = $Value; t = $PropertyType }; _WSave $w; _Chg "reg $p $Name=$Value"
}
function global:Remove-ItemProperty {
    [CmdletBinding()] param([string]$Path, [string]$LiteralPath, [string]$Name)
    $p = $Path; if ($LiteralPath) { $p = $LiteralPath }
    $w = _W; $k = "$p|$Name"
    if (-not $w.reg.ContainsKey($k)) { throw "Property $Name does not exist at path $p." }
    $w.reg.Remove($k); _WSave $w; _Chg "reg-remove $p $Name"
}

# ---------------------------------------------------------------- services
function global:Get-Service {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Name)
    $w = _W
    if (-not $w.svc.ContainsKey($Name)) { throw "Cannot find any service with service name '$Name'." }
    return [pscustomobject]@{ Name = $Name; Status = $w.svc[$Name].status; StartType = $w.svc[$Name].start }
}
function global:Stop-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name, [switch]$Force)
    $w = _W; $w.svc[$Name].status = 'Stopped'; _WSave $w; _Chg "Stop-Service $Name" }
function global:Start-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name)
    $w = _W; $w.svc[$Name].status = 'Running'; _WSave $w; _Chg "Start-Service $Name" }
function global:Set-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name, [string]$StartupType)
    $w = _W; if ($w.neverTouch -contains $Name) { throw "harness: $Name must never be changed" }
    $w.svc[$Name].start = $StartupType; _WSave $w; _Chg "Set-Service $Name $StartupType" }

# ---------------------------------------------------------------- power (powercfg)
function global:powercfg {
    $a = @($args); $w = _W; $global:LASTEXITCODE = 0
    switch ($a[0]) {
        '/getactivescheme' { "Power Scheme GUID: $($w.power.active)  (active)" }
        '/list' { foreach ($s in $w.power.schemes) { "Power Scheme GUID: $s  (x)" } }
        '/duplicatescheme' {
            if ($w.power.canDup -notcontains $a[1]) { $global:LASTEXITCODE = 1; 'Unable to perform operation.'; return }
            $w.power.schemes += $a[2]; _WSave $w; _Chg "powercfg duplicate $($a[1]) $($a[2])"
        }
        '/changename' { _Chg "powercfg changename" }
        '/setacvalueindex' { $w.power.ac["$($a[1])|$($a[2])|$($a[3])"] = [int]$a[4]; _WSave $w; _Chg "powercfg ac $($a[3])=$($a[4])" }
        '/setactive' { if ($w.power.schemes -notcontains $a[1]) { $global:LASTEXITCODE = 1; return }; $w.power.active = $a[1]; _WSave $w; _Chg "powercfg active $($a[1])" }
        '/delete' {
            $w.power.schemes = @($w.power.schemes | Where-Object { $_ -ne $a[1] })
            foreach ($k in @($w.power.ac.Keys)) { if ($k.StartsWith("$($a[1])|")) { $w.power.ac.Remove($k) } }
            _WSave $w; _Chg "powercfg delete $($a[1])"
        }
        default { $global:LASTEXITCODE = 1 }
    }
}

# ---------------------------------------------------------------- memory, CIM, disks
function global:Get-MMAgent { [CmdletBinding()] param() $w = _W; [pscustomobject]@{ MemoryCompression = [bool]$w.mm } }
function global:Enable-MMAgent { [CmdletBinding()] param([switch]$MemoryCompression) $w = _W; $w.mm = $true; _WSave $w; _Chg 'Enable-MMAgent' }
function global:Disable-MMAgent { [CmdletBinding()] param([switch]$MemoryCompression) $w = _W; $w.mm = $false; _WSave $w; _Chg 'Disable-MMAgent' }
function global:Get-CimInstance {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$ClassName, [string]$Filter, [string]$Namespace)
    $w = _W
    switch ($ClassName) {
        'Win32_ComputerSystem' { [pscustomobject]@{ Manufacturer = 'x'; Model = $w.pc.model; PCSystemType = $w.pc.type; TotalPhysicalMemory = [double]$w.pc.ramGB * 1GB; AutomaticManagedPagefile = [bool]$w.pf.auto } }
        'Win32_PageFileSetting' { if (-not $w.pf.auto) { [pscustomobject]@{ Name = 'C:\pagefile.sys'; InitialSize = 1024; MaximumSize = [int]$w.pf.max } } }
        'Win32_Processor' { [pscustomobject]@{ Name = 'cpu'; NumberOfCores = 2; NumberOfLogicalProcessors = 4; MaxClockSpeed = 1498; LoadPercentage = 50 } }
        'Win32_OperatingSystem' { [pscustomobject]@{ TotalVisibleMemorySize = 3774873; FreePhysicalMemory = 377487 } }
        default { throw "harness: Get-CimInstance $ClassName not stubbed" }
    }
}
function global:Set-CimInstance { [CmdletBinding()] param($InputObject, [hashtable]$Property)
    $w = _W; $w.pf.auto = [bool]$Property['AutomaticManagedPagefile']; _WSave $w; _Chg "pagefile auto=$($w.pf.auto)" }
function global:Get-PhysicalDisk { [CmdletBinding()] param() [pscustomobject]@{ FriendlyName = 'disk'; MediaType = 'SSD'; BusType = 'NVMe'; Size = 128GB } }
function global:Get-Printer { [CmdletBinding()] param() $w = _W; foreach ($p in $w.printers) { [pscustomobject]@{ Name = $p } } }

# ---------------------------------------------------------------- Defender
function global:Get-MpPreference { [CmdletBinding()] param() $w = _W; [pscustomobject]@{ ExclusionPath = @($w.mp) } }
function global:Add-MpPreference { [CmdletBinding()] param([string[]]$ExclusionPath) $w = _W; $w.mp = @($w.mp) + $ExclusionPath; _WSave $w; _Chg "Add-MpPreference $ExclusionPath" }
function global:Remove-MpPreference { [CmdletBinding()] param([string[]]$ExclusionPath)
    $w = _W; if ($w.failMpRemove) { throw 'harness: Remove-MpPreference failed' }
    $w.mp = @($w.mp | Where-Object { $ExclusionPath -notcontains $_ }); _WSave $w; _Chg "Remove-MpPreference $ExclusionPath" }
function global:Start-MpScan { [CmdletBinding()] param([string]$ScanType) _Chg 'Start-MpScan' }
function global:dism.exe { _Chg "dism $args"; $global:LASTEXITCODE = 0 }

# ---------------------------------------------------------------- network
function global:Get-NetAdapter { [CmdletBinding()] param([switch]$Physical) $w = _W; foreach ($n in $w.nics) { [pscustomobject]@{ Name = $n; Status = 'Up' } } }
function global:Get-NetAdapterAdvancedProperty { [CmdletBinding()] param([string]$Name)
    $w = _W; foreach ($k in $w.netadv.Keys) { $n, $d = $k.Split('|'); if ($n -eq $Name) { [pscustomobject]@{ Name = $n; DisplayName = $d; DisplayValue = $w.netadv[$k].v; ValidDisplayValues = @($w.netadv[$k].valid) } } } }
function global:Set-NetAdapterAdvancedProperty { [CmdletBinding()] param([string]$Name, [string]$DisplayName, [string]$DisplayValue)
    $w = _W; $w.netadv["$Name|$DisplayName"].v = $DisplayValue; _WSave $w; _Chg "netadv $Name $DisplayName=$DisplayValue" }
function global:Get-NetAdapterPowerManagement { [CmdletBinding()] param([string]$Name)
    $w = _W; if (-not $w.netpm.ContainsKey($Name)) { throw 'not supported' }; [pscustomobject]@{ Name = $Name; AllowComputerToTurnOffDevice = $w.netpm[$Name] } }
function global:Set-NetAdapterPowerManagement { [CmdletBinding()] param([string]$Name, [string]$AllowComputerToTurnOffDevice)
    $w = _W; $w.netpm[$Name] = $AllowComputerToTurnOffDevice; _WSave $w; _Chg "netpm $Name=$AllowComputerToTurnOffDevice" }

# ---------------------------------------------------------------- scheduled tasks
function global:New-ScheduledTaskAction { [CmdletBinding()] param([string]$Execute, [string]$Argument, [string]$WorkingDirectory) [pscustomobject]@{ Execute = $Execute; Arguments = $Argument } }
function global:New-ScheduledTaskTrigger { [CmdletBinding()] param([switch]$Daily, [switch]$Once, [switch]$Weekly, [switch]$AtLogOn, [string]$User, $At, $DaysOfWeek, $RepetitionInterval, $RepetitionDuration)
    [pscustomobject]@{ Kind = "$(if ($Daily) { 'daily' } elseif ($Once) { 'once' } elseif ($Weekly) { 'weekly' } else { 'logon' })"; Repetition = $RepetitionInterval; DaysOfWeek = "$DaysOfWeek"; At = "$At" } }
function global:New-ScheduledTaskSettingsSet { [CmdletBinding()] param([switch]$AllowStartIfOnBatteries, [switch]$DontStopIfGoingOnBatteries, [switch]$StartWhenAvailable, $MultipleInstances, $ExecutionTimeLimit, $Priority) [pscustomobject]@{ Priority = $Priority } }
function global:New-ScheduledTaskPrincipal { [CmdletBinding()] param([string]$UserId, [string]$LogonType, [string]$RunLevel) [pscustomobject]@{ UserId = $UserId; LogonType = $LogonType; RunLevel = $RunLevel } }
function global:New-ScheduledTask { [CmdletBinding()] param($Action, $Trigger, $Settings, $Principal, [string]$Description) [pscustomobject]@{ Action = $Action; Trigger = @($Trigger); Principal = $Principal } }
function global:Register-ScheduledTask { [CmdletBinding()] param([string]$TaskName, $InputObject)
    $w = _W; $w.tasks[$TaskName] = @{ path = '\'; state = 'Ready'; args = "$($InputObject.Action.Arguments)"; user = "$($InputObject.Principal.UserId)"; logon = "$($InputObject.Principal.LogonType)"; triggers = @($InputObject.Trigger | ForEach-Object { $_.Kind }) }
    _WSave $w; _Chg "Register-ScheduledTask $TaskName" }
function global:Get-ScheduledTask { [CmdletBinding()] param([string]$TaskName, [string]$TaskPath)
    $w = _W
    foreach ($k in $w.tasks.Keys) {
        $t = $w.tasks[$k]
        if (($TaskName -and $k -ne $TaskName) -or ($TaskPath -and $t.path -ne $TaskPath)) { continue }
        [pscustomobject]@{ TaskName = $k; TaskPath = $t.path; State = $t.state }; $found = $true
    }
    if ($TaskName -and -not $w.tasks.ContainsKey($TaskName)) { Write-Error "No MSFT_ScheduledTask objects found with property 'TaskName' equal to '$TaskName'." }
}
function global:Unregister-ScheduledTask { [CmdletBinding()] param([string]$TaskName, [switch]$Confirm) $w = _W; $w.tasks.Remove($TaskName); _WSave $w; _Chg "Unregister-ScheduledTask $TaskName" }
function global:Disable-ScheduledTask { [CmdletBinding()] param([string]$TaskName, [string]$TaskPath) $w = _W; $w.tasks[$TaskName].state = 'Disabled'; _WSave $w; _Chg "Disable-ScheduledTask $TaskName"; [pscustomobject]@{} }
function global:Enable-ScheduledTask { [CmdletBinding()] param([string]$TaskName, [string]$TaskPath) $w = _W; $w.tasks[$TaskName].state = 'Ready'; _WSave $w; _Chg "Enable-ScheduledTask $TaskName"; [pscustomobject]@{} }
function global:Start-Process { [CmdletBinding()] param([Parameter(Position = 0)]$FilePath, $ArgumentList, $Verb, [switch]$PassThru, [switch]$Wait) _Chg "Start-Process $FilePath (UAC)" }
