# Creates the Nemiii desktop shortcut (and optionally starts her when you log in).
# Called by scripts/windows-shortcut.sh. ASCII only on purpose.
param([string]$Distro, [string]$Root, [string]$Icon, [string]$Autostart = "0", [string]$Remove = "0", [string]$Tray = "0", [string]$TrayScript = "")
$ws = New-Object -ComObject WScript.Shell
function Place($dir) {
  $lnk = Join-Path $dir 'Nemiii.lnk'
  if ($Remove -eq "1") { if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Output ("removed " + $lnk) }; return }
  $s = $ws.CreateShortcut($lnk)
  $s.TargetPath = Join-Path $env:SystemRoot 'System32\wsl.exe'
  $s.Arguments = '-d ' + $Distro + ' -e bash -lic "cd ''' + $Root + ''' && ./run.sh --open --hold"'
  $s.WorkingDirectory = $env:USERPROFILE
  $s.IconLocation = $Icon + ',0'
  $s.WindowStyle = 7
  $s.Description = 'Nemiii voice assistant'
  $s.Save()
  Write-Output ("created " + $lnk)
}
Place ([Environment]::GetFolderPath('Desktop'))
if ($Autostart -eq "1" -or $Remove -eq "1") { Place ([Environment]::GetFolderPath('Startup')) }

# Optional tray icon (starts hidden when you log in to Windows)
$startup = [Environment]::GetFolderPath('Startup')
$trayLnk = Join-Path $startup 'Nemiii Tray.lnk'
if ($Remove -eq "1") {
  if (Test-Path $trayLnk) { Remove-Item $trayLnk -Force; Write-Output ("removed " + $trayLnk) }
} elseif ($Tray -eq "1") {
  $t = $ws.CreateShortcut($trayLnk)
  $t.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $t.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $TrayScript + '" -Distro "' + $Distro + '" -Root "' + $Root + '" -Icon "' + $Icon + '"'
  $t.WindowStyle = 7
  $t.Description = 'Nemiii tray icon'
  $t.Save()
  Write-Output ("created " + $trayLnk)
  Start-Process -WindowStyle Hidden powershell.exe -ArgumentList ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $TrayScript + '" -Distro "' + $Distro + '" -Root "' + $Root + '" -Icon "' + $Icon + '"')
}
