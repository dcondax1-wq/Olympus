# Windows stubs for tests/test_clean_storage.py: dot-sourced before scripts/clean_storage.ps1 runs under pwsh on Linux.
# Only what Linux does not have is stubbed (services, Recycle Bin, takeown / icacls, UAC). File deletes are REAL, but only
# inside the sandbox tree the test builds. "HARNESS-..." lines let the test see what was asked of Windows.
if ($env:LE_T_STRICT -eq '1') { Set-StrictMode -Version 2 }

function global:Get-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name) [pscustomobject]@{ Name = $Name; Status = 'Running' } }
function global:Stop-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name, [switch]$Force) [Console]::WriteLine("HARNESS-SVC stop $Name") }
function global:Start-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name) [Console]::WriteLine("HARNESS-SVC start $Name") }
function global:Clear-RecycleBin { [CmdletBinding()] param([switch]$Force) [Console]::WriteLine("HARNESS-BIN emptied") }
function global:takeown.exe { [Console]::WriteLine("HARNESS-TAKEOWN $args"); $global:LASTEXITCODE = 0 }
function global:icacls.exe { [Console]::WriteLine("HARNESS-ICACLS $args"); $global:LASTEXITCODE = 0 }
# UAC: the elevated child really runs (same pwsh, LE_T_ELEVATED=1) so the result file hand-over is tested too.
# LE_T_UAC=no -> "Administrator was declined" (Start-Process throws, as it does when the prompt is cancelled).
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
