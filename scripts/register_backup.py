"""Register an original boot backup after configuring the device. No USB access."""
from pathlib import Path
import hashlib
import json
import re
import sys
from local_settings import CONFIG, LOCAL, SERIAL, require_device
from boot_format import verify
from gpt_format import partition_sizes
ROOT=Path(__file__).resolve().parents[1]
def main():
    require_device()
    serial=SERIAL
    if not re.fullmatch(r'[A-Za-z0-9_-]{4,64}',serial):raise RuntimeError('Invalid serial format.')
    folder=Path(input('Full path to your VERIFIED ORIGINAL backup folder: ').strip().strip('"')).resolve()
    data=(folder/'boot_a.bin').read_bytes()
    if len(data)!=33554432:raise RuntimeError('Expected a 32 MiB boot partition.')
    verify(data,True)  # A modified Magisk boot must not be used as the original.
    if partition_sizes((folder/'gpt.bin').read_bytes()).get('boot_a')!=33554432:raise RuntimeError('GPT boot size mismatch.')
    manifest_file=folder/'backup-manifest.json'
    if not manifest_file.exists() and (folder/'manifest-verificato.json').exists():
        manifest_file=folder/'manifest-verificato.json'
    if not manifest_file.exists():
        read=json.loads((folder/'read-manifest.json').read_text(encoding='utf-8'))
        if read.get('expected_serial')!=serial or read.get('expected_product')!='sp6308a':
            raise RuntimeError('The backup was read for a different configured device.')
        manifest={'serial':serial,'product':'sp6308a','files':read['files'],'boot_avb_hash':{'verified':True}}
    else:
        manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('serial')!=serial or manifest.get('product')!='sp6308a':raise RuntimeError('Backup identity does not match the recipient device.')
    for name in ('boot_a.bin','vbmeta_a.bin','seccfg.bin'):
        content=(folder/name).read_bytes();record=manifest['files'][name]
        if len(content)!=record['size'] or hashlib.sha256(content).hexdigest()!=record['sha256']:raise RuntimeError('Backup checksum mismatch: '+name)
    LOCAL.mkdir(exist_ok=True)
    current=json.loads(CONFIG.read_text(encoding='utf-8'))
    if current.get('backup_folder') and current['backup_folder']!=str(folder):
        if input('Replace registered backup? Type REGISTER to continue: ').strip()!='REGISTER':
            raise RuntimeError('Cancelled.')
    (LOCAL/'backup-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    current.update(backup_folder=str(folder),stock_sha256=hashlib.sha256(data).hexdigest())
    CONFIG.write_text(json.dumps(current,indent=2),encoding='utf-8')
    print('Original backup registered and verified. No USB commands were sent.')
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError,RuntimeError,AssertionError,EOFError) as error:print('STOPPED: '+str(error));sys.exit(2)
