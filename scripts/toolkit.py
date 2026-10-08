"""SUNMI V2s toolkit. Offline by default; USB actions require --apply.

Requires local configuration for the recipient device and verified original boot.
No erase, lock, boot_b, vbmeta, system, vendor or seccfg writes.
"""
from pathlib import Path
import argparse
import base64
import ctypes
from contextlib import redirect_stdout
from datetime import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
from local_settings import SERIAL, PRODUCT, SIZE, STOCK, STOCK_SHA, BACKUP, LOCAL, TOOLS, require_device, require_backup, configure_device
PATCHED = LOCAL / 'build/boot-patched.img'
FASTBOOT = TOOLS / 'platform-tools/fastboot.exe'
ADB = TOOLS / 'platform-tools/adb.exe'

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def check_file(path, expected, size=None):
    if not path.is_file() or (size is not None and path.stat().st_size != size) or digest(path) != expected:
        raise RuntimeError('Missing, damaged or unverified file: ' + str(path))

def inventory_check(paths=None):
    entries = json.loads((TOOLS / 'tools-manifest.json').read_text(encoding='utf-8'))['files']
    selected = entries if paths is None else {p: entries[p] for p in paths}
    for relative, record in selected.items():
        check_file(TOOLS / relative, record['sha256'], record['size'])
    print('Verified files: ' + str(len(selected)), flush=True)

def check_tool(tool):
    names = [tool.name, 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'libwinpthread-1.dll']
    inventory_check(['platform-tools/' + n for n in names])

def parse_partition_size(value):
    if not re.fullmatch(r'(?:0[xX])?[0-9a-fA-F]+', value):
        raise RuntimeError('Unrecognized partition size: ' + value)
    return int(value, 16)  # This bootloader reports 2000000 as implicit hexadecimal.

def public_key_hash(path):
    if path.name.lower() != 'adbkey.pub':
        raise RuntimeError('Select adbkey.pub, never the private adbkey file.')
    raw = base64.b64decode(path.read_text(encoding='ascii').split()[0], validate=True)
    if len(raw) != 524 or int.from_bytes(raw[:4], 'little') != 64:
        raise RuntimeError('Invalid Android RSA public key.')
    return hashlib.sha256(raw).hexdigest()

