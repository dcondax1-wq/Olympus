# Rule checks for the v2 deep tune (tests/test_clean_pc.py): parses scripts/pc_tune.ps1, scripts/pc_keeper.ps1 and
# scripts/clean_pc.ps1, loads only their functions and lists (AST, no script body runs), then checks the rules.
# One line per check: "PASS name" / "FAIL name (detail)". Exit 0.
param([Parameter(Mandatory = $true)][string]$Tune, [Parameter(Mandatory = $true)][string]$Keeper, [Parameter(Mandatory = $true)][string]$Clean)
$ErrorActionPreference = 'Stop'
function Load([string]$File, [string[]]$Lists) {
    $tokens = $null; $errs = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($File, [ref]$tokens, [ref]$errs)
    if ($errs.Count) { foreach ($e in $errs) { "FAIL parse error $File line $($e.Extent.StartLineNumber): $($e.Message)" }; return }
    "PASS parses: $(Split-Path -Leaf $File)"
    foreach ($a in $ast.EndBlock.Statements) {
        if ($a -is [System.Management.Automation.Language.AssignmentStatementAst] -and $a.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
            $Lists -contains $a.Left.VariablePath.UserPath) { . ([scriptblock]::Create($a.Extent.Text)) }
    }
    foreach ($f in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)) { . ([scriptblock]::Create($f.Extent.Text)) }
}
function T([string]$Name, [bool]$Ok, [string]$Detail = '') { if ($Ok) { "PASS $Name" } else { "FAIL $Name ($Detail)" } }
function ET([string]$s) { [DateTime]::Parse($s, [Globalization.CultureInfo]::InvariantCulture) }

. Load $Tune @('TuneServices', 'NeverServices', 'NtExclude', 'BotExclude', 'PowerAC', 'ProcFreqMax', 'PlanGuid')
. Load $Keeper @('Down', 'Never')
. Load $Clean @()

# --- services: never a security / update / network one
$names = @($TuneServices | ForEach-Object { $_.Name })
$clash = @($names | Where-Object { $NeverServices -contains $_ })
T 'services: none of the switched-off services is on the never list' ($clash.Count -eq 0) ($clash -join ', ')
foreach ($n in @('WinDefend', 'mpssvc', 'wuauserv', 'Dnscache', 'Dhcp', 'WlanSvc', 'BFE', 'SecurityHealthService', 'TabletInputService', 'Audiosrv', 'W32Time')) {
    T "services: $n can never be switched off" (-not (Test-ServiceAllowed $n))
}
T 'services: DiagTrack may be switched off' (Test-ServiceAllowed 'DiagTrack')
T 'services: an unknown service is never switched off' (-not (Test-ServiceAllowed 'SomethingElse'))
T 'services: every one has a reason' (@($TuneServices | Where-Object { -not $_.Why }).Count -eq 0)
T 'services: Xbox ones only on the bot PC (the main PC keeps its games)' (@($TuneServices | Where-Object { $_.Name -like 'Xb*' -and $_.Where -ne 'bot' }).Count -eq 0)

# --- Defender: only data folders, never a program or a drive
T 'Defender: NinjaTrader folders are db, log, trace only' ((($NtExclude | Sort-Object) -join ',') -eq 'db,log,trace') ($NtExclude -join ',')
T 'Defender: bot folders are data, logs only' ((($BotExclude | Sort-Object) -join ',') -eq 'data,logs') ($BotExclude -join ',')

