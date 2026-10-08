# SUNMI V2s: USB debugging guide

How to obtain ADB access from a PC, install APKs and restore the original boot if something goes wrong.

**Reference environment:** Windows x64; SUNMI V2s running Android 12, product `sp6308a`, firmware `SP3115GO-Sunmi-20240130193859`, slot A and a 32 MiB boot_a. Developer options must allow OEM unlocking. A different firmware requires compatibility verification before modifying boot.

**Unlocking erases user data.** The boot backup does not include photos, applications or personal data. Save those separately before unlocking.

This procedure enables ADB for the authorized PC. Settings may continue to request the SUNMI account code. If ADB already works, install the tools, configure the serial and verify ADB; skip backup, unlocking and flashing.

## 1. Prepare the PC

1. Extract the project, for example to `C:\sunmi-v2s-adb-toolkit`. Paths with spaces are supported.
2. Place `sunmi-v2s-tools-windows.zip` next to the project folder.
3. Run `00-Setup-Tools.cmd`. If the bundle is elsewhere, enter its path when prompted.
4. Wait for `Tools installed and verified`. Setup verifies the checksum and extracts tools into `.tools`.
5. Keep at least 2 GiB free, charge the terminal and use a USB data cable.

Python and Android Studio do not need separate installation. Use `99-Verify-Tools.cmd` to check the installed files again.

Numbered launchers perform the action in their name. Scripts that modify the device request a typed confirmation. Where administrator access is specified, right-click the launcher and select Run as administrator.

## 2. Install the driver and configure the device

### Enter bootloader Fastboot

1. Turn off the V2s.
2. Press Power + Volume up to open Boot Mode.
3. Select **FASTBOOT MODE**, following the button instructions on screen.
4. Connect USB to the PC.

Recovery's “enter fastboot” option may open fastbootd. The required mode is bootloader Fastboot: `is-userspace` must report `no`. From Recovery, select “reboot to bootloader”.

### Install the Windows driver

1. Open Device Manager (`devmgmt.msc`).
2. If the interface has a driver error, select Update driver > Browse my computer > Let me pick from a list > Have Disk.
3. Open `.tools\drivers\google-usb-driver\android_winusb.inf`.
4. For the compatible Fastboot interface, select **Android Bootloader Interface**.

The observed Fastboot ID is `VID_18D1&PID_4EE0`. The included Google driver supports this interface; it is not universal for all SUNMI devices. If Windows rejects it, check the hardware ID and active mode. Do not edit INF/CAT files or disable signature verification.

### Save the serial locally

1. Run `02a-List-Devices.cmd`: a line should show the terminal's serial followed by `fastboot`.
2. Run `01-Configure-Device.cmd` and enter that serial. It is saved in `.local\device.json`.
3. Run `02-Check-Fastboot.cmd`.

Expected results:

```text
product: sp6308a
is-userspace: no
current-slot: a
partition-size:boot_a: 2000000
unlocked: no   or yes, if already unlocked
```

`2000000` is hexadecimal: 33,554,432 bytes, or 32 MiB. If product, mode, slot or size differ, stop and keep the log. Do not remove script checks.

## 3. Save the original backup

Do this before unlocking or writing boot. If you already have a verified original backup from the same device and firmware, go to chapter 4. A backup read after modifying boot does not replace the original backup.

1. Install `.tools\drivers\UsbDk_1.0.22_x64.msi`. Restart Windows if requested. UsbDk is needed for this low-level read.
2. Turn off and disconnect the V2s. Leave only the terminal being read connected during the operation.
3. Run `03-Backup-Partitions.cmd` **as administrator**.
4. When the program is waiting, hold Volume up + Volume down and connect USB without pressing Power. Release the buttons after about 10 seconds.
5. Wait for reading and verification to finish. The displayed output path is `.local\backups\<date-time>`.
6. Keep a second copy of the original backup.

MTKClient reads GPT, boot_a, boot_b, vbmeta_a, vbmeta_b, vendor_boot_a, vendor_boot_b and seccfg. It may load a temporary agent into RAM; the wrapper requests reads only, without writing persistent partitions.

Verification covers GPT CRCs, sizes, headers, SHA-256 and boot AVB metadata. A missing final empty GPT sector is filled only if zero padding reproduces the original CRC. An incomplete read is not a usable backup.

If the buttons open Recovery, turn off and retry while the program is waiting. In the reference environment boot_b is empty: do not use it as an alternative boot slot.

## 4. Register the backup and unlock the bootloader

### Register the backup

1. Run `04-Register-Backup.cmd`.
2. Enter the path to the original backup folder.
3. Wait for `Original backup registered and verified`.

The script verifies boot, GPT, checksums and the configuration against the manifest. A BROM read does not confirm the serial through Android: connect only the configured device and use its own backup. Registration is saved under `.local`; the backup remains in the specified folder. A modified boot is not accepted as the original.

### Native unlocking

