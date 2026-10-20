# Windows stub layer for tests/test_win_scripts.py (loaded as the pwsh profile of a sandbox HOME, so every script started
# through the fake powershell.exe gets it). Functions beat cmdlets / exes of the same name. Every stub appends one line
# to $env:LE_T_LOG ("name<TAB>arg<TAB>arg"); registry, scheduled tasks and shortcuts live as JSON files in the sandbox.
# Nothing here touches the real machine: git is a fake, NinjaTrader is a fake path, UAC is simulated.
if ($env:LE_T_STRICT -eq '1') { Set-StrictMode -Version 2 }
$ErrorActionPreference = 'Continue'

function global:_T-Log([string]$Name, [object[]]$A) {
    $parts = @($Name) + @($A | ForEach-Object { "$_" })
    [System.IO.File]::AppendAllText($env:LE_T_LOG, (($parts -join "`t") + "`n"))
}

# ---------------------------------------------------------------------------------------------- native tools
function global:powercfg { _T-Log 'powercfg' $args; $global:LASTEXITCODE = 0 }
function global:schtasks { _T-Log 'schtasks' $args; $global:LASTEXITCODE = 0 }
function global:reg { _T-Log 'reg' $args; $global:LASTEXITCODE = 0 }

# ---------------------------------------------------------------------------------------------- registry (HKLM: / HKCU:)
function global:_T-IsReg([string]$P) { return ($P -match '^(HKLM|HKCU|HKCR|HKU|Registry)::?') }
function global:_T-RegLoad {
    if (Microsoft.PowerShell.Management\Test-Path -LiteralPath $env:LE_T_REG) {
        return (Get-Content -Raw -LiteralPath $env:LE_T_REG | ConvertFrom-Json -AsHashtable)
    }
    return @{}
}
function global:_T-RegSave($Db) { $Db | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $env:LE_T_REG }