# --- kind of PC, heat cap, memory choices
T 'kind: a Surface Pro 7 is surface' ((Get-TuneKind 'Surface Pro 7' 2 3.6) -eq 'surface')
T 'kind: a 16 GB laptop is desktop (full speed)' ((Get-TuneKind 'ThinkPad' 2 16) -eq 'desktop')
T 'kind: an 8 GB laptop is surface (cooler)' ((Get-TuneKind 'Inspiron' 2 8) -eq 'surface')
T 'kind: a desktop is desktop' ((Get-TuneKind 'OptiPlex 7070' 1 16) -eq 'desktop')
T 'heat cap: surface 2800 MHz' ((Get-AutoMHz 'surface') -eq 2800)
T 'heat cap: desktop none' ((Get-AutoMHz 'desktop') -eq 0)
T 'SysMain off on 4 GB + SSD' (Get-SysMainAdvice 3.6 $true)
T 'SysMain kept on 16 GB' (-not (Get-SysMainAdvice 16 $true))
T 'SysMain kept on a hard disk' (-not (Get-SysMainAdvice 4 $false))
T 'page file: system managed is left alone' (-not (Test-PagefileTooSmall $true 0))
T 'page file: set by hand at 2 GB is too small' (Test-PagefileTooSmall $false 2048)
T 'page file: set by hand at 8 GB is left alone' (-not (Test-PagefileTooSmall $false 8192))
T 'power: every setting is plugged-in only (AC) and has a name' (@($PowerAC | Where-Object { -not $_.What }).Count -eq 0)
T 'power: the surface keeps PCI Express power saving (heat)' (@($PowerAC | Where-Object { $_.What -like 'PCI*' -and $_.Surface }).Count -eq 0)

# --- the trading-hours guard (the same as clean_pc)
T 'guard: Mon 10:00 ET bot PC waits' (-not (Test-DeepAllowed (ET '2026-11-02 10:00') $false $false))
T 'guard: Mon 16:05 ET bot PC runs' (Test-DeepAllowed (ET '2026-11-02 16:05') $false $true)
T 'guard: main PC with NinjaTrader open waits' (-not (Test-DeepAllowed (ET '2026-11-02 10:00') $true $true))
T 'guard: main PC without NinjaTrader runs' (Test-DeepAllowed (ET '2026-11-02 10:00') $true $false)
T 'guard: Sunday runs' (Test-DeepAllowed (ET '2026-11-08 11:00') $false $true)

# --- keeper: never lowers NinjaTrader, python, Windows or Defender
foreach ($n in @('NinjaTrader', 'python', 'pythonw', 'MsMpEng', 'explorer', 'dwm', 'svchost', 'claude')) { T "keeper: never lowers $n" (-not (Test-MayLower $n)) }
T 'keeper: lowers OneDrive and Teams' ((Test-MayLower 'OneDrive') -and (Test-MayLower 'ms-teams'))
T 'keeper: no protected name on its lowering list' (@($Down | Where-Object { $Never -contains $_.ToLowerInvariant() }).Count -eq 0)
T 'keeper: trims at 85% used' ((Test-NeedTrim 85 85) -and -not (Test-NeedTrim 84 85))

# --- Obsidian (2026-11-03: the owner's vault; Jarvis syncs it with Obsidian Git): protected everywhere
. Load $Clean @('Protect', 'CloseProcs', 'StartupOff')
T 'Obsidian: protected in clean_pc' (Is-Protected 'Obsidian')
T 'Obsidian: never closed' (-not ($CloseProcs -contains 'Obsidian'))
T 'Obsidian: never switched off at sign-in' (-not (Is-StartupJunk 'Obsidian' 'C:\Users\x\AppData\Local\Programs\Obsidian\Obsidian.exe'))
T 'Obsidian: keeper never lowers it' (-not (Test-MayLower 'Obsidian'))
T 'startup bytes: 03 = off, 02 = on' ((Test-StartupDisabled ([byte[]](3, 0, 0))) -and -not (Test-StartupDisabled ([byte[]](2, 0, 0))) -and -not (Test-StartupDisabled (Enabled-Bytes)))

# --- health score (clean_pc.ps1)
$hi = Get-HealthScore 40 100 0 30 50
$lo = Get-HealthScore 5 0 20 1 95
T 'health: a roomy, cool PC scores 100' ($hi -eq 100) "$hi"
T 'health: a full, hot PC scores under 10' ($lo -lt 10) "$lo"
T 'health: temperature not readable: the rest scaled to 100' ((Get-HealthScore 40 100 0 30 $null) -eq 100)
T 'health: nothing readable -> none' ($null -eq (Get-HealthScore $null $null $null $null $null))
T 'health: more free memory scores higher' ((Get-HealthScore 30 50 5 20 60) -gt (Get-HealthScore 10 50 5 20 60))
exit 0
