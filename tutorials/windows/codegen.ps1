# Records clicks for a tutorial in a browser on Windows (a browser inside WSL is clumsy).
#
# Run from PowerShell, with the script's path in WSL:
#   powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 task2.a3
#
# Opens the site, logged in, and records what you do (capture.mjs). The first time, log in in that window: the session
# is saved when you close it and used from then on, also by `npm run record` in WSL. The recorded steps are written
# live to tutorials\recorded\<name>.js, ready to paste into scripts/<name>.ts.

param(
    [Parameter(Position = 0)][string]$Name = "recording",
    [string]$Path = "/",
    [string]$BaseUrl = "http://localhost:8002",
    [string]$Viewport = "1440,810",
    # "latitude,longitude" the browser reports, where a new route's map opens. Must match TUTORIAL_GEOLOCATION in .env
    [string]$Geolocation = ""
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
$Url = ([Uri]::new([Uri]$BaseUrl, $Path)).AbsoluteUri

# Node cannot run from a \\wsl.localhost folder: the recorder runs from a local copy, with Playwright installed beside it
$Runner = Join-Path $env:LOCALAPPDATA "aslt-tutorial-recorder"
New-Item -ItemType Directory -Force -Path $Runner | Out-Null
Copy-Item (Join-Path $PSScriptRoot "capture.mjs") $Runner -Force
Push-Location $Runner
try {
    $Installed = Join-Path $Runner "node_modules\playwright\package.json"
    if (-not (Test-Path $Installed) -or (Get-Content $Installed -Raw | ConvertFrom-Json).version -ne $PlaywrightVersion) {
        Write-Host "Installing Playwright $PlaywrightVersion for the recorder (once)"
        if (-not (Test-Path "package.json")) { '{ "private": true }' | Set-Content "package.json" }
        & npm install --no-audit --no-fund "playwright@$PlaywrightVersion"
        & npx playwright install chromium
    }
    $Arguments = @("capture.mjs", "--output", $Output, "--url", $Url, "--auth", $AuthFile, "--viewport", $Viewport)
    if ($Geolocation) { $Arguments += @("--geolocation", $Geolocation) }
    Write-Host "node $($Arguments -join ' ')"
    & node @Arguments
}
finally {
    Pop-Location
}
