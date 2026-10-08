# Read-only USB driver inventory. No installations or device changes.
Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.PNPDeviceID -match 'VID_18D1|VID_0E8D' -or $_.Name -match 'Android|SUNMI|UsbDk'
} | Select-Object Name,PNPDeviceID,Service,Status,ConfigManagerErrorCode | Format-List
