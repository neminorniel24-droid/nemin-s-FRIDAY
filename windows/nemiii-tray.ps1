# Nemiii tray icon. Started by scripts/windows-shortcut.sh --tray. ASCII only on purpose.
# Right-click the icon: Open Nemiii, Mini orb, Stop Nemiii, Quit tray. Double-click = open.
param([string]$Distro, [string]$Root, [string]$Icon)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

function Wsl([string]$cmd) {
  Start-Process -WindowStyle Hidden -FilePath (Join-Path $env:SystemRoot 'System32\wsl.exe') `
    -ArgumentList ('-d ' + $Distro + ' -e bash -lic "cd ''' + $Root + ''' && ' + $cmd + '"')
}
function WslText([string]$cmd) {
  $exe = Join-Path $env:SystemRoot 'System32\wsl.exe'
  (& $exe -d $Distro -e bash -lic ("cd '" + $Root + "' && " + $cmd) 2>$null | Out-String).Trim()
}

$ni = New-Object System.Windows.Forms.NotifyIcon
try { $ni.Icon = New-Object System.Drawing.Icon($Icon) } catch { $ni.Icon = [System.Drawing.SystemIcons]::Application }
$ni.Text = 'Nemiii'
$ni.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$open = $menu.Items.Add('Open Nemiii')
$mini = $menu.Items.Add('Mini orb')
$stop = $menu.Items.Add('Stop Nemiii')
$null = $menu.Items.Add('-')
$quit = $menu.Items.Add('Quit tray icon')

$open.add_Click({ Wsl './run.sh --open' })
$mini.add_Click({
  $port = WslText 'cat .run/port'
  if (-not $port) { $ni.ShowBalloonTip(4000, 'Nemiii', 'Nemiii is not running. Choose Open Nemiii first.', [System.Windows.Forms.ToolTipIcon]::Info); return }
  Start-Process 'chrome' ('--app=http://localhost:' + $port + '/mini --window-size=300,330')
})
$stop.add_Click({ Wsl './stop.sh --quiet' })
$quit.add_Click({ $ni.Visible = $false; $ni.Dispose(); [System.Windows.Forms.Application]::Exit() })
$ni.add_DoubleClick({ Wsl './run.sh --open' })
$ni.ContextMenuStrip = $menu

[System.Windows.Forms.Application]::Run()
