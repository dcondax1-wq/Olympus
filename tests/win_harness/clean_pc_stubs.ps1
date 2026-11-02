# Windows stubs for tests/test_clean_pc.py: dot-sourced before scripts/clean_pc.ps1 runs under pwsh on Linux.
# A small Surface-like PC (4 GB, 2 cores, NVMe). Anything that would change the machine prints "HARNESS-CHANGE ..." so the
# test can prove a -DryRun / -Report run changed nothing. Functions beat cmdlets / exes of the same name.
if ($env:LE_T_STRICT -eq '1') { Set-StrictMode -Version 2 }

function global:Get-CimInstance {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$ClassName, [string]$Filter, [string]$Namespace)
    switch ($ClassName) {
        'Win32_OperatingSystem' { [pscustomobject]@{ Caption = 'Microsoft Windows 11 Home'; BuildNumber = '26100'; Version = '10.0.26100'
                                                      TotalVisibleMemorySize = 3774873; FreePhysicalMemory = 377487; LastBootUpTime = (Get-Date).AddHours(-30) } }
        'Win32_Processor' { [pscustomobject]@{ Name = 'Intel(R) Core(TM) i5-1035G4 CPU @ 1.10GHz  '; NumberOfCores = 2; NumberOfLogicalProcessors = 4; MaxClockSpeed = 1498; LoadPercentage = 97 } }
        'Win32_ComputerSystem' { [pscustomobject]@{ Manufacturer = 'Microsoft Corporation'; Model = 'Surface Pro 7'; TotalPhysicalMemory = 4GB } }
        'Win32_PhysicalMemory' { [pscustomobject]@{ Capacity = 4GB; Speed = 3733; ConfiguredClockSpeed = 3733 } }
        'Win32_PhysicalMemoryArray' { [pscustomobject]@{ MemoryDevices = 1 } }
        'Win32_LogicalDisk' { [pscustomobject]@{ DeviceID = 'C:'; FreeSpace = 21GB; Size = 118GB } }
        'Win32_VideoController' { [pscustomobject]@{ Name = 'Intel(R) Iris(R) Plus Graphics'; DriverVersion = '31.0.101.2111'; CurrentHorizontalResolution = 2736; CurrentVerticalResolution = 1824; CurrentRefreshRate = 60 } }
        'Win32_Battery' { [pscustomobject]@{ EstimatedChargeRemaining = 100 } }
        'Win32_StartupCommand' { @([pscustomobject]@{ Name = 'OneDrive'; Command = 'OneDrive.exe /background' }, [pscustomobject]@{ Name = 'Discord'; Command = 'Update.exe --processStart Discord.exe' }) }
        default { throw "harness: Get-CimInstance $ClassName not stubbed" }
    }
}
function global:Get-PhysicalDisk { [CmdletBinding()] param() [pscustomobject]@{ FriendlyName = 'KBG40ZPZ128G'; MediaType = 'SSD'; BusType = 'NVMe'; Size = 128GB } }
function global:powercfg { 'Power Scheme GUID: 381b4222-f694-41f0-9621-a68e2a2b1d4b  (Balanced)'; $global:LASTEXITCODE = 0 }
function global:dism.exe { [Console]::WriteLine("HARNESS-CHANGE dism $args"); $global:LASTEXITCODE = 0 }
function global:Stop-Process { [CmdletBinding()] param([Parameter(ValueFromPipeline = $true)]$InputObject, [switch]$Force) process { [Console]::WriteLine("HARNESS-CHANGE Stop-Process") } }
function global:Remove-Item { [CmdletBinding()] param([string]$LiteralPath, [switch]$Force) [Console]::WriteLine("HARNESS-CHANGE Remove-Item $LiteralPath") }
function global:Start-Process { [CmdletBinding()] param([Parameter(Position = 0)]$FilePath, $ArgumentList, $Verb, [switch]$PassThru, [switch]$Wait) [Console]::WriteLine("HARNESS-CHANGE Start-Process $FilePath") }
function global:Get-AppxPackage { [CmdletBinding()] param([string]$Name) }
function global:Remove-AppxPackage { [CmdletBinding()] param([string]$Package) [Console]::WriteLine("HARNESS-CHANGE Remove-AppxPackage $Package") }
function global:Start-MpScan { [CmdletBinding()] param([string]$ScanType) [Console]::WriteLine("HARNESS-CHANGE Start-MpScan") }
function global:Get-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name) [pscustomobject]@{ Name = $Name; Status = 'Running' } }
function global:Stop-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name, [switch]$Force) [Console]::WriteLine("HARNESS-CHANGE Stop-Service $Name") }
function global:Set-Service { [CmdletBinding()] param([Parameter(Position = 0)][string]$Name, [string]$StartupType) [Console]::WriteLine("HARNESS-CHANGE Set-Service $Name") }
function global:Delete-DeliveryOptimizationCache { [CmdletBinding()] param([switch]$Force) [Console]::WriteLine("HARNESS-CHANGE Delete-DeliveryOptimizationCache") }
# registry (HKCU: / HKLM: are not drives on Linux): writes are recorded, never applied
function global:_T-IsReg([string]$P) { return ($P -match '^(HKLM|HKCU):') }
function global:Test-Path {
    [CmdletBinding()] param([Parameter(Position = 0)][string]$Path, [string]$LiteralPath, [Microsoft.PowerShell.Commands.TestPathType]$PathType = 'Any')
    $p = $Path; if ($LiteralPath) { $p = $LiteralPath }
    if (_T-IsReg $p) { return $false }
    Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
function global:New-Item {
    [CmdletBinding()] param([Parameter(Position = 0)][string[]]$Path, [string]$ItemType, [switch]$Force)
    if ($Path -and (_T-IsReg $Path[0])) { [Console]::WriteLine("HARNESS-REG New-Item $($Path[0])"); return }
    Microsoft.PowerShell.Management\New-Item @PSBoundParameters
}
function global:New-ItemProperty {
    [CmdletBinding()] param([string]$Path, [string]$Name, [object]$Value, [string]$PropertyType, [switch]$Force)
    [Console]::WriteLine("HARNESS-REG $Path $Name=$Value")
}
