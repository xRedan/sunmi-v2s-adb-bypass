"""Read GPT and seven boot-related partitions. Default: offline plan.
Loads a temporary MediaTek RAM agent, never writes a persistent partition.
"""
from pathlib import Path
from datetime import datetime
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from gpt_format import complete_gpt_export,partition_sizes
from boot_format import verify
from toolkit import inventory_check
from local_settings import STOCK_SHA,SERIAL,PRODUCT,LOCAL,TOOLS,require_device
ROOT=Path(__file__).resolve().parents[1]
PARTS=('boot_a','boot_b','vbmeta_a','vbmeta_b','vendor_boot_a','vendor_boot_b','seccfg')

def read_commands(folder,source):
    # MTKClient's script parser splits on spaces without processing quotes.
    # Relative output paths avoid spaces in the absolute project path.
    relative=Path(os.path.relpath(folder,source))
    if ' ' in str(relative): raise RuntimeError('Backup output relative path must not contain spaces.')
    return 'gpt '+str(relative)+'\n'+'r '+','.join(PARTS)+' '+','.join(str(relative/(part+'.bin')) for part in PARTS)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--read',action='store_true',help='Run the read-only USB backup; otherwise just show the plan.')
    a=p.parse_args()
    require_device()
    inventory_check([n for n in json.loads((TOOLS/'tools-manifest.json').read_text())['files'] if n.startswith('mtkclient/')])
    if not a.read:
        print('Offline plan: GPT + r for '+','.join(PARTS)+'. No USB access.'); return 0
    if not ctypes.windll.shell32.IsUserAnAdmin(): raise RuntimeError('Run the CMD launcher as administrator.')
    if shutil.disk_usage(ROOT).free<2*1024**3: raise RuntimeError('At least 2 GiB of free disk space is required.')
    folder=LOCAL/'backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    commands=folder/'read-commands.txt'
    source=TOOLS/'mtkclient'
    commands.write_text(read_commands(folder,source),encoding='utf-8')
    print('Power OFF. Hold Volume + and Volume -, connect USB, do not press Power. Release after about 10 seconds.',flush=True)
    print('Reads storage only. A temporary agent may run in RAM. Backup output: '+str(folder),flush=True)
    with (folder/'read-log.txt').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-B','-u',str(source/'mtk.py'),'script',str(commands)],cwd=source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
        expired=threading.Event()
        def stop():
            if process.poll() is None: expired.set();process.terminate()
        timer=threading.Timer(900,stop);timer.start()
        try:
            for line in process.stdout:
                print(line.rstrip(),flush=True);log.write(line);log.flush()
            code=process.wait()
        finally:
            timer.cancel()
            if process.poll() is None: process.terminate();process.wait()
    if code or expired.is_set(): raise RuntimeError('Read incomplete. Files are not yet verified. No automatic retry.')
    gpt=(folder/'gpt.bin').read_bytes(); full=complete_gpt_export(gpt);sizes=partition_sizes(full)
    (folder/'gpt-reconstructed.bin').write_bytes(full)
    records={}
    for part in PARTS:
        data=(folder/(part+'.bin')).read_bytes()
        if len(data)!=sizes[part]: raise RuntimeError('Partition size mismatch: '+part)
        blank=not any(data)
        magic=b'ANDROID!' if part.startswith('boot_') else b'VNDRBOOT' if part.startswith('vendor_boot_') else b'AVB0' if part.startswith('vbmeta_') else b'MMMM\x04\0\0\0'
        if not blank and not data.startswith(magic): raise RuntimeError('Invalid partition header: '+part)
        if part in ('boot_a','vbmeta_a') and blank: raise RuntimeError('Active partition is empty: '+part)
        records[part+'.bin']={'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'all_zero':blank}
    boot=(folder/'boot_a.bin').read_bytes()
    original=records['boot_a.bin']['sha256']==STOCK_SHA if STOCK_SHA else True
    checks=verify(boot,original)
    manifest={'serial':'NOT_CHECKED_IN_BROM','expected_serial':SERIAL,'expected_product':PRODUCT,'files':records,'gpt_partition_sizes':sizes,'original_stock_boot_matches':original,'boot_checks':checks,'userdata_included':False}
    (folder/'read-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Backup verified; original stock boot match: '+str(original))
    print('This is not a full device/userdata backup. Output is stored in .local/backups, which Git ignores.')
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,ValueError,KeyError,RuntimeError,AssertionError,subprocess.TimeoutExpired) as error:
        print('STOPPED: '+str(error));sys.exit(2)