function global:Test-Path {
    [CmdletBinding()]
    param([Parameter(Position = 0, ValueFromPipeline = $true)][string[]]$Path, [string[]]$LiteralPath,
          [Microsoft.PowerShell.Commands.TestPathType]$PathType = 'Any', [switch]$IsValid)
    $p = @($Path) + @($LiteralPath) | Where-Object { $_ } | Select-Object -First 1
    if ($p -and (_T-IsReg $p)) { return (_T-RegLoad).ContainsKey($p) }
    Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
function global:New-Item {
    [CmdletBinding()]
    param([Parameter(Position = 0)][string[]]$Path, [string]$ItemType, [object]$Value, [switch]$Force, [string]$Name)
    if ($Path -and (_T-IsReg $Path[0])) {
        $db = _T-RegLoad; if (-not $db.ContainsKey($Path[0])) { $db[$Path[0]] = @{} }; _T-RegSave $db
        _T-Log 'New-Item' @($Path[0]); return [pscustomobject]@{ PSPath = $Path[0] }
    }
    Microsoft.PowerShell.Management\New-Item @PSBoundParameters
}
function global:Set-ItemProperty {
    [CmdletBinding()]
    param([Parameter(Position = 0)][string[]]$Path, [Parameter(Position = 1)][string]$Name, [Parameter(Position = 2)][object]$Value,
          [ValidateSet('String', 'ExpandString', 'Binary', 'DWord', 'MultiString', 'QWord', 'Unknown')][string]$Type)
    if (-not (_T-IsReg $Path[0])) { throw "harness: Set-ItemProperty only stubbed for the registry ($Path)" }
    $db = _T-RegLoad
    if (-not $db.ContainsKey($Path[0])) { throw "Cannot find path '$($Path[0])' because it does not exist." }
    if ($Type -eq 'DWord' -and -not ($Value -is [int] -or $Value -is [long])) { throw "harness: DWord value for $Name is a $($Value.GetType().Name), not an int" }
    $db[$Path[0]][$Name] = @{ type = $Type; value = $Value }; _T-RegSave $db
    _T-Log 'Set-ItemProperty' @($Path[0], $Name, $Type, $Value)
}
function global:Get-ItemProperty {
    [CmdletBinding()]
    param([Parameter(Position = 0)][string[]]$Path, [Parameter(Position = 1)][string[]]$Name, [string[]]$LiteralPath)
    $p = @($Path) + @($LiteralPath) | Where-Object { $_ } | Select-Object -First 1
    if ($p -and (_T-IsReg $p)) {
        $db = _T-RegLoad
        if ($db.ContainsKey($p)) {
            $o = [ordered]@{}; foreach ($k in $db[$p].Keys) { $o[$k] = $db[$p][$k].value }
            if ($Name -and -not $o.Contains($Name[0])) { Write-Error "Property $($Name[0]) does not exist at path $p."; return }
            return [pscustomobject]$o
        }
        if ($p -notmatch '\*') { Write-Error "Cannot find path '$p' because it does not exist." }
        return
    }
    Microsoft.PowerShell.Management\Get-ItemProperty @PSBoundParameters
}

# ---------------------------------------------------------------------------------------------- ScheduledTasks module
function global:New-ScheduledTaskAction {
    [CmdletBinding()] param([Parameter(Mandatory = $true)][string]$Execute, [string]$Argument, [string]$WorkingDirectory, [string]$Id)
    [pscustomobject]@{ Execute = $Execute; Arguments = $Argument; WorkingDirectory = $WorkingDirectory }
}
function global:New-ScheduledTaskTrigger {
    [CmdletBinding(DefaultParameterSetName = 'Once')]
    param([Parameter(ParameterSetName = 'AtLogon', Mandatory = $true)][switch]$AtLogOn,
          [Parameter(ParameterSetName = 'AtLogon')][string]$User,
          [Parameter(ParameterSetName = 'Daily', Mandatory = $true)][switch]$Daily,
          [Parameter(ParameterSetName = 'Once', Mandatory = $true)][switch]$Once,
          [Parameter(ParameterSetName = 'Daily', Mandatory = $true)][Parameter(ParameterSetName = 'Once', Mandatory = $true)][datetime]$At,
          [Parameter(ParameterSetName = 'Once')][timespan]$RepetitionInterval,
          [Parameter(ParameterSetName = 'Once')][timespan]$RepetitionDuration)
    $rep = [pscustomobject]@{ Interval = $null; Duration = $null }
    if ($PSBoundParameters.ContainsKey('RepetitionInterval')) {
        $rep = [pscustomobject]@{ Interval = [System.Xml.XmlConvert]::ToString($RepetitionInterval); Duration = [System.Xml.XmlConvert]::ToString($RepetitionDuration) }
    }
    [pscustomobject]@{ Kind = $PSCmdlet.ParameterSetName; User = $User; At = $(if ($PSBoundParameters.ContainsKey('At')) { $At.ToString('s') } else { $null }); Repetition = $rep;
                       CimClass = [pscustomobject]@{ CimClassName = "MSFT_Task$($PSCmdlet.ParameterSetName)Trigger" } }
}
function global:New-ScheduledTaskSettingsSet {
    [CmdletBinding()]
    param([switch]$AllowStartIfOnBatteries, [switch]$DontStopIfGoingOnBatteries, [switch]$StartWhenAvailable, [timespan]$ExecutionTimeLimit,
          [int]$RestartCount, [timespan]$RestartInterval, [ValidateSet('Parallel', 'Queue', 'IgnoreNew', 'StopExisting')][string]$MultipleInstances,
          [switch]$DontStopOnIdleEnd, [switch]$WakeToRun, [switch]$Hidden)
    [pscustomobject]@{ ExecutionTimeLimit = $(if ($PSBoundParameters.ContainsKey('ExecutionTimeLimit')) { [System.Xml.XmlConvert]::ToString($ExecutionTimeLimit) } else { 'PT72H' })
                       RestartCount = $RestartCount; RestartInterval = $(if ($RestartInterval) { [System.Xml.XmlConvert]::ToString($RestartInterval) } else { $null })
                       MultipleInstances = $MultipleInstances; DisallowStartIfOnBatteries = -not $AllowStartIfOnBatteries
                       StopIfGoingOnBatteries = -not $DontStopIfGoingOnBatteries; StartWhenAvailable = [bool]$StartWhenAvailable; WakeToRun = [bool]$WakeToRun }
}
function global:New-ScheduledTaskPrincipal {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$UserId, [ValidateSet('None', 'Password', 'S4U', 'Interactive', 'Group', 'ServiceAccount', 'InteractiveOrPassword')][string]$LogonType,
          [ValidateSet('Limited', 'Highest')][string]$RunLevel)
    [pscustomobject]@{ UserId = $UserId; LogonType = $LogonType; RunLevel = $RunLevel }
}
function global:New-ScheduledTask {
    [CmdletBinding()] param([object[]]$Action, [object[]]$Trigger, [object]$Settings, [object]$Principal, [string]$Description)
    [pscustomobject]@{ Actions = @($Action); Triggers = @($Trigger); Settings = $Settings; Principal = $Principal; Description = $Description }
}
function global:_T-TaskFile([string]$N) { Join-Path $env:LE_T_TASKS "$N.json" }
function global:Register-ScheduledTask {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true, Position = 0)][string]$TaskName, [Parameter(Mandatory = $true)][object]$InputObject, [switch]$Force, [string]$TaskPath)
    if ($env:LE_T_TASK_DENY -eq '1' -and -not $env:LE_T_ELEVATED) { throw "Access is denied." }
    if (Microsoft.PowerShell.Management\Test-Path -LiteralPath (_T-TaskFile $TaskName)) { throw "Cannot create a file when that file already exists." }
    $InputObject | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (_T-TaskFile $TaskName)
    _T-Log 'Register-ScheduledTask' @($TaskName)
    [pscustomobject]@{ TaskName = $TaskName; State = 'Ready' }
}
function global:Get-ScheduledTask {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$TaskName, [string]$TaskPath)
    $f = _T-TaskFile $TaskName
    if (-not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $f)) { Write-Error "No MSFT_ScheduledTask objects found with property 'TaskName' equal to '$TaskName'."; return }
    $t = Get-Content -Raw -LiteralPath $f | ConvertFrom-Json
    $t | Add-Member -NotePropertyName TaskName -NotePropertyValue $TaskName
    $t | Add-Member -NotePropertyName State -NotePropertyValue 'Ready'
    $t
}
function global:Unregister-ScheduledTask {
    [CmdletBinding(SupportsShouldProcess = $true)] param([Parameter(Position = 0)][string]$TaskName)
    $f = _T-TaskFile $TaskName
    if (-not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $f)) { Write-Error "No MSFT_ScheduledTask objects found with property 'TaskName' equal to '$TaskName'."; return }
    Remove-Item -LiteralPath $f; _T-Log 'Unregister-ScheduledTask' @($TaskName)
}
function global:Get-ScheduledTaskInfo { param([Parameter(ValueFromPipeline = $true)]$InputObject) process { [pscustomobject]@{ LastRunTime = $null; LastTaskResult = 267011 } } }
function global:Start-ScheduledTask { param([string]$TaskName) _T-Log 'Start-ScheduledTask' @($TaskName) }
function global:Get-CimClass {
    [CmdletBinding()] param([string]$Namespace, [Parameter(Position = 0)][string]$ClassName)
    [pscustomobject]@{ CimClassName = $ClassName; Namespace = $Namespace }
}
function global:New-CimInstance {
    [CmdletBinding()] param([object]$CimClass, [switch]$ClientOnly, [System.Collections.IDictionary]$Property)
    if (-not $ClientOnly) { throw "harness: New-CimInstance without -ClientOnly would write to the CIM repository" }
    $o = [ordered]@{}; foreach ($k in $Property.Keys) { $o[$k] = $Property[$k] }
    $o['CimClass'] = [pscustomobject]@{ CimClassName = $CimClass.CimClassName }
    [pscustomobject]$o
}
function global:Get-CimInstance {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$ClassName)
    switch ($ClassName) {
        'Win32_ComputerSystem' { [pscustomobject]@{ Manufacturer = 'Microsoft Corporation'; Model = 'Surface Pro 7'; TotalPhysicalMemory = 8GB } }
        'Win32_OperatingSystem' { [pscustomobject]@{ Caption = 'Microsoft Windows 11 Home'; BuildNumber = '22631' } }
        default { throw "harness: Get-CimInstance $ClassName not stubbed" }
    }
}

