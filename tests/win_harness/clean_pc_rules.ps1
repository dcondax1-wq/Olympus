# Rule checks for tests/test_clean_pc.py: parses scripts/clean_pc.ps1, loads only its functions and its lists (AST, nothing
# of the script body runs), then checks the rules. One line per check: "PASS name" / "FAIL name (detail)". Exit 0.
param([Parameter(Mandatory = $true)][string]$Script, [Parameter(Mandatory = $true)][string]$Tmp)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Script, [ref]$tokens, [ref]$errs)
if ($errs.Count) { foreach ($e in $errs) { "FAIL parse error line $($e.Extent.StartLineNumber): $($e.Message)" }; exit 0 }
'PASS parses with no errors'

# the lists (top-level assignments) and every function, defined here
$lists = @('Protect', 'CloseProcs', 'StartupOff', 'BloatApps')
foreach ($a in $ast.EndBlock.Statements) {
    if ($a -is [System.Management.Automation.Language.AssignmentStatementAst] -and $a.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $lists -contains $a.Left.VariablePath.UserPath) { . ([scriptblock]::Create($a.Extent.Text)) }
}
foreach ($f in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)) { . ([scriptblock]::Create($f.Extent.Text)) }
$DryRun = $true; $Standalone = $false

function T([string]$Name, [bool]$Ok, [string]$Detail = '') { if ($Ok) { "PASS $Name" } else { "FAIL $Name ($Detail)" } }
function ET([string]$s) { [DateTime]::Parse($s, [Globalization.CultureInfo]::InvariantCulture) }

# --- the trading window and the deep part (2026-11-02 is a Monday)
T 'trading window: Mon 01:14 ET is outside' (-not (Is-TradingWindow (ET '2026-11-02 01:14')))
T 'trading window: Mon 01:15 ET is inside' (Is-TradingWindow (ET '2026-11-02 01:15'))
T 'trading window: Mon 16:04 ET is inside' (Is-TradingWindow (ET '2026-11-02 16:04'))
T 'trading window: Mon 16:05 ET is outside' (-not (Is-TradingWindow (ET '2026-11-02 16:05')))
T 'trading window: Saturday 10:00 ET is outside' (-not (Is-TradingWindow (ET '2026-11-07 10:00')))
T 'deep part: bot PC in trading hours waits' (-not (Test-DeepAllowed (ET '2026-11-02 10:00') $false $false))
T 'deep part: bot PC at 17:00 ET runs' (Test-DeepAllowed (ET '2026-11-02 17:00') $false $true)
T 'deep part: main PC (standalone) without NinjaTrader runs any time' (Test-DeepAllowed (ET '2026-11-02 10:00') $true $false)
T 'deep part: main PC with NinjaTrader open in trading hours waits' (-not (Test-DeepAllowed (ET '2026-11-02 10:00') $true $true))

# --- never touched
foreach ($p in @('NinjaTrader', 'python', 'pythonw', 'OneDrive', 'claude', 'git', 'LE START BOT', 'MsMpEng')) { T "protected: $p" (Is-Protected $p) }
$bad = @($CloseProcs | Where-Object { Is-Protected $_ }); T 'no program closed is protected' ($bad.Count -eq 0) ($bad -join ', ')
foreach ($p in @('NinjaTrader', 'python', 'msedge', 'explorer', 'powershell', 'OneDrive', 'Claude', 'git', 'pwsh', 'WindowsTerminal')) {
    T "never closed: $p" (-not ($CloseProcs -contains $p))
}
T 'startup: Discord switched off' (Is-StartupJunk 'Discord' 'C:\Users\x\AppData\Local\Discord\Update.exe --processStart Discord.exe')
T 'startup: Spotify switched off' (Is-StartupJunk 'Spotify' 'Spotify.exe /minimized')
T 'startup: NinjaTrader kept' (-not (Is-StartupJunk 'NinjaTrader' 'C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe'))
T 'startup: the bot kept even when its command mentions teams' (-not (Is-StartupJunk 'LE START BOT' 'python server.py --teams'))
T 'startup: OneDrive kept' (-not (Is-StartupJunk 'OneDrive' 'OneDrive.exe /background'))
T 'startup: Claude kept' (-not (Is-StartupJunk 'Claude' 'Claude.exe'))
T 'preinstalled apps: nothing for trading on the list' (-not (@($BloatApps | Where-Object { $_ -match '(?i)edge|onedrive|ninja|python|terminal|store|defender|security' }).Count))

