"""Prepare and check a target-specific boot image offline. Never accesses USB."""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
from local_settings import STOCK, STOCK_SHA, SERIAL, LOCAL, TOOLS, require_backup
require_backup()
BOOT_TOOLS = TOOLS/'magiskboot'
TOOL = BOOT_TOOLS/'magiskboot.exe'
APK = TOOLS/'apps/Magisk-v30.7.apk'
BUILD = LOCAL/'build/work'
OUTPUT = LOCAL/'build'
EXPECTED_STOCK = STOCK_SHA
def sha(b): return hashlib.sha256(b).hexdigest()
assert sha(STOCK.read_bytes()) == EXPECTED_STOCK
assert sha(APK.read_bytes()) == 'e0d32d2123532860f97123d927b1bb86c4e08e6fd8a48bfc6b5bee0afae9ebd5'
assert sha(TOOL.read_bytes()) == 'bb72543569ea6ec2eb4cc55b999be96c5f624a15c8e40afbf1c6bc8d67e4063e'
import tempfile
OUTPUT.mkdir(parents=True,exist_ok=True)
BUILD=Path(tempfile.mkdtemp(prefix='work-',dir=OUTPUT))
OUTPUT.mkdir(exist_ok=True)
ENV = dict(os.environ, KEEPVERITY='true', KEEPFORCEENCRYPT='true', PATCHVBMETAFLAG='false')
LOG = []
def run(*args, codes=(0,)):
    p = subprocess.run([str(TOOL), *map(str,args)], cwd=BUILD, env=ENV,
                       capture_output=True, text=True, timeout=90)
    LOG.append({'arguments':list(map(str,args)), 'exit_code':p.returncode,
                'stdout':p.stdout, 'stderr':p.stderr})
    if p.returncode not in codes:
        raise RuntimeError(str(args)+': '+p.stderr+p.stdout)
    return p

def cpio_entries(raw):
    entries = {}; pos = 0
    while pos+110 <= len(raw):
        h=raw[pos:pos+110]
        assert h[:6] in (b'070701',b'070702')
        f=[int(h[6+i*8:14+i*8],16) for i in range(13)]
        name=raw[pos+110:pos+110+f[11]-1].decode('utf-8')
        start=(pos+110+f[11]+3)&~3; end=start+f[6]
        assert end<=len(raw)
        if name=='TRAILER!!!': break
        assert name not in entries
        entries[name]={'mode':f[1], 'uid':f[2], 'gid':f[3], 'data':raw[start:end]}
        pos=(end+3)&~3
    return entries

def boot_sections(data):
    assert data[:8]==b'ANDROID!' and struct.unpack_from('<I',data,40)[0]==2
    k,r,sec,page=(struct.unpack_from('<I',data,i)[0] for i in (8,16,24,36))
    align=lambda n:(n+page-1)//page*page
    ro=page+align(k); so=ro+align(r)
    dtbo_size,dtbo_offset=struct.unpack_from('<IQ',data,1632)
    dtb_size=struct.unpack_from('<I',data,1648)[0]
    dtb_off=so+align(sec)+align(dtbo_size)
    return {'kernel':data[page:page+k], 'ramdisk':gzip.decompress(data[ro:ro+r]),
            'second':data[so:so+sec], 'dtb':data[dtb_off:dtb_off+dtb_size],
            'recovery_dtbo':data[dtbo_offset:dtbo_offset+dtbo_size] if dtbo_size else b'',
            'header':data[:page], 'page':page,
            'cmdline':data[64:576].split(b'\0',1)[0].decode('ascii')}

run('unpack',str(STOCK))
run('cpio','ramdisk.cpio','test')
original_cpio=(BUILD/'ramdisk.cpio').read_bytes()
original=cpio_entries(original_cpio)
assert original['system/bin/init']['data'][:5]==b'\x7fELF\x01'
assert struct.unpack_from('<H',original['system/bin/init']['data'],18)[0]==40
assert b'ro.adb.secure=1\n' in original['prop.default']['data']
shutil.copyfile(BUILD/'ramdisk.cpio',BUILD/'ramdisk.cpio.orig')
with zipfile.ZipFile(APK) as z:
    for name,member in {'magiskinit':'lib/armeabi-v7a/libmagiskinit.so',
                        'magisk':'lib/armeabi-v7a/libmagisk.so',
                        'init-ld':'lib/armeabi-v7a/libinit-ld.so',
                        'stub.apk':'assets/stub.apk'}.items():
        (BUILD/name).write_bytes(z.read(member))
    (BUILD/'boot_patch.reference.sh').write_bytes(z.read('assets/boot_patch.sh'))
