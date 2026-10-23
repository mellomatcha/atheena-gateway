$ErrorActionPreference = 'Stop'
# Only a localhost listener; the sandbox services continue to run in isolated CT 102.
$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $probe.Connect('127.0.0.1', 4173)
    Write-Output 'Port 4173 is already in use. If this is the ATHEENA preview, open http://127.0.0.1:4173/.'
    return
} catch {
    # No existing listener: establish this preview's own SSH tunnel.
} finally {
    $probe.Dispose()
}
$sshPath = (Get-Command ssh.exe -ErrorAction Stop).Source
$previewProcess = Start-Process -FilePath $sshPath -WindowStyle Hidden -PassThru -ArgumentList @(
    '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
    '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30',
    '-N', '-L', '127.0.0.1:4173:10.10.10.12:20131', 'helios-proxmox'
)
Write-Output "Preview tunnel started (PID $($previewProcess.Id)). Open http://127.0.0.1:4173/."
