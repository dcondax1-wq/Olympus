# Windows PowerShell 5.1 lint for tests/test_win_scripts.py: parses each .ps1 with the PowerShell parser and reports
# syntax that only PowerShell 7 understands, plus 5.1 pitfalls. One line per finding: "file:line: message". Exit 0.
param([Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Files)

$bad7 = @{
    'QuestionQuestion'       = "'??' (null-coalescing) is PowerShell 7 only"
    'QuestionQuestionEquals' = "'??=' is PowerShell 7 only"
    'QuestionDot'            = "'?.' is PowerShell 7 only"
    'QuestionLBracket'       = "'?[' is PowerShell 7 only"
    'AndAnd'                 = "'&&' pipeline chain is PowerShell 7 only"
    'OrOr'                   = "'||' pipeline chain is PowerShell 7 only"
    'QuestionMark'           = "'? :' ternary is PowerShell 7 only"
}
# cmdlet parameters / values that 5.1 does not have
$badParams = @{
    'ForEach-Object'    = @('Parallel', 'ThrottleLimit', 'AsJob')
    'ConvertFrom-Json'  = @('AsHashtable', 'Depth', 'NoEnumerate')
    'ConvertTo-Json'    = @('AsArray', 'EnumsAsStrings', 'EscapeHandling')
    'Invoke-RestMethod' = @('SkipCertificateCheck', 'SkipHttpErrorCheck', 'StatusCodeVariable', 'ResponseHeadersVariable', 'Authentication', 'NoProxy', 'Form', 'Resume', 'RetryIntervalSec', 'MaximumRetryCount')
    'Invoke-WebRequest' = @('SkipCertificateCheck', 'SkipHttpErrorCheck', 'Authentication', 'NoProxy', 'Form', 'Resume', 'RetryIntervalSec', 'MaximumRetryCount')
    'Get-Content'       = @('AsByteStream')
    'Set-Content'       = @('AsByteStream')
    'Split-Path'        = @('LeafBase', 'Extension')
    'Test-Connection'   = @('TargetName', 'TcpPort')
    'Start-Process'     = @('Environment')
    'Join-Path'         = @('AdditionalChildPath')
    'Get-Date'          = @('AsUTC')
    'Select-String'     = @('Raw', 'NoEmphasis')
}
$badCmds = @('Get-Error', 'Test-Json', 'Start-ThreadJob', 'ConvertTo-CliXml', 'Join-String', 'Get-Uptime', 'ConvertFrom-Markdown')
$badEnc = @('utf8NoBOM', 'utf8BOM', 'ansi')

foreach ($f in $Files) {
    $tokens = $null; $errs = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tokens, [ref]$errs)
    $name = Split-Path -Leaf $f
    foreach ($e in $errs) { "{0}:{1}: parse error: {2}" -f $name, $e.Extent.StartLineNumber, $e.Message }
    foreach ($t in $tokens) {
        $k = "$($t.Kind)"
        if ($bad7.ContainsKey($k)) { "{0}:{1}: {2}" -f $name, $t.Extent.StartLineNumber, $bad7[$k] }
    }
    if ($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.TernaryExpressionAst] }, $true).Count) { "{0}: ternary expression" -f $name }
    if ($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.PipelineChainAst] }, $true).Count) { "{0}: pipeline chain && / ||" -f $name }
    $cmds = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($c in $cmds) {
        $cn = $c.GetCommandName()
        if (-not $cn) { continue }
        $line = $c.Extent.StartLineNumber
        if ($badCmds -contains $cn) { "{0}:{1}: {2} does not exist in 5.1" -f $name, $line, $cn }
        $params = @($c.CommandElements | Where-Object { $_ -is [System.Management.Automation.Language.CommandParameterAst] } | ForEach-Object { $_.ParameterName })
        foreach ($key in $badParams.Keys) {
            if ($cn -ieq $key) { foreach ($p in $params) { if ($badParams[$key] -contains $p) { "{0}:{1}: {2} -{3} is PowerShell 7 only" -f $name, $line, $cn, $p } } }
        }
        if ($cn -ieq 'Join-Path') {
            $pos = @($c.CommandElements | Select-Object -Skip 1 | Where-Object { $_ -isnot [System.Management.Automation.Language.CommandParameterAst] })
            $named = @($params | Where-Object { $_ -in @('Path', 'ChildPath') }).Count
            if ($pos.Count - $named -gt 2) { "{0}:{1}: Join-Path with 3+ parts is PowerShell 7 only (nest two Join-Path calls)" -f $name, $line }
        }
        if ($cn -ieq 'Invoke-WebRequest' -and $params -notcontains 'UseBasicParsing') { "{0}:{1}: Invoke-WebRequest without -UseBasicParsing fails on 5.1 without Internet Explorer" -f $name, $line }
        for ($i = 0; $i -lt $c.CommandElements.Count - 1; $i++) {
            $el = $c.CommandElements[$i]
            if ($el -is [System.Management.Automation.Language.CommandParameterAst] -and $el.ParameterName -eq 'Encoding') {
                $v = "$($c.CommandElements[$i + 1])".Trim("'", '"')
                if ($badEnc -contains $v) { "{0}:{1}: -Encoding {2} is PowerShell 7 only" -f $name, $line, $v }
            }
        }
    }
    # automatic variables that 5.1 does not set
    foreach ($v in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.VariableExpressionAst] }, $true)) {
        if ($v.VariablePath.UserPath -in @('PSStyle', 'IsWindows', 'IsLinux', 'IsMacOS', 'IsCoreCLR')) {
            "{0}:{1}: `${2} is not set in 5.1" -f $name, $v.Extent.StartLineNumber, $v.VariablePath.UserPath
        }
    }
}
exit 0
