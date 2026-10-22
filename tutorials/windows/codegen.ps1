# Records clicks for a tutorial in a browser on Windows (a browser inside WSL is clumsy).
#
# Run from PowerShell, with the script's path in WSL:
#   powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\kolaf\dev\airsportslivetracking\tutorials\windows\codegen.ps1 task2.a3
#
# Opens the site, logged in, and records what you do (capture.mjs). The first time, log in in that window: the session
# is saved when you close it and used from then on, also by `npm run record` in WSL. The recorded steps are written
# live to tutorials\recorded\<name>.js, ready to paste into scripts/<name>.ts.

# The page size, start location and site address come from tutorials\.env (TUTORIAL_WIDTH/TUTORIAL_HEIGHT,
# TUTORIAL_GEOLOCATION, TUTORIAL_BASE_URL), the same settings `npm run record` uses, so the two always match. Give
# -Viewport, -Geolocation or -BaseUrl only to override them.
param(
    [Parameter(Position = 0)][string]$Name = "recording",
    [string]$Path = "/",
    [string]$BaseUrl = "",
    # "width,height" of the page, 16:9
    [string]$Viewport = "",
    # "latitude,longitude" the browser reports, where a new route's map opens
    [string]$Geolocation = ""
)

$ErrorActionPreference = "Stop"

$Settings = @{}
$EnvFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
if (Test-Path $EnvFile) {
    foreach ($Line in Get-Content $EnvFile) {
        if ($Line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $Settings[$Matches[1]] = $Matches[2].Trim('"') }
    }
}
if (-not $BaseUrl) { $BaseUrl = if ($Settings["TUTORIAL_BASE_URL"]) { $Settings["TUTORIAL_BASE_URL"] } else { "http://localhost:8002" } }
if (-not $Viewport) {
    $Width = if ($Settings["TUTORIAL_WIDTH"]) { $Settings["TUTORIAL_WIDTH"] } else { "1440" }
    $Height = if ($Settings["TUTORIAL_HEIGHT"]) { $Settings["TUTORIAL_HEIGHT"] } else { "810" }
    $Viewport = "$Width,$Height"
}
if (-not $Geolocation) { $Geolocation = $Settings["TUTORIAL_GEOLOCATION"] }
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
