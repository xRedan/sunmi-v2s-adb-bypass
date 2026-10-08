param([string]$Bundle)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskTools = Join-Path $taskRoot '.tools'
$taskLock = Get-Content -LiteralPath (Join-Path $taskRoot 'tools.lock.json') -Raw | ConvertFrom-Json

try {
    if (-not $Bundle) {
        $taskCandidates = @(
            (Join-Path $taskRoot $taskLock.bundle.filename),
            (Join-Path (Split-Path -Parent $taskRoot) $taskLock.bundle.filename)
        )
        $Bundle = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
    if (-not $Bundle) { $Bundle = Read-Host 'Full path to sunmi-v2s-tools-windows.zip' }
    $taskArchive = (Resolve-Path -LiteralPath $Bundle).Path
    $taskHash = (Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskHash -ne $taskLock.bundle.sha256) { throw 'Tool bundle checksum mismatch. Use the bundle matching tools.lock.json.' }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $taskZip = [IO.Compression.ZipFile]::OpenRead($taskArchive)
    try {
        $taskPrefix = [IO.Path]::GetFullPath($taskTools) + [IO.Path]::DirectorySeparatorChar
        foreach ($taskEntry in $taskZip.Entries) {
            $taskTarget = [IO.Path]::GetFullPath((Join-Path $taskTools $taskEntry.FullName))
            if (-not $taskTarget.StartsWith($taskPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Unsafe archive path. Extraction stopped.'
            }
        }
    } finally { $taskZip.Dispose() }
    New-Item -ItemType Directory -Path $taskTools -Force | Out-Null
    # Windows PowerShell's .NET may lack the overwrite overload. Extract each
    # already-validated entry and overwrite public tool files only.
    $taskZip = [IO.Compression.ZipFile]::OpenRead($taskArchive)
    try {
        foreach ($taskEntry in $taskZip.Entries) {
            $taskTarget = [IO.Path]::GetFullPath((Join-Path $taskTools $taskEntry.FullName))
            if ($taskEntry.FullName.EndsWith('/')) {
                New-Item -ItemType Directory -Path $taskTarget -Force | Out-Null
            } else {
                New-Item -ItemType Directory -Path (Split-Path -Parent $taskTarget) -Force | Out-Null
                [IO.Compression.ZipFileExtensions]::ExtractToFile($taskEntry, $taskTarget, $true)
            }
        }
    } finally { $taskZip.Dispose() }
    $taskManifest = Get-Content -LiteralPath (Join-Path $taskTools 'tools-manifest.json') -Raw | ConvertFrom-Json
    foreach ($taskFile in $taskManifest.files.PSObject.Properties) {
        $taskPath = Join-Path $taskTools $taskFile.Name
        $taskActual = (Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($taskActual -ne $taskFile.Value.sha256) { throw ('Extracted file checksum mismatch: ' + $taskFile.Name) }
    }
    Write-Host 'Tools installed and verified. Next: configure the device with 01-Configure-Device.cmd.'
    exit 0
} catch {
    Write-Error ('Setup stopped: ' + $_.Exception.Message)
    exit 2
}
