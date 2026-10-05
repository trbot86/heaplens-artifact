param([Parameter(Mandatory=$true)][string]$Config)
$ErrorActionPreference = 'Stop'
$settings = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
foreach ($property in $settings.environment.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process')
}
# Only the generated script path is an argument; reject quote injection.
if ($settings.script.Contains('"')) { throw 'Invalid script path' }
$child = Start-Process -FilePath $settings.node -ArgumentList ('"' + $settings.script + '"') `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput $settings.stdout -RedirectStandardError $settings.stderr
$childId = $child.Id
$processHandle = $child.Handle
if (-not $child.WaitForExit([int]$settings.seconds * 1000)) {
    & taskkill.exe /PID $childId /T /F
    throw "Browser controller timed out; stopped owned Node process $childId"
}
$child.WaitForExit()
$child.Refresh()
if ($child.ExitCode -ne 0) { throw "Browser controller failed with exit code $($child.ExitCode); see $($settings.stderr)" }