# --- bot folder detection (standalone on the main PC)
$bot = Join-Path $Tmp 'bot'; $none = Join-Path $Tmp 'kit'
New-Item -ItemType Directory -Force -Path (Join-Path $bot 'engine'), $none | Out-Null
Set-Content -LiteralPath (Join-Path $bot 'server.py') -Value '#'; Set-Content -LiteralPath (Join-Path (Join-Path $bot 'engine') 'ninjatrader.py') -Value '#'
T 'bot folder detected (server.py + engine/ninjatrader.py)' (Test-BotFolder $bot)
T 'folder without the bot -> standalone' (-not (Test-BotFolder $none))
T 'empty path -> standalone' (-not (Test-BotFolder ''))

# --- NinjaTrader workspace reading
$xml = @'
<NinjaTrader><Chart><Bars><Instrument>MNQ 12-26</Instrument><DaysBack>20</DaysBack><IsTickReplay>false</IsTickReplay></Bars>
<Indicator type="NinjaTrader.NinjaScript.Indicators.LE_BarFeed" /></Chart>
<Chart><Bars><Instrument>NQ 12-26</Instrument><DaysBack>60</DaysBack><IsTickReplay>true</IsTickReplay></Bars>
<Indicator type="NinjaTrader.NinjaScript.Indicators.SMA" /><Indicator type="NinjaTrader.NinjaScript.Indicators.VWAP" /></Chart></NinjaTrader>
'@
$st = Get-WorkspaceStats $xml
T 'workspace: 2 data series' ($st.Series -eq 2) "$($st.Series)"
T 'workspace: most days loaded 60' ($st.MaxDays -eq 60) "$($st.MaxDays)"
T 'workspace: Tick Replay on in 1' ($st.TickReplay -eq 1) "$($st.TickReplay)"
T 'workspace: 3 indicators read' ($st.IndicatorCount -eq 3) "$($st.IndicatorCount)"
T 'workspace: the bot chart (LE_BarFeed) found' ($st.HasBarFeed)
$adv = (Get-WorkspaceAdvice 'Main' $st) -join ' | '
T 'advice: Tick Replay off' ($adv -match 'Tick Replay off') $adv
$bst = Get-WorkspaceStats '<DaysBack>20</DaysBack> LE_BarFeed'
T 'advice: the bot chart goes back to 30 days' (((Get-WorkspaceAdvice 'Bot' $bst) -join ' ') -match 'keep it at 30') ((Get-WorkspaceAdvice 'Bot' $bst) -join ' ')
$ost = Get-WorkspaceStats '<DaysBack>90</DaysBack>'
T 'advice: a look-only chart goes to 3-5 days' (((Get-WorkspaceAdvice 'Other' $ost) -join ' ') -match '3-5 days')
$okst = Get-WorkspaceStats '<DaysBack>30</DaysBack> LE_BarFeed'
T 'advice: a 30-day bot chart alone is fine' ((Get-WorkspaceAdvice 'Bot' $okst).Count -eq 0)
T 'empty workspace text reads as nothing' ((Get-WorkspaceStats '').Series -eq 0)
$env:OneDrive = ''
T 'OneDrive path seen' (Test-InOneDrive 'C:\Users\x\OneDrive\Documents\NinjaTrader 8')
T 'local Documents is not OneDrive' (-not (Test-InOneDrive 'C:\Users\x\Documents\NinjaTrader 8'))

# --- PC report verdicts and power mode names
T 'verdict: 3.6 GB / 2 cores = WEAK' ((Get-Verdict 3.6 $true 2) -like 'WEAK*') (Get-Verdict 3.6 $true 2)
T 'verdict: 16 GB / SSD / 6 cores = GOOD' ((Get-Verdict 16 $true 6) -like 'GOOD*') (Get-Verdict 16 $true 6)
T 'verdict: no SSD = WEAK' ((Get-Verdict 16 $false 6) -like 'WEAK*')
T 'power mode: Best performance' ((Get-PowerModeName 'ded574b5-45a0-4f42-8737-46345c09c238') -eq 'Best performance')
T 'power mode: Balanced' ((Get-PowerModeName '00000000-0000-0000-0000-000000000000') -like 'Balanced*')
exit 0
