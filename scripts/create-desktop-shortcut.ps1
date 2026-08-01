# create-desktop-shortcut.ps1
#
# Creates a "Nemiii" shortcut on your Windows Desktop, using the peacock-orb
# icon and pointing at start-nemiii.bat.
#
# Run this from WSL (not from inside Windows PowerShell directly, since the
# project lives on the WSL filesystem):
#
#   powershell.exe -ExecutionPolicy Bypass -File "$(wslpath -w ~/friday/nemin-ai-assist/scripts/create-desktop-shortcut.ps1)"
#
# $PSScriptRoot will resolve to the \\wsl$\...\scripts UNC path automatically
# since that's how the script itself was reached - no hardcoded usernames.

$WshShell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Nemiii.lnk'

$shortcut = $WshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $PSScriptRoot 'start-nemiii.bat'
$shortcut.WorkingDirectory = $PSScriptRoot

$iconPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'assets\nemiii.ico'
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
} else {
    Write-Warning "Icon not found at $iconPath - shortcut will use the default .bat icon."
}

$shortcut.Description = "Launch Nemiii - voice-controlled PC assistant"
$shortcut.Save()

Write-Output "Shortcut created: $shortcutPath"
