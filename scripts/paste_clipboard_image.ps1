Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
$rootDir = Split-Path -Parent $PSScriptRoot
$captureDir = Join-Path $rootDir "captures"
if (-not (Test-Path $captureDir)) {
    New-Item -ItemType Directory -Force -Path $captureDir | Out-Null
}

# Find focused pane in Herdr
$paneJson = herdr pane list | ConvertFrom-Json
$focusedPane = $paneJson.result.panes | Where-Object { $_.focused -eq $true } | Select-Object -First 1
if (-not $focusedPane) {
    $focusedPane = $paneJson.result.panes | Select-Object -First 1
}
$paneId = $focusedPane.pane_id

if ([System.Windows.Forms.Clipboard]::ContainsImage()) {
    $img = [System.Windows.Forms.Clipboard]::GetImage()
    $ts = (Get-Date).ToString("yyyyMMdd_HHmmss_fff")
    $filePath = Join-Path $captureDir "clip_$ts.png"
    $img.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    herdr pane send-text $paneId "$filePath "
} elseif ([System.Windows.Forms.Clipboard]::ContainsFileDropList()) {
    $files = [System.Windows.Forms.Clipboard]::GetFileDropList()
    $joined = ($files -join " ") + " "
    herdr pane send-text $paneId $joined
} elseif ([System.Windows.Forms.Clipboard]::ContainsText()) {
    $txt = [System.Windows.Forms.Clipboard]::GetText()
    herdr pane send-text $paneId $txt
}
