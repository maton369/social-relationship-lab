import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import distribution_bootstrap as bootstrap


def archive(extra=None):
    buffer=io.BytesIO()
    entries={'source/model.py':'# fixture','source/social_dynamics.py':'# fixture'}
    for key in ('macos-arm64','windows-amd64'):
        for name in ('igraph/__init__.py','leidenalg/__init__.py','texttable.py'):
            entries['platforms/'+key+'/'+name]=key
    entries.update(extra or {})
    with zipfile.ZipFile(buffer,'w') as z:
        for name,value in entries.items():z.writestr(name,value)
    return base64.b64encode(buffer.getvalue()).decode()


class DistributionChecks(unittest.TestCase):
    def test_extracts_only_selected_platform_and_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            base,vendor=bootstrap.extract(archive(),folder,'windows-amd64')
            self.assertTrue((base/'model.py').is_file())
            self.assertEqual((vendor/'igraph/__init__.py').read_text(),'windows-amd64')
            self.assertEqual(json.loads((base/'installed.json').read_text())['platform'],'windows-amd64')

    def test_second_launch_reuses_cache_without_replacing_user_output(self):
        with tempfile.TemporaryDirectory() as folder:
            encoded=archive();base,vendor=bootstrap.extract(encoded,folder,'macos-arm64')
            (base/'sentinel').write_text('keep')
            self.assertEqual(bootstrap.extract(encoded,folder,'macos-arm64'),(base,vendor))
            self.assertEqual((base/'sentinel').read_text(),'keep')

    def test_traversal_is_rejected_and_partial_extraction_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):bootstrap.extract(archive({'source/../../escape.py':'bad'}),folder,'windows-amd64')
            self.assertFalse(list(Path(folder).rglob('escape.py')))
            self.assertFalse(list(Path(folder).rglob('installed.json')))
            self.assertFalse(list(Path(folder).rglob('extract-*')))

    def test_incomplete_payload_fails_without_overwriting_good_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            base,_=bootstrap.extract(archive(),folder,'macos-arm64')
            with self.assertRaises(RuntimeError):bootstrap.extract(archive(),folder,'unsupported')
            self.assertTrue((base/'installed.json').is_file())

    def test_platform_and_python_version_are_checked(self):
        with patch.object(bootstrap.sys,'platform','win32'),patch.object(bootstrap.sys,'version_info',(3,11)),patch.object(bootstrap.platform,'machine',return_value='AMD64'):
            self.assertEqual(bootstrap.platform_key(),'windows-amd64')
        with patch.object(bootstrap.sys,'version_info',(3,12)):
            with self.assertRaises(RuntimeError):bootstrap.platform_key()


if __name__=='__main__':unittest.main()
