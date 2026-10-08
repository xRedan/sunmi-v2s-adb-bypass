# SUNMI V2s USB Debugging Toolkit

[Step-by-step guide](docs/guide-en.md) · [Recovery](docs/guide-en.md#8-restore-the-original-boot)

To use the thermal printer, check out this repository: [sunmi-mobile-printer](https://github.com/xRedan/sunmi-mobile-printer)

Bypass SUNMI's developer-account and device-linking requirements for USB debugging on supported SUNMI V2s devices. This toolkit enables authenticated ADB access and APK installation without registering a SUNMI developer account or linking the terminal to that account.

The procedure requires an available OEM bootloader unlock option. It backs up the original boot partitions, uses native Fastboot unlocking, prepares a device-specific boot image with Magisk, and authorizes the development PC's public ADB key.

The intended result is `adb` reporting `device` and allowing APK installation. The SUNMI account-code prompt may remain in Settings; this toolkit does not change account ownership or remote-management enrollment.

## Supported environment

Reference device: **SUNMI V2s**, Android 12, Fastboot product `sp6308a`, firmware `SP3115GO-Sunmi-20240130193859`, ARM32, active slot A, 32 MiB `boot_a`.

The scripts check product, bootloader mode, unlock state, slot, partition size, image integrity and the PC key. A different firmware requires compatibility verification and an original backup from that device. No ready-made device boot image is distributed.

**Unlocking erases user data. Flashing changes boot_a persistently.** Obtain and verify the original backup before either operation. Restoration writes the saved original boot_a; it is not a full firmware or userdata restore.

## Getting started

1. Extract or clone this repository, for example to `C:\sunmi-v2s-adb-toolkit`. Paths with spaces are supported.
2. Obtain the companion **`sunmi-v2s-tools-windows.zip`** and place it next to the repository folder. Run `00-Setup-Tools.cmd`. It checks the bundle hash in `tools.lock.json` and installs tools under `.tools`.
3. Follow the [step-by-step guide](docs/guide-en.md), starting with drivers and device identification.

The bundle contains portable Python, Android platform-tools, drivers, pinned MTKClient source, the Windows magiskboot port and the official Magisk APK. See [Tools and dependencies](docs/TOOLS.md).

If ADB already works, configure the device and use `08-Verify-ADB.cmd` or `10-Install-APK.cmd`. Unlocking and flashing are unnecessary for that path.

## Workflow

| Step | Launcher | Purpose |
| --- | --- | --- |
| 0 | `00-Setup-Tools.cmd` | Install and verify public tools |
| 1 | `01-Configure-Device.cmd` | Save the device serial locally |
| 2 | `02-Check-Fastboot.cmd` | Read-only identity and bootloader checks |
| 3 | `03-Backup-Partitions.cmd` | Read GPT and seven boot-related partitions |
| 4 | `04-Register-Backup.cmd` | Verify and register the original backup |
| 5 | `05-Unlock-Bootloader.cmd` | Native unlock with data-wipe confirmation |
| 6 | `06-Build-Boot.cmd` | Prepare and verify the modified boot offline |
| 7 | `07-Flash-Boot.cmd` | Flash boot_a and reboot after successful writing |
| 8 | `08-Verify-ADB.cmd` | Verify authenticated Android access |
| 9 | `09-Install-Magisk.cmd` | Install the full official Magisk app |
| 10 | `10-Install-APK.cmd` | Install a selected local APK |
| Recovery | `90-Restore-Original-Boot.cmd` | Restore the verified original boot_a |

`02a-List-Devices.cmd` lists Fastboot devices. `91-Reboot.cmd` reboots from bootloader Fastboot. `99-Verify-Tools.cmd` checks tools without USB access.

## Repository layout

```text
scripts/          English Python and PowerShell sources
tests/            Offline tests using synthetic device identifiers
docs/             English guide and PDF copy
tools.lock.json   Public component versions and bundle hash
.tools/           Installed tools; ignored by Git
.local/           Configuration, backups, builds and logs; ignored by Git
```

Keep device data under `.local`. Never force-add that directory, ADB keys, boot images or logs. The tool bundle belongs in a release attachment, rather than Git history.

## Development

Using Python 3.12:

```text
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Tests mock USB commands. They exercise configuration ordering, wrong-device checks, cancellation, failed flashing and recovery independence from the modified image/PC key. They do not unlock or flash a connected terminal.

Project scripts and documentation use the [MIT license](LICENSE); third-party tools retain their own licenses.