# ---------------------------------------------------------------------------------------------- network: Get-NetTCPConnection
function global:Get-NetTCPConnection {
    [CmdletBinding()] param([string]$State, [uint16[]]$LocalPort)
    $pids = @(& $env:LE_T_PYREAL $env:LE_T_PORTPID $LocalPort[0] 2>$null | Where-Object { $_ -match '^\d+$' })
    if (-not $pids) { throw "No MSFT_NetTCPConnection objects found with property 'LocalPort' equal to '$($LocalPort[0])'." }
    foreach ($p in $pids) { [pscustomobject]@{ LocalPort = $LocalPort[0]; State = 'Listen'; OwningProcess = [uint32]$p } }
}

# ---------------------------------------------------------------------------------------------- UI: Read-Host
function global:Read-Host {
    [CmdletBinding()] param([Parameter(Position = 0)][object]$Prompt, [switch]$AsSecureString, [switch]$MaskInput)
    $q = @()
    if (Microsoft.PowerShell.Management\Test-Path -LiteralPath $env:LE_T_ANSWERS) { $q = @(Get-Content -Raw -LiteralPath $env:LE_T_ANSWERS | ConvertFrom-Json) }
    if ($q.Count -eq 0) { throw "harness: Read-Host with no scripted answer left: $Prompt" }
    $ans = "$($q[0])"
    ConvertTo-Json -InputObject @($q | Select-Object -Skip 1) | Set-Content -LiteralPath $env:LE_T_ANSWERS
    _T-Log 'Read-Host' @("$Prompt", $(if ($AsSecureString) { '<secure>' } else { $ans }))
    if ($AsSecureString) {
        $s = New-Object System.Security.SecureString
        foreach ($ch in $ans.ToCharArray()) { $s.AppendChar($ch) }
        $s.MakeReadOnly(); return $s
    }
    return $ans
}

