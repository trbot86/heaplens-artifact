import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'headline-pmu/reproduction/drivers'))
from trace_store import TraceStore


class TraceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.store = TraceStore(raw_root=self.root/'nfs-raw', archive_root=self.root/'scratch',
                                manifest_root=self.root/'nfs-metadata', campaign='test-campaign',
                                host='synthetic-local', raw_floor=0, archive_floor=0)
        self.identity = dict(trial_id='app-before-r01', measurement_status='completed',
                             application='synthetic', variant='before', repetition=1,
                             source_revision='test-only', binary_sha256='a'*64, command_sha256='b'*64)
        self.raw = self.store.raw_root/self.identity['trial_id']/'events.bin'
        self.raw.parent.mkdir()
        self.data = struct.pack('<QQQQHHB3x',1,100,48,4096,1,2,1)+struct.pack('<QQQQHHB3x',0,200,0,4096,0,0,0)
        self.raw.write_bytes(self.data)

    def tearDown(self):
        self.tmp.cleanup()

    def run_archive(self):
        return self.store.archive(self.identity['trial_id'],self.identity)

    def test_verified_archive_and_durable_location(self):
        record = self.run_archive()
        self.assertFalse(self.raw.exists())
        self.assertEqual(gzip.decompress(Path(record['archive_path']).read_bytes()),self.data)
        self.assertEqual(record['raw_sha256'],hashlib.sha256(self.data).hexdigest())
        self.assertEqual((record['allocations'],record['frees']),(1,1))
        self.assertEqual(record['retention'],'pending_author_review_no_automatic_deletion')
        inventory=json.loads((self.store.manifest_root/'inventory.json').read_text())
        self.assertEqual(inventory['archived_trials'],1)
        self.assertEqual(inventory['remaining_trials'],199)
        self.assertEqual(inventory['entries'][0]['archive_path'],record['archive_path'])

    def test_allocation_only_is_valid(self):
        self.raw.write_bytes(self.data[:40])
        self.assertEqual(self.run_archive()['frees'],0)

    def test_partial_record_preserved(self):
        self.raw.write_bytes(b'bad')
        with self.assertRaises(ValueError):self.run_archive()
        self.assertEqual(self.raw.read_bytes(),b'bad')

    def test_bad_event_preserved(self):
        data=bytearray(self.data);data[36]=2;self.raw.write_bytes(data)
        with self.assertRaises(ValueError):self.run_archive()
        self.assertTrue(self.raw.exists())

    def test_running_measurement_rejected(self):
        self.identity['measurement_status']='running'
        with self.assertRaises(ValueError):self.run_archive()
        self.assertTrue(self.raw.exists())

    def test_unsafe_identifier_rejected(self):
        with self.assertRaises(ValueError):self.store.archive('../other',self.identity)
        self.assertTrue(self.raw.exists())

    def test_low_space_preserves_raw(self):
        with patch('trace_store.shutil.disk_usage') as usage:
            usage.return_value.free=0
            with self.assertRaises(RuntimeError):self.run_archive()
        self.assertTrue(self.raw.exists())

    def test_next_trial_reserve(self):
        with patch('trace_store.shutil.disk_usage') as usage:
            usage.return_value.free=5
            with self.assertRaises(RuntimeError):self.store.before_trial(raw_cap=6)

    def test_no_overwrite_or_retry(self):
        self.run_archive();self.raw.write_bytes(self.data)
        with self.assertRaises(FileExistsError):self.run_archive()
        self.assertEqual(self.raw.read_bytes(),self.data)

    def test_metadata_failure_preserves_raw(self):
        import trace_store
        original=trace_store.write_json
        def fail_on_verified(path,value):
            if value.get('status')=='verified_raw_retained':raise OSError('synthetic metadata failure')
            original(path,value)
        with patch('trace_store.write_json',side_effect=fail_on_verified):
            with self.assertRaises(OSError):self.run_archive()
        self.assertEqual(self.raw.read_bytes(),self.data)

    def test_corrupt_archive_preserves_raw(self):
        with patch('trace_store.gzip.open',side_effect=OSError('synthetic corruption')):
            with self.assertRaises(OSError):self.run_archive()
        self.assertEqual(self.raw.read_bytes(),self.data)

    def test_changed_source_preserves_raw(self):
        original=gzip.open
        def change_source(*args,**kwargs):
            self.raw.write_bytes(self.data+self.data)
            return original(*args,**kwargs)
        with patch('trace_store.gzip.open',side_effect=change_source):
            with self.assertRaises(RuntimeError):self.run_archive()
        self.assertTrue(self.raw.exists())

    def test_symlink_raw_refused(self):
        other=self.root/'other.bin';self.raw.rename(other)
        self.raw.symlink_to(other)
        with self.assertRaises(ValueError):self.run_archive()
        self.assertTrue(other.exists())

    def test_missing_archive_visible_in_inventory(self):
        row=self.run_archive();Path(row['archive_path']).unlink()
        inv=self.store.inventory()
        self.assertFalse(inv['entries'][0]['archive_present'])
        self.assertEqual(inv['archived_trials'],0)

    def test_existing_settings_cannot_change(self):
        with self.assertRaises(ValueError):
            TraceStore(raw_root=self.store.raw_root,archive_root=self.store.archive_root,
                       manifest_root=self.store.manifest_root,campaign='other',host='synthetic-local',
                       raw_floor=0,archive_floor=0)


if __name__=='__main__':unittest.main()