def check_backup():
    require_backup()
    manifest = json.loads((LOCAL / 'backup-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('serial') != SERIAL or manifest.get('product') != PRODUCT or not manifest.get('boot_avb_hash', {}).get('verified'):
        raise RuntimeError('Original backup identity or AVB verification is invalid.')
    for name in ('boot_a.bin', 'vbmeta_a.bin', 'seccfg.bin'):
        record = manifest['files'][name]
        check_file(BACKUP / name, record['sha256'], record['size'])
    check_file(STOCK, STOCK_SHA, SIZE)
    from gpt_format import partition_sizes
    from boot_format import verify
    sizes = partition_sizes((BACKUP / 'gpt.bin').read_bytes())
    if sizes.get('boot_a') != SIZE:
        raise RuntimeError('Original GPT boot size mismatch.')
    verify(STOCK.read_bytes(), True)

class Tee:
    def __init__(self, screen, log):
        self.screen, self.log = screen, log
    def write(self, text):
        self.screen.write(text); self.log.write(text)
    def flush(self):
        self.screen.flush(); self.log.flush()

def check_image(mode):
    require_backup()
    check_file(STOCK, STOCK_SHA, SIZE)
    if STOCK.read_bytes()[:8] != b'ANDROID!':
        raise RuntimeError('Invalid original boot header.')
    if mode == 'restore':
        return STOCK  # Restoration is independent of the patched image and PC key.
    folder = LOCAL / 'build'
    manifest = json.loads((folder / 'boot-manifest.json').read_text(encoding='utf-8'))
    image = folder / 'boot-patched.img'
    expected = manifest['sha256']
    check_file(image, expected, SIZE)
    checks = manifest.get('metadata_correction_verified', {})
    required = {'serial': SERIAL, 'product': PRODUCT, 'stock_sha256': STOCK_SHA,
                'magisk_abi': 'armeabi-v7a', 'cpio_restore_verified': True,
                'keep_verity': True, 'keep_force_encrypt': True,
                'patch_vbmeta_flags': False, 'image_restricted_to_ram_test': False,
                'force_normal_boot_in_image': False}
    if any(manifest.get(k) != v for k, v in required.items()):
        raise RuntimeError('Inconsistent persistent boot manifest.')
    if not all(checks.get(k) is True for k in ('embedded_boot_hash_verified', 'embedded_vbmeta_auth_hash_verified')) or checks.get('vbmeta_flags') != 0:
        raise RuntimeError('Boot metadata checks are incomplete.')
    original, patched = STOCK.read_bytes(), image.read_bytes()
    if patched[:8] != b'ANDROID!' or any(original[a:b] != patched[a:b] for a,b in ((64,576),(608,1632))):
        raise RuntimeError('Original kernel command line was changed.')
    from boot_format import verify, boot_sections, cpio_entries
    verify(original, True)
    verify(patched, False)
    before, after = boot_sections(original), boot_sections(patched)
    if any(before[n] != after[n] for n in ('kernel','second','dtb','recovery_dtbo','cmdline','page')):
        raise RuntimeError('Unexpected change to original boot sections.')
    key = Path(os.environ.get('USERPROFILE', str(Path.home()))) / '.android/adbkey.pub'
    expected_key = manifest['adb_public_key_sha256']
    if public_key_hash(key) != expected_key:
        raise RuntimeError('This PC has a different ADB public key. Use the offline rebuild step; do not copy private keys.')
    ramdisk = cpio_entries(after['ramdisk'])
    embedded = base64.b64decode(ramdisk['overlay.d/sbin/sunmi-pc-adb.pub']['data'].split()[0], validate=True)
    if hashlib.sha256(embedded).hexdigest() != expected_key:
        raise RuntimeError('The embedded public key differs from the verified PC key.')
    return image

class FastbootSession:
    def __init__(self, runner=subprocess.run, log=None):
        self.runner, self.log = runner, log
        self.preflight_complete = False
        self.flash_succeeded = False
        self.mode = None
        self.image = None
        self.slot = None
        self.unlock_ready = False
        self.reboot_allowed = False

    def say(self, message):
        print(message, flush=True)
        if self.log:
            self.log.write(message + '\n'); self.log.flush()

    def run(self, args, timeout=20):
        allowed = len(args) == 2 and args[0] == 'getvar'
        if args == ['flashing', 'get_unlock_ability']:
            allowed = self.unlock_ready
        elif args == ['flashing', 'unlock']:
            allowed = self.unlock_ready
        elif args == ['flash', 'boot_a', str(self.image)]:
            allowed = self.preflight_complete and not self.flash_succeeded
        elif args == ['set_active', 'a']:
            allowed = self.mode == 'restore' and self.flash_succeeded and self.slot == 'b'
        elif args == ['reboot']:
            allowed = self.flash_succeeded or self.reboot_allowed
        if not allowed:
            raise RuntimeError('Command rejected: checks are incomplete or action is outside this toolkit.')
        self.say('Command: fastboot -s ' + SERIAL + ' ' + ' '.join(args))
        r = self.runner([str(FASTBOOT), '-s', SERIAL, *args], capture_output=True,
                        text=True, errors='replace', timeout=timeout)
        output = r.stdout + r.stderr
        self.say(output)
        if r.returncode or 'FAILED' in output:
            raise RuntimeError('Command failed. No automatic retry, erase or reboot will follow.')
        return output

    def getvar(self, name):
        output = self.run(['getvar', name])
        m = re.search(r'^(?:\(bootloader\)\s*)?' + re.escape(name) + r':\s*(.*?)\s*$', output, re.M)
        if not m:
            raise RuntimeError('Unrecognized getvar response: ' + name)
        return m.group(1)

    def identity(self, require_unlocked=True):
        for name, expected in [('product', PRODUCT), ('is-userspace', 'no')]:
            if self.getvar(name) != expected:
                raise RuntimeError('Wrong device or Fastboot mode: ' + name)
        state = self.getvar('unlocked')
        if state not in ('yes', 'no') or (require_unlocked and state != 'yes'):
            raise RuntimeError('Bootloader is not in the expected unlocked state.')
        self.slot = self.getvar('current-slot')
        if self.slot not in ('a', 'b'):
            raise RuntimeError('Unknown active slot.')
        size = parse_partition_size(self.getvar('partition-size:boot_a'))
        if size != SIZE:
            raise RuntimeError('Unexpected boot_a size. Expected 2000000 hex = 33554432 bytes = 32 MiB.')
        return state

    def flash(self, mode, image, confirmer):
        self.mode, self.image = mode, image
        self.identity()
        if mode == 'install' and self.slot != 'a':
            raise RuntimeError('Installation requires active slot A.')
        confirmer(('RESTORE' if mode == 'restore' else 'FLASH') + ' BOOT_A ' + SERIAL)
        self.preflight_complete = True
        self.run(['flash', 'boot_a', str(image)], timeout=120)
        self.flash_succeeded = True
        if mode == 'restore' and self.slot == 'b':
            self.run(['set_active', 'a'])
        self.run(['reboot'])
        self.say('Fastboot confirmed writing and reboot. Partition readback was not performed; verify Android separately.')

    def unlock(self, confirmer):
        state = self.identity(require_unlocked=False)
        if state == 'yes':
            self.say('Already unlocked: skipping unlock and data wipe.'); return
        if self.slot != 'a':
            raise RuntimeError('Native unlock requires the recorded slot A.')
        self.unlock_ready = True
        output = self.run(['flashing', 'get_unlock_ability'])
        m = re.search(r'unlock_ability\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)', output)
        if not m or int(m.group(1), 0) not in (1, 16777216):
            raise RuntimeError('OEM unlock authorization is not recognized.')
        confirmer('UNLOCK ' + SERIAL + ' ERASE DATA')
        self.say('Follow the confirmation instructions on the device. User data will be erased.')
        self.run(['flashing', 'unlock'], timeout=180)
        if self.getvar('unlocked') != 'yes':
            raise RuntimeError('Unlock is not confirmed. Check the current state before repeating anything.')
        self.say('Unlock confirmed. No automatic reboot. Select Normal Mode or use the reboot script.')

def confirm(phrase):
    print('To continue, type exactly: ' + phrase, flush=True)
    if input('Confirmation: ').strip() != phrase:
        raise RuntimeError('Cancelled. No requested write command was sent.')

def adb_run(args, timeout=25, runner=subprocess.run, required=True):
    print('Command: adb -s ' + SERIAL + ' ' + ' '.join(args), flush=True)
    r = runner([str(ADB), '-s', SERIAL, *args], capture_output=True, text=True, errors='replace', timeout=timeout)
    print(r.stdout + r.stderr, flush=True)
    if r.returncode:
        if not required:
            print('Optional diagnostic unavailable; ADB access remains usable.', flush=True)
            return ''
        raise RuntimeError('ADB command failed. Check the USB driver, Android startup and authorization status.')
    return r.stdout.strip()

def verify_adb(wait=45):
    end = time.monotonic() + wait
    while True:
        r = subprocess.run([str(ADB), '-s', SERIAL, 'get-state'], capture_output=True,
                           text=True, errors='replace', timeout=10)
        state = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and r.stdout.strip() == 'device':
            print('ADB state: device', flush=True)
            break
        print('ADB state: ' + state, flush=True)
        if 'unauthorized' in state or time.monotonic() >= end:
            raise RuntimeError('ADB is not authorized/available. Follow the troubleshooting section; no automatic device changes.')
        time.sleep(3)
    if adb_run(['shell', 'getprop', 'ro.serialno']) != SERIAL:
        raise RuntimeError('Android serial does not match this device.')
    if adb_run(['shell', 'getprop', 'sys.boot_completed']) != '1':
        raise RuntimeError('Android has not finished booting. Wait and rerun this read-only check.')
    for command in [['id'], ['getprop','ro.build.fingerprint'], ['getprop','ro.product.cpu.abilist'],
                    ['getprop','ro.adb.secure'], ['getenforce'], ['getprop','sys.usb.config']]:
        adb_run(['shell', *command])
    for command in [['cat','/data/local/tmp/sunmi-pc-adb.log'], ['/debug_ramdisk/magisk','-v']]:
        adb_run(['shell', *command], required=False)
    print('Authenticated ADB is working. uid=2000(shell) is the normal ADB shell, not root.', flush=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['configure','devices','verify-tools','check-fastboot','unlock','install','restore','verify-adb','install-magisk','install-apk','reboot'])
    p.add_argument('--apk', type=Path, help='APK file to install.')
    p.add_argument('--apply', action='store_true', help='Enable the selected USB action. Write actions also require a typed confirmation.')
    p.add_argument('--serial', help='Device serial to store locally for subsequent commands.')
    a = p.parse_args()
    if a.action == 'configure':
        configure_device(a.serial or input('Device serial: ').strip()); return 0
    if a.action == 'devices':
        check_tool(FASTBOOT)
        if not a.apply:
            print('Offline plan: fastboot devices. Use --apply to list connected devices.'); return 0
        r = subprocess.run([str(FASTBOOT), 'devices'], capture_output=True, text=True, errors='replace', timeout=20)
        print(r.stdout + r.stderr)
        return r.returncode
    if a.action == 'verify-tools':
        inventory_check(); print('Tool integrity verification passed. No USB access.'); return 0
    require_device()
    tool = ADB if a.action in ('verify-adb','install-magisk','install-apk') else FASTBOOT
    check_tool(tool)
    image = None
    if a.action in ('install','restore'):
        check_backup()
        image = check_image(a.action)
    if a.action == 'unlock':
        check_backup()
    app = None
    if a.action == 'install-magisk':
        name = 'Magisk-v30.7.apk'
        inventory_check(['apps/' + name]); app = TOOLS / 'apps' / name
    elif a.action == 'install-apk':
        app = a.apk or Path(input('Full path to your APK: ').strip().strip('"'))
        if not app.is_file() or app.suffix.lower() != '.apk':
            raise RuntimeError('Select an existing APK file.')
        print('Recipient APK SHA-256: ' + digest(app))
    if not a.apply:
        print('Offline checks passed. USB action disabled. Use --apply or the corresponding CMD launcher.')
        return 0
    if a.action in ('unlock','install','restore') and not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('Right-click the CMD launcher and choose Run as administrator.')
    (LOCAL / 'logs').mkdir(parents=True, exist_ok=True)
    path = LOCAL / 'logs' / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + a.action + '.txt')
    with path.open('w', encoding='utf-8') as log, redirect_stdout(Tee(sys.stdout, log)):
        session = FastbootSession()
        try:
            if a.action == 'check-fastboot':
                session.identity(False); print('Fastboot identity and partition size verified.')
            elif a.action == 'unlock': session.unlock(confirm)
            elif a.action in ('install','restore'): session.flash(a.action, image, confirm)
            elif a.action == 'reboot':
                session.identity(False); session.reboot_allowed = True; session.run(['reboot'])
            elif a.action == 'verify-adb': verify_adb()
            elif app is not None:
                verify_adb(wait=0)
                confirm('INSTALL ' + app.name)
                result = adb_run(['install','-r',str(app)], timeout=180)
                if 'Success' not in result:
                    raise RuntimeError('APK installation was not confirmed. The reported package error is preserved above.')
                print('APK installed. Open it on the device.')
        except Exception:
            if session.preflight_complete:
                session.say('A write may have occurred, possibly partially. No automatic retry or reboot. Use original boot restoration if Android does not start.')
            raise
    print('Log: ' + str(path))
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired, AssertionError, EOFError) as error:
        print('STOPPED: ' + str(error), flush=True)
        sys.exit(2)
