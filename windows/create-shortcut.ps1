# Creates the Nemiii desktop shortcut (and optionally starts her when you log in).
# Called by scripts/windows-shortcut.sh. ASCII only on purpose.
param([string]$Distro, [string]$Root, [string]$Icon, [string]$Autostart = "0", [string]$Remove = "0")
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