for name in ('magiskinit','magisk','init-ld'):
    elf=(BUILD/name).read_bytes()
    assert elf[:5]==b'\x7fELF\x01' and struct.unpack_from('<H',elf,18)[0]==40
for name in ('magisk','stub.apk','init-ld'):
    run('compress=xz',name,name+'.xz')
config=('KEEPVERITY=true\nKEEPFORCEENCRYPT=true\nRECOVERYMODE=false\nVENDORBOOT=false\n'
        +'SHA1='+hashlib.sha1(STOCK.read_bytes()).hexdigest()+'\n')
(BUILD/'config').write_text(config,encoding='ascii',newline='\n')

# Read ONLY the public key. The private adbkey is never opened or embedded.
key_source=Path(os.environ.get('USERPROFILE',str(Path.home())))/'.android/adbkey.pub'
if not key_source.is_file():
    raise RuntimeError('ADB public key missing. Run .tools/platform-tools/adb.exe start-server on this PC, then rebuild.')
key_b64=key_source.read_text(encoding='ascii').strip().split()[0]
key_raw=base64.b64decode(key_b64,validate=True)
assert len(key_raw)==524 and struct.unpack_from('<I',key_raw)[0]==64
key_line=key_b64+' sunmi-development-pc\n'
(BUILD/'sunmi-pc-adb.pub').write_text(key_line,encoding='ascii',newline='\n')
rc='''# Target-specific, late boot ADB authorization helper.
service sunmi_pc_adb /system/bin/sh ${MAGISKTMP}/sunmi-pc-adb.sh ${MAGISKTMP}
    user root
    group root shell
    disabled
    oneshot
    seclabel u:r:magisk:s0

on property:sys.boot_completed=1
    start sunmi_pc_adb

on property:sys.sunmi.pc_adb_ready=1
    restart adbd
'''
script='''#!/system/bin/sh
# Authorize only the bundled public key of the development PC.
# Runs once after Android boot completes; no partition writes or app removal.
set -eu
[ "$(/system/bin/getprop ro.serialno)" = "DEVICE_SERIAL" ] || exit 10
[ "$(/system/bin/getprop sys.boot_completed)" = "1" ] || exit 11
base="$1"
key="$base/sunmi-pc-adb.pub"
dest=/data/misc/adb/adb_keys
[ -f "$key" ] && [ -d /data/misc/adb ] || exit 12
[ ! -L "$dest" ] || exit 13
umask 077
log=/data/local/tmp/sunmi-pc-adb.log
exec >"$log" 2>&1
/system/bin/chmod 0644 "$log"
echo "SUNMI development helper: boot completed, serial checked."
key_id="$(/system/bin/cut -d ' ' -f 1 "$key")"
if [ -f "$dest" ] && /system/bin/grep -Fq "$key_id" "$dest"; then
    echo "PC key already present."
else
    if [ -f "$dest" ] && [ ! -e "$dest.sunmi_pc_before" ]; then
        /system/bin/cp -p "$dest" "$dest.sunmi_pc_before"
        /system/bin/chmod 0600 "$dest.sunmi_pc_before"
    fi
    printf '\\n' >>"$dest"
    /system/bin/cat "$key" >>"$dest"
    echo "PC public key added."
fi
/system/bin/chown 0:2000 "$dest"
/system/bin/chmod 0640 "$dest"
/system/bin/restorecon "$dest"
echo "ADB authentication stays enabled; restarting adbd."
/system/bin/setprop sys.sunmi.pc_adb_ready 1
'''
script=script.replace('DEVICE_SERIAL',SERIAL)
(BUILD/'sunmi-pc-adb.rc').write_text(rc,encoding='ascii',newline='\n')
(BUILD/'sunmi-pc-adb.sh').write_text(script,encoding='ascii',newline='\n')
commands=['add 0750 init magiskinit','mkdir 0750 overlay.d','mkdir 0750 overlay.d/sbin',
          'add 0644 overlay.d/sbin/magisk.xz magisk.xz',
          'add 0644 overlay.d/sbin/stub.xz stub.apk.xz',
          'add 0644 overlay.d/sbin/init-ld.xz init-ld.xz',
          'add 0644 overlay.d/sunmi-pc-adb.rc sunmi-pc-adb.rc',
          'add 0644 overlay.d/sbin/sunmi-pc-adb.pub sunmi-pc-adb.pub',
          'add 0750 overlay.d/sbin/sunmi-pc-adb.sh sunmi-pc-adb.sh',
          'patch','backup ramdisk.cpio.orig','mkdir 000 .backup','add 000 .backup/.magisk config']
