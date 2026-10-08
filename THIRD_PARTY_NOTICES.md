# Third-party notices

The MIT license applies to project scripts and documentation. Components in the separate tool bundle retain their own licenses and notices.

- Android platform-tools: `.tools/platform-tools/NOTICE.txt` and the [Android platform-tools distribution](https://developer.android.com/tools/releases/platform-tools).
- Google USB driver: original signed driver package and its included license files; [official distribution](https://developer.android.com/studio/run/win-usb).
- UsbDk: [upstream source](https://github.com/daynix/UsbDk), Apache-2.0.
- MTKClient: `.tools/mtkclient/LICENSE`, GPL-3.0; the bundle includes [source at the pinned commit](https://github.com/bkerler/mtkclient/tree/cd25cf9c1ff6d36e82697ac2c798e69e9cfb78c3).
- Magisk: [Magisk 30.7 source](https://github.com/topjohnwu/Magisk/tree/v30.7), GPL-3.0.
- Windows magiskboot port: [build project](https://github.com/PinNaCode/magiskboot_build); an unofficial Windows build of Magisk's tool. The executable checksum is recorded in `tools.lock.json`.
- Python: `.tools/python/LICENSE.txt`. Python dependency metadata and notices are included in the corresponding `Lib/site-packages/*.dist-info` directories.

Refer to `tools.lock.json` and the bundle's `tools-manifest.json` for exact component versions and file checksums.