# ---------------------------------------------------------------------------------------------- Start-Process (UAC, windows)
function global:Start-Process {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true, Position = 0)][string]$FilePath, [Parameter(Position = 1)][string[]]$ArgumentList,
          [string]$Verb, [switch]$Wait, [string]$WorkingDirectory, [string]$WindowStyle, [switch]$PassThru, [switch]$NoNewWindow)
    _T-Log 'Start-Process' @($FilePath, ($ArgumentList -join ' '), "verb=$Verb", "wait=$Wait")
    $isPs = $FilePath -match '(?i)powershell(\.exe)?$'
    if ($Verb -eq 'RunAs' -and $env:LE_T_UAC -eq 'no') { throw "This command cannot be run due to the error: The operation was canceled by the user." }
    if (-not $isPs) { return }                                   # NinjaTrader.exe, a URL: recorded only
    $sp = @{ FilePath = $FilePath; ArgumentList = $ArgumentList; NoNewWindow = $true }
    $envOld = $env:LE_T_ELEVATED
    if ($Verb -eq 'RunAs') { $env:LE_T_ELEVATED = '1' }
    try {
        if ($Wait) { Microsoft.PowerShell.Management\Start-Process @sp -Wait }
        else {
            $n = [guid]::NewGuid().ToString('N').Substring(0, 8)
            $sp['RedirectStandardOutput'] = Join-Path $env:LE_T_BG "bg-$n.out"; $sp['RedirectStandardError'] = Join-Path $env:LE_T_BG "bg-$n.err"
            $p = Microsoft.PowerShell.Management\Start-Process @sp -PassThru
            Add-Content -LiteralPath (Join-Path $env:LE_T_BG 'pids.txt') -Value $p.Id
            if ($PassThru) { return $p }
        }
    } finally { $env:LE_T_ELEVATED = $envOld }
}

# ---------------------------------------------------------------------------------------------- New-Object -ComObject WScript.Shell
function global:New-Object {
    [CmdletBinding(DefaultParameterSetName = 'Net')]
    param([Parameter(ParameterSetName = 'Net', Mandatory = $true, Position = 0)][string]$TypeName,
          [Parameter(ParameterSetName = 'Net', Position = 1)][object[]]$ArgumentList,
          [Parameter(ParameterSetName = 'Com', Mandatory = $true)][string]$ComObject,
          [System.Collections.IDictionary]$Property, [switch]$Strict)
    if ($PSCmdlet.ParameterSetName -eq 'Com') {
        if ($ComObject -ne 'WScript.Shell') { throw "harness: COM $ComObject not stubbed" }
        $sh = [pscustomobject]@{}
        $sh | Add-Member -MemberType ScriptMethod -Name CreateShortcut -Value {
            param($LnkPath)
            if ($LnkPath -notmatch '\.lnk$') { throw "CreateShortcut: not a .lnk path: $LnkPath" }
            $s = [pscustomobject]@{ FullName = $LnkPath; TargetPath = ''; WorkingDirectory = ''; IconLocation = ''; Description = ''; Arguments = '' }
            $s | Add-Member -MemberType ScriptMethod -Name Save -Value {
                $dir = Split-Path -Parent $this.FullName
                if (-not (Microsoft.PowerShell.Management\Test-Path -LiteralPath $dir)) { throw "Save: folder $dir does not exist" }
                ($this | Select-Object FullName, TargetPath, WorkingDirectory, IconLocation, Description | ConvertTo-Json) | Set-Content -LiteralPath $this.FullName
                _T-Log 'Shortcut' @($this.FullName, $this.TargetPath)
            }
            return $s
        }
        return $sh
    }
    Microsoft.PowerShell.Utility\New-Object @PSBoundParameters
}
