# Records clicks for a tutorial in a browser on Windows (a browser inside WSL is clumsy).
#
# Run from PowerShell, with the script's path in WSL:
#   powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 create-2a3-task
#
# Opens the site, logged in, next to Playwright's recorder. The first time, log in in that window: the session is saved
# when you close it and used from then on, also by `npm run record` in WSL. The recorded code is written live to
# tutorials\recorded\<name>.js, ready to paste into scripts/<name>.ts.

param(
    [Parameter(Position = 0)][string]$Name = "recording",
    [string]$Path = "/",
    [string]$BaseUrl = "http://localhost:8002",
    [string]$Viewport = "1440,810"
)

$ErrorActionPreference = "Stop"
# The same Playwright version as tutorials/package.json
$PlaywrightVersion = "1.64.1"

$Tutorials = Split-Path -Parent $PSScriptRoot
$AuthDir = Join-Path $Tutorials ".auth"
$AuthFile = Join-Path $AuthDir "state.json"
$RecordedDir = Join-Path $Tutorials "recorded"
New-Item -ItemType Directory -Force -Path $AuthDir, $RecordedDir | Out-Null
$Output = Join-Path $RecordedDir "$Name.js"

$Arguments = @(
    "-y", "playwright@$PlaywrightVersion", "codegen",
    "--target=javascript",
    "--viewport-size=$Viewport",
    "--save-storage=$AuthFile",
    "--output=$Output"
)
if (Test-Path $AuthFile) { $Arguments += "--load-storage=$AuthFile" }
$Arguments += ([Uri]::new([Uri]$BaseUrl, $Path)).AbsoluteUri

# npx cannot run from a \\wsl.localhost folder
Push-Location $env:TEMP
try {
    & npx @Arguments
}
finally {
    Pop-Location
}
Write-Host "Recorded code: $Output"
