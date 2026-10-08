# Tools and dependencies

The repository contains project sources and documentation. Windows executables, drivers and third-party source code are supplied separately in `sunmi-v2s-tools-windows.zip`.

Run `00-Setup-Tools.cmd` to verify that archive against `tools.lock.json`, extract it into `.tools`, and check every listed file against `tools-manifest.json`. Setup performs no USB operations. Later, `99-Verify-Tools.cmd` repeats file verification without reinstalling.

## Bundle contents

| Directory | Component | Purpose |
| --- | --- | --- |
| `python/` | Portable CPython 3.12.14 x64 and CLI dependencies | Run scripts without a system Python installation |
| `platform-tools/` | Android platform-tools 37.0.1-15733141 | ADB and native Fastboot |
| `drivers/google-usb-driver/` | Signed Google USB driver r13 | Compatible Android Bootloader Interface |
| `drivers/` | UsbDk 1.0.22 x64 installer | USB access for low-level MediaTek reads |
| `mtkclient/` | Pinned MTKClient source | Read GPT and boot-related partitions |
| `magiskboot/` | Pinned unofficial Windows magiskboot port | Offline boot unpacking and repacking |
| `apps/` | Official Magisk 30.7 APK | ARM32 boot components and full manager app |

`tools.lock.json` identifies component versions, public sources and checksums. The bundle includes third-party notices and the corresponding MTKClient source. See [Third-party notices](../THIRD_PARTY_NOTICES.md).

## Obtaining the tools

Use the companion archive matching the checksum in this repository. When distributing the project on GitHub, attach the archive to the same release as the source. Do not substitute an arbitrary archive with the same filename or edit the checksum merely to bypass a mismatch.

The public source links in `tools.lock.json` are also useful for inspection. A manual installation must reproduce the directory layout and verified file manifest; downloading newer individual components is not equivalent to installing this bundle.

## Building a release bundle

With the verified tools already installed, run:

```text
python scripts/package_tools.py
```

This packages only files listed in the public tool manifest. It checks their hashes and excludes additional files such as MTKClient device caches and logs. The archive is written under `artifacts/`; its checksum is printed. After reviewing a deliberate bundle update, use `--update-lock` to record its filename, size and checksum in `tools.lock.json`.

The bundled runtime uses paths relative to `.tools`. Project configuration and device files belong under `.local`, which is excluded from Git and from the tool archive.
