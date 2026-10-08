"""Offline workflow tests. No real ADB, Fastboot or MediaTek commands."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import local_settings as settings
import toolkit
import package_tools
import backup_partitions
import zipfile
TEST_ROOT=Path(__file__).resolve().parents[1]/'artifacts/test-tmp'
TEST_ROOT.mkdir(parents=True,exist_ok=True)
assert TEST_ROOT.resolve().is_relative_to(Path(__file__).resolve().parents[1])

class FakeFastboot:
    def __init__(self,overrides=None,fail_flash=False):
        self.values={'product':'sp6308a','is-userspace':'no','unlocked':'yes','current-slot':'a','partition-size:boot_a':'2000000'}
        self.values.update(overrides or {});self.calls=[];self.fail_flash=fail_flash
    def __call__(self,command,**kwargs):
        self.calls.append(command[3:]);args=command[3:]
        if args[0]=='getvar':return subprocess.CompletedProcess(command,0,'',args[1]+': '+self.values[args[1]]+'\n')
        if args==['flashing','get_unlock_ability']:return subprocess.CompletedProcess(command,0,'','unlock_ability = 16777216')
        if args==['flashing','unlock']:self.values['unlocked']='yes'
        failed=self.fail_flash and args[0]=='flash'
        return subprocess.CompletedProcess(command,1 if failed else 0,'','FAILED' if failed else 'OKAY')

class ConfigurationTests(unittest.TestCase):
    def test_backup_command_paths_support_spaces_in_project_location(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            project=Path(folder)/'Github Project'/'toolkit'
            source=project/'.tools'/'mtkclient'
            output=project/'.local'/'backups'/'test-backup'
            commands=backup_partitions.read_commands(output,source).splitlines()
            gpt=commands[0].split(' ');read=commands[1].split(' ')
            self.assertEqual(len(gpt),2)
            self.assertEqual(len(read),3)
            self.assertEqual((source/gpt[1]).resolve(),output.resolve())
            self.assertEqual(read[1].split(','),list(backup_partitions.PARTS))
            self.assertEqual([(source/part).resolve() for part in read[2].split(',')],[(output/(part+'.bin')).resolve() for part in backup_partitions.PARTS])
    def test_fastboot_check_runs_with_serial_only_configuration(self):
        fake=FakeFastboot({'unlocked':'no'})
        session=toolkit.FastbootSession(runner=fake)
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            with patch.object(sys,'argv',['tool','check-fastboot','--apply']),patch.object(settings,'SERIAL','TEST_DEVICE'),patch.object(toolkit,'SERIAL','TEST_DEVICE'),patch.object(toolkit,'LOCAL',Path(folder)),patch.object(toolkit,'check_tool'),patch.object(toolkit,'check_backup') as backup,patch.object(toolkit,'FastbootSession',return_value=session):
                self.assertEqual(toolkit.main(),0)
                backup.assert_not_called()
        self.assertEqual(len(fake.calls),5)
        self.assertTrue(all(c[0]=='getvar' for c in fake.calls))
    def test_device_configuration_does_not_require_backup(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            local=Path(folder);config=local/'device.json'
            with patch.object(settings,'LOCAL',local),patch.object(settings,'CONFIG',config):
                settings.configure_device('TEST_DEVICE')
                self.assertEqual(json.loads(config.read_text())['serial'],'TEST_DEVICE')
                with patch.object(settings,'SERIAL','TEST_DEVICE'):
                    settings.require_device()
                    with self.assertRaises(RuntimeError):settings.require_backup()
    def test_missing_device_stops_before_usb(self):
        with patch.object(sys,'argv',['tool','check-fastboot','--apply']),patch.object(settings,'SERIAL',''),patch.object(toolkit.subprocess,'run') as runner:
            with self.assertRaises(RuntimeError):toolkit.main()
            runner.assert_not_called()
    def test_changing_device_clears_registered_backup(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            config=Path(folder)/'device.json';config.write_text(json.dumps({'serial':'FIRST_DEVICE','backup_folder':'old','stock_sha256':'0'*64}))
            with patch.object(settings,'LOCAL',Path(folder)),patch.object(settings,'CONFIG',config),patch('builtins.input',return_value='CHANGE'):
                settings.configure_device('SECOND_DEVICE')
                self.assertNotIn('backup_folder',json.loads(config.read_text()))
    def test_invalid_serial_not_saved(self):
        for serial in ('','*','--all','a b'):
            with self.assertRaises(RuntimeError):settings.configure_device(serial)

class FlashGuardTests(unittest.TestCase):
    def setUp(self):self.patcher=patch.object(toolkit,'SERIAL','TEST_DEVICE');self.patcher.start()
    def tearDown(self):self.patcher.stop()
    def flash(self,fake,mode='install',confirm=lambda _:None):
        s=toolkit.FastbootSession(runner=fake,log=io.StringIO());s.flash(mode,Path('test.img'),confirm)
    def test_hex_size(self):self.assertEqual(toolkit.parse_partition_size('2000000'),33554432)
    def test_wrong_identity_blocks_writes(self):
        for field,value in [('product','other'),('is-userspace','yes'),('unlocked','no'),('current-slot','b'),('partition-size:boot_a','1000000')]:
            fake=FakeFastboot({field:value})
            with self.assertRaises(RuntimeError):self.flash(fake)
            self.assertTrue(all(c[0]=='getvar' for c in fake.calls))
    def test_cancel_blocks_flash(self):
        def cancel(_):raise RuntimeError('cancel')
        fake=FakeFastboot()
        with self.assertRaises(RuntimeError):self.flash(fake,confirm=cancel)
        self.assertTrue(all(c[0]=='getvar' for c in fake.calls))
    def test_failed_flash_has_no_retry_reboot_or_slot_change(self):
        fake=FakeFastboot({'current-slot':'b'},fail_flash=True)
        with self.assertRaises(RuntimeError):self.flash(fake,'restore')
        self.assertEqual(sum(c[0]=='flash' for c in fake.calls),1)
        self.assertNotIn(['reboot'],fake.calls);self.assertNotIn(['set_active','a'],fake.calls)
    def test_restore_a_after_successful_write(self):
        fake=FakeFastboot({'current-slot':'b'});self.flash(fake,'restore')
        self.assertEqual([c[0] for c in fake.calls[-3:]],['flash','set_active','reboot'])
    def test_already_unlocked_does_not_wipe(self):
        fake=FakeFastboot();toolkit.FastbootSession(runner=fake).unlock(lambda _:self.fail('Unexpected confirmation'))
        self.assertTrue(all(c[0]=='getvar' for c in fake.calls))
    def test_restore_does_not_require_patched_image_or_pc_key(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            stock=Path(folder)/'boot.img';stock.write_bytes(b'ANDROID!'+bytes(toolkit.SIZE-8))
            sha=hashlib.sha256(stock.read_bytes()).hexdigest()
            with patch.object(toolkit,'require_backup'),patch.object(toolkit,'STOCK',stock),patch.object(toolkit,'STOCK_SHA',sha),patch.object(toolkit,'public_key_hash',side_effect=AssertionError('Must not read PC key')):
                self.assertEqual(toolkit.check_image('restore'),stock)
    def test_other_partition_commands_rejected(self):
        fake=FakeFastboot();s=toolkit.FastbootSession(runner=fake)
        for args in (['erase','userdata'],['flashing','lock'],['flash','boot_b','test.img'],['flash','vbmeta_a','test.img']):
            with self.assertRaises(RuntimeError):s.run(args)
        self.assertEqual(fake.calls,[])

class ADBTests(unittest.TestCase):
    def test_existing_adb_does_not_require_magisk_helper(self):
        def runner(command,**kwargs):
            args=command[3:]
            if args==['get-state']:return subprocess.CompletedProcess(command,0,'device\n','')
            if args==['shell','getprop','ro.serialno']:return subprocess.CompletedProcess(command,0,'TEST_DEVICE\n','')
            if args==['shell','getprop','sys.boot_completed']:return subprocess.CompletedProcess(command,0,'1\n','')
            if args[1] in ('cat','/debug_ramdisk/magisk'):return subprocess.CompletedProcess(command,1,'','not found')
            return subprocess.CompletedProcess(command,0,'ok\n','')
        original=toolkit.adb_run
        def call(args,**kwargs):return original(args,runner=runner,**kwargs)
        with patch.object(toolkit,'SERIAL','TEST_DEVICE'),patch.object(toolkit.subprocess,'run',side_effect=runner),patch.object(toolkit,'adb_run',side_effect=call):
            toolkit.verify_adb(wait=0)

class PackagingTests(unittest.TestCase):
    def make_tools(self,folder):
        tools=Path(folder)/'tools';tools.mkdir()
        (tools/'public.txt').write_bytes(b'public tool fixture')
        record={'size':19,'sha256':hashlib.sha256(b'public tool fixture').hexdigest()}
        (tools/'tools-manifest.json').write_text(json.dumps({'files':{'public.txt':record}}))
        (tools/'session-private.txt').write_bytes(b'extra device session file')
        return tools
    def test_only_manifest_files_are_packaged(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            tools=self.make_tools(folder);target=Path(folder)/'bundle.zip'
            result=package_tools.package(tools,target)
            self.assertEqual(result['sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()),{'public.txt','tools-manifest.json'})
    def test_tampered_tool_rejected_before_archive_creation(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            tools=self.make_tools(folder);(tools/'public.txt').write_bytes(b'changed')
            target=Path(folder)/'bundle.zip'
            with self.assertRaises(RuntimeError):package_tools.package(tools,target)
            self.assertFalse(target.exists())
    def test_manifest_cannot_escape_tools_directory(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            tools=self.make_tools(folder)
            (tools/'tools-manifest.json').write_text(json.dumps({'files':{'../outside.txt':{'size':0,'sha256':'0'*64}}}))
            with self.assertRaises(RuntimeError):package_tools.package(tools,Path(folder)/'bundle.zip')

if __name__=='__main__':unittest.main(verbosity=2)
