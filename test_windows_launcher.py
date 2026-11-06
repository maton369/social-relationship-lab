"""Host-independent launcher checks. These do not execute Windows or TouchDesigner."""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import windows_launcher as launcher


class WindowsLauncherChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lab space ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '共有 project'
        self.root.mkdir()
        self.target = self.root / '.deps/windows-cp311'
        self.toe = self.root / 'Social_Relationship_Lab_Analysis.toe'
        self.toe.write_bytes(b'fixture')
        self.exe = self.root / 'Program Files/TouchDesigner.exe'
        self.exe.parent.mkdir()
        self.exe.write_bytes(b'fixture')
        self.req = self.root / 'requirements-windows.txt'
        self.req.write_text('igraph==0.11.9\n')
        stack = self.enterContext(ExitStack())
        for name, value in [('ROOT', self.root), ('TARGET', self.target),
                            ('TOE', self.toe), ('REQUIREMENTS', self.req)]:
            stack.enter_context(patch.object(launcher, name, value))

    def test_failed_install_preserves_previous_dependencies(self):
        self.target.mkdir(parents=True)
        old = self.target / 'previous.txt'
        old.write_text('keep')
        with patch.object(launcher, 'pip_python', return_value='python.exe'), \
             patch.object(launcher.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'pip')):
            with self.assertRaises(subprocess.CalledProcessError):
                launcher.setup()
        self.assertEqual(old.read_text(), 'keep')
        self.assertEqual(list(self.target.parent.glob('windows-stage-*')), [])

    def test_current_install_is_checked_without_download(self):
        self.target.mkdir(parents=True)
        (self.target / 'installed.json').write_text(json.dumps({'fingerprint': launcher.fingerprint()}))
        with patch.object(launcher, 'check_packages') as check, \
             patch.object(launcher, 'pip_python') as pip:
            launcher.setup()
            check.assert_called_once_with(self.target)
            pip.assert_not_called()

    def test_success_records_marker_after_import_check(self):
        with patch.object(launcher, 'pip_python', return_value='python.exe'), \
             patch.object(launcher, 'check_packages') as check, \
             patch.object(launcher.subprocess, 'run'):
            launcher.setup()
        self.assertEqual(check.call_count, 1)
        self.assertEqual(json.loads((self.target / 'installed.json').read_text())['fingerprint'], launcher.fingerprint())

    def test_offline_launch_preserves_space_and_unicode_paths(self):
        with patch.object(launcher.sys, 'platform', 'win32'), \
             patch.object(launcher.sys, 'version_info', (3, 11)), \
             patch.object(launcher.platform, 'machine', return_value='AMD64'), \
             patch.object(launcher, 'check_packages') as check, \
             patch.object(launcher, 'setup') as setup, \
             patch.object(launcher.subprocess, 'Popen') as start:
            self.assertEqual(launcher.main(['--td', str(self.exe), '--launch-only']), 0)
        setup.assert_not_called()
        check.assert_called_once_with(self.target)
        args, kwargs = start.call_args
        self.assertEqual(args[0], [str(self.exe.resolve()), str(self.toe)])
        self.assertEqual(kwargs['cwd'], str(self.root))
        self.assertEqual(kwargs['env']['SOCIAL_LAB_PACKAGES'], str(self.target))
        self.assertEqual(kwargs['env']['SOCIAL_LAB_HOME'], str(self.root))


if __name__ == '__main__':
    unittest.main()
