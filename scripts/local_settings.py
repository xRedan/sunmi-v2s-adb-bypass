"""Local device configuration. Device data is stored outside version-controlled files."""
from pathlib import Path
import json
import re
ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'.tools'
LOCAL=ROOT/'.local'
CONFIG=LOCAL/'device.json'
config=json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
SERIAL=config.get('serial','')
PRODUCT='sp6308a'
SIZE=33554432
BACKUP=Path(config.get('backup_folder',str(LOCAL/'MISSING-BACKUP')))
STOCK=BACKUP/'boot_a.bin'
STOCK_SHA=config.get('stock_sha256','')

def require_device():
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{3,63}',SERIAL):
        raise RuntimeError('Run 01-Configure-Device.cmd first. A backup is not required for device checks.')

def require_backup():
    require_device()
    if not re.fullmatch(r'[0-9a-f]{64}',STOCK_SHA) or not STOCK.is_file() or not (LOCAL/'backup-manifest.json').is_file():
        raise RuntimeError('Run 04-Register-Backup.cmd with the original backup before building, unlocking or flashing.')

def configure_device(serial):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{3,63}',serial):
        raise RuntimeError('Invalid device serial format.')
    current=json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
    if current.get('serial') and current['serial']!=serial:
        if input('Changing device clears backup registration. Type CHANGE to continue: ').strip()!='CHANGE':
            raise RuntimeError('Cancelled.')
        current={}
    current.update(serial=serial,product=PRODUCT)
    LOCAL.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(current,indent=2),encoding='utf-8')
    print('Device configured. Next: 02-Check-Fastboot.cmd. Backup registration is a separate step.')