run('cpio','ramdisk.cpio',*commands)
run('cpio','ramdisk.cpio','test',codes=(1,))
patched_cpio=(BUILD/'ramdisk.cpio').read_bytes()
patched=cpio_entries(patched_cpio)
assert patched['init']['data']==(BUILD/'magiskinit').read_bytes()
assert patched['.backup/.magisk']['data']==config.encode('ascii')
# Keep all original files except /init byte-for-byte (including security props and fstabs).
for name,e in original.items():
    if name!='init':
        assert patched[name]==e, 'Unexpected ramdisk change: '+name
assert patched['overlay.d/sbin/sunmi-pc-adb.pub']['data']==key_line.encode('ascii')
assert patched['overlay.d/sunmi-pc-adb.rc']['data']==rc.encode('ascii')
assert patched['overlay.d/sbin/sunmi-pc-adb.sh']['data']==script.encode('ascii')
# Check the built-in restore restores all original files and removes added files.
shutil.copyfile(BUILD/'ramdisk.cpio',BUILD/'restore-test.cpio')
run('cpio','restore-test.cpio','restore')
assert cpio_entries((BUILD/'restore-test.cpio').read_bytes())==original
if (BUILD/'kernel').exists():
    (BUILD/'kernel').unlink()  # repacker uses raw original kernel
run('repack',str(STOCK),'sunmi-debug-boot.img')
image=(BUILD/'sunmi-debug-boot.img').read_bytes()
before,after=boot_sections(STOCK.read_bytes()),boot_sections(image)
checks={name:before[name]==after[name] for name in ('kernel','second','dtb','recovery_dtbo','cmdline','page')}
assert all(checks.values())
assert after['ramdisk']==patched_cpio and len(image)==STOCK.stat().st_size
assert len(before['dtb'])==103319
# Only ramdisk size and boot checksum may differ in the boot header.
expected_header=bytearray(before['header'])
expected_header[16:20]=after['header'][16:20]
expected_header[576:608]=after['header'][576:608]
assert bytes(expected_header)==after['header']
from boot_format import correct
image,metadata_checks=correct(image,STOCK.read_bytes())
(OUTPUT/'boot-patched.img').write_bytes(image)
for name in ('sunmi-pc-adb.rc','sunmi-pc-adb.sh','config'):
    shutil.copyfile(BUILD/name,OUTPUT/name)
manifest={'serial':SERIAL,'product':'sp6308a','slot':'a','android_version':12,
          'image':'boot-patched.img','size':len(image),'sha256':sha(image),
          'stock_sha256':EXPECTED_STOCK,'stock_backup':str(STOCK),
          'magisk_version':'v30.7','magisk_abi':'armeabi-v7a',
          'magisk_apk_sha256':sha(APK.read_bytes()),
          'repacker':'PinNaCode/magiskboot_build, unofficial Windows port, magiskboot b22b6a4',
          'repacker_sha256':sha(TOOL.read_bytes()),
          'adb_public_key_sha256':sha(key_raw),
          'keep_verity':True,'keep_force_encrypt':True,'patch_vbmeta_flags':False,
          'unchanged_sections':checks,'original_ramdisk_files_preserved_except_init':True,
          'cpio_restore_verified':True,'hardware_boot_verified':False,
          'image_restricted_to_ram_test':False, 'force_normal_boot_in_image':False,
          'metadata_correction_verified':metadata_checks,
          'notes':['Image is modified and no longer carries a valid SUNMI OEM signature.',
                   'No vbmeta/system/vendor partition is modified.',
                   'Runtime helper appends this PC public ADB key in userdata and restarts adbd.',
                   'Magisk may create files in /data/adb and install its stub app.',
                   'This rebuilt image has been checked offline, not flashed or booted. Boot and ADB must be verified on the device after flashing.']}
(OUTPUT/'boot-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(OUTPUT/'preparation-log.json').write_text(json.dumps(LOG,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
