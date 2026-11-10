import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from integrity import compare, fingerprint, load_baseline, snapshot

SCRIPT = Path(__file__).resolve().parents[1]/'integrity.py'


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'files'
        self.root.mkdir()
        self.file = self.root/'example.txt'
        self.file.write_bytes(b'abc')
        self.manifest = self.base/'baseline.json'

    def cli(self, command, manifest=None):
        return subprocess.run([sys.executable,str(SCRIPT),command,str(self.root),
                               str(manifest or self.manifest)],capture_output=True,text=True)

    def test_known_sha256_vector(self):
        self.assertEqual(fingerprint(self.file), {'sha256':
            'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad', 'size':3})

    def test_unchanged(self):
        before = snapshot(self.root)
        self.assertEqual(compare(before,snapshot(self.root)),
                         {'added':[],'modified':[],'removed':[],'unchanged_count':1})

    def test_added_modified_removed_together(self):
        removed = self.root/'old.txt'
        removed.write_text('old')
        before=snapshot(self.root)
        self.file.write_bytes(b'xyz')  # Same length: size alone would miss this.
        removed.unlink()
        (self.root/'new.txt').write_text('new')
        self.assertEqual(compare(before,snapshot(self.root)),
                         {'added':['new.txt'],'modified':['example.txt'],
                          'removed':['old.txt'],'unchanged_count':0})

    def test_rename_is_added_and_removed(self):
        before=snapshot(self.root)
        self.file.rename(self.root/'renamed.txt')
        result=compare(before,snapshot(self.root))
        self.assertEqual(result['added'],['renamed.txt'])
        self.assertEqual(result['removed'],['example.txt'])
        self.assertEqual(result['modified'],[])

    def test_nested_empty_and_hidden_files(self):
        folder=self.root/'nested'
        folder.mkdir()
        (folder/'empty.txt').write_bytes(b'')
        (self.root/'.hidden').write_text('hidden')
        records=snapshot(self.root)['files']
        self.assertIn('.hidden',records)
        self.assertEqual(records['nested/empty.txt']['sha256'],hashlib.sha256(b'').hexdigest())

    def test_empty_directory(self):
        self.file.unlink()
        self.assertEqual(snapshot(self.root)['files'],{})

    def test_timestamp_only_change_is_not_content_change(self):
        before=snapshot(self.root)
        os.utime(self.file,(1000000000,1000000000))
        self.assertEqual(compare(before,snapshot(self.root))['modified'],[])

    def test_invalid_baseline_and_traversal_rejected(self):
        bad=[{}, {'version':True,'algorithm':'sha256','files':{}},
             {'version':1,'algorithm':'md5','files':{}},
             {'version':1,'algorithm':'sha256','files':{'../escape':{'sha256':'a'*64,'size':0}}},
             {'version':1,'algorithm':'sha256','files':{'file':{'sha256':'bad','size':0}}}]
        for value in bad:
            with self.subTest(value=value):
                self.manifest.write_text(json.dumps(value))
                with self.assertRaises(ValueError): load_baseline(self.manifest)

    def test_duplicate_json_keys_rejected(self):
        self.manifest.write_text('{"version":1,"version":1,"algorithm":"sha256","files":{}}')
        with self.assertRaisesRegex(ValueError,'Duplicate'): load_baseline(self.manifest)

    def test_unreadable_file_aborts_instead_of_clean_result(self):
        with patch('integrity.fingerprint',side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError): snapshot(self.root)

    def test_link_rejected_when_supported(self):
        link=self.root/'link'
        try:
            link.symlink_to(self.file)
        except OSError:
            self.skipTest('OS does not permit symlink creation for this account')
        with self.assertRaisesRegex(ValueError,'Links/reparse'): snapshot(self.root)

    def test_cli_exit_codes_and_no_overwrite(self):
        self.assertEqual(self.cli('baseline').returncode,0)
        original=self.manifest.read_bytes()
        self.assertEqual(self.cli('check').returncode,0)
        self.file.write_text('changed')
        result=self.cli('check')
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stdout)['modified'],['example.txt'])
        self.assertEqual(self.cli('baseline').returncode,2)
        self.assertEqual(self.manifest.read_bytes(),original)

    def test_manifest_inside_root_rejected(self):
        result=self.cli('baseline',self.root/'baseline.json')
        self.assertEqual(result.returncode,2)
        self.assertFalse((self.root/'baseline.json').exists())

    def test_missing_manifest_is_error_not_no_changes(self):
        result=self.cli('check')
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,'')

    def test_missing_root_is_error(self):
        with self.assertRaises(OSError): snapshot(self.root/'missing')


if __name__=='__main__':
    unittest.main()
