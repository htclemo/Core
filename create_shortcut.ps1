# Creates a Desktop shortcut named "TheCore" that launches the local monitor.
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$MainPy = Join-Path $ProjectRoot "main.py"
$IconPath = Join-Path $ProjectRoot "assets\thecore.ico"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "TheCore.lnk"
$Arguments = "`"$MainPy`""

if (-not (Test-Path $MainPy)) {
    throw "main.py not found at $MainPy"
}

if (Test-Path $VenvPythonw) {
    $TargetPath = $VenvPythonw
} else {
    $pythonwCmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pythonwCmd) {
        $TargetPath = $pythonwCmd.Source
    } else {
        throw "Could not find .venv\Scripts\pythonw.exe or pythonw on PATH. Create the venv first."
    }
}

$Wsh = New-Object -ComObject WScript.Shell
$Shortcut = $Wsh.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.Arguments = $Arguments
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.WindowStyle = 1
$Shortcut.Description = "TheCore - local PC system monitor"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
}
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
Write-Host "Target: $TargetPath $Arguments"
if (Test-Path $IconPath) {
    Write-Host "Icon: $IconPath"
}