1. In Android, enable **OEM unlocking** in Developer options. If those options are hidden, tap Build number seven times in device information.
2. Return to FASTBOOT MODE and repeat `02-Check-Fastboot.cmd`.
3. Run `05-Unlock-Bootloader.cmd` **as administrator**.
4. An already unlocked bootloader skips this operation. Otherwise, type the requested phrase containing the configured serial and `ERASE DATA`.
5. Follow any confirmation shown on the V2s. User data is erased.
6. Wait for `unlocked: yes`. Reboot using `91-Reboot.cmd` or Normal Mode.
7. Complete Android setup and re-enable Developer options and USB debugging.

The command is `fastboot flashing unlock`. The toolkit does not modify seccfg to unlock the terminal. If the SUNMI code remains required, continue with boot preparation.

## 5. Prepare the modified boot

1. On the PC, open PowerShell in the project folder and run:

```text
& .\.tools\platform-tools\adb.exe start-server
```

This starts ADB and creates the PC key if needed. The expected public file is `%USERPROFILE%\.android\adbkey.pub`. Do not replace or distribute the private `adbkey` file.

2. Run `06-Build-Boot.cmd`.
3. Wait for completion without errors. The image and manifest are `.local\build\boot-patched.img` and `.local\build\boot-manifest.json`.

Preparation runs on the PC. It uses the registered original boot and ARM32 Magisk 30.7; it preserves the kernel, command line, DTB and original ramdisk files, except init replaced by Magisk. It adds a service that checks the serial and authorizes only the PC's public key after Android boots.

ADB authentication stays enabled. Embedded AVB hashes are updated without recreating the OEM signature, so the modified boot requires an unlocked bootloader. Structure and integrity are checked offline; actual boot must be verified after flashing.

## 6. Write boot_a

1. Connect the V2s in FASTBOOT MODE.
2. Repeat `02-Check-Fastboot.cmd`: the correct product, `is-userspace: no`, `unlocked: yes`, slot A and 32 MiB are required.
3. Run `07-Flash-Boot.cmd` **as administrator**.
4. After verification, type the requested phrase: `FLASH BOOT_A` followed by the configured serial.
5. Wait for `Sending ... OKAY` and `Writing ... OKAY`.
6. Following success, the script reboots the terminal. Wait for the Android home screen.

Only boot_a is written. An error stops the process without retries, erases or automatic reboot. If writing started, its outcome may be uncertain: use chapter 8 to restore if Android does not boot.

## 7. Verify ADB and install an APK

1. Leave Android at the home screen, unlocked and connected over USB.
2. Run `08-Verify-ADB.cmd`.
3. The useful result is `device` status together with `sys.boot_completed: 1`.

Additional expected results in the reference environment:

```text
id: uid=2000(shell) ...
ro.adb.secure: 1
getenforce: Enforcing
/debug_ramdisk/magisk -v: 30.7:MAGISK:R
```

The log `/data/local/tmp/sunmi-pc-adb.log` reports the serial check and the presence or addition of the public key. `uid=2000(shell)` is a normal ADB shell; installing APKs does not require a root shell.

If Magisk stays on “download in progress”, run `09-Install-Magisk.cmd` to install the included full official Magisk APK.

For another app, run `10-Install-APK.cmd`, enter the APK path and confirm `INSTALL` with the filename. The expected result is `Success`. For `Failure [INSTALL_...]`, save the complete error code before making changes to an existing app.

## 8. Restore the original boot

You need the registered original backup and an unlocked bootloader. Restoration does not depend on the modified boot image or the PC's current ADB key.

1. If Android does not boot, disconnect USB and hold Power until the terminal turns off or restarts. Use Power + Volume up for Boot Mode, then FASTBOOT MODE. From Recovery, select “reboot to bootloader”.
2. Connect USB and run `02-Check-Fastboot.cmd`.
3. Run `90-Restore-Original-Boot.cmd` **as administrator**.
4. Confirm `RESTORE BOOT_A` followed by the configured serial.
5. Wait for sending and writing confirmations. Only after success does the script select A if necessary and reboot.
6. Verify the Android home screen. ADB access provided by the modified boot may no longer be available.

Recovery writes the original backup into boot_a. Do not select B in the documented environment: boot_b is empty. Do not relock the bootloader as a remedy for a failed boot.

Restoration does not recover erased data or the entire ROM, and does not necessarily remove Magisk files or keys from userdata. If Fastboot/Recovery are unavailable or writing the original is rejected, keep backups and logs for assisted recovery.

## 9. Common problems

| Problem | Action |
| --- | --- |
| Fastboot missing or timing out | Check mode, driver, data cable and a direct USB port. Repeat only the read-only check. |
| `is-userspace: yes` | Return to the bootloader; you are in fastbootd. |
| Different product, slot or size | Stop. Do not remove checks or try an image from another firmware. |
| ADB missing while Android is running | Wait for boot, reconnect USB and check the Android interface in Device Manager. |
| ADB `unauthorized` | Accept an RSA prompt if shown. If the PC key changed, rebuild boot using the current key. |
| Error after flashing starts | Keep the log; do not retry blindly. Restore the original boot. |

Logs are under `.local\logs` and backup folders. Do not add logs, images or device configuration to Git.

References: [ADB](https://developer.android.com/tools/adb), [Windows drivers](https://developer.android.com/studio/run/win-usb), [bootloader unlocking](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking), [Magisk](https://topjohnwu.github.io/Magisk/install.html). Versions: `tools.lock.json`.
