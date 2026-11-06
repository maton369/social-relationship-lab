"""Install Windows wheels beside the project and launch TouchDesigner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '.deps' / 'windows-cp311'
TOE = ROOT / 'Social_Relationship_Lab_Analysis.toe'
REQUIREMENTS = ROOT / 'requirements-windows.txt'


def fingerprint():
    return hashlib.sha256(REQUIREMENTS.read_bytes() + sys.version.encode()).hexdigest()


def check_packages(folder):
    # -I excludes PYTHONPATH and the current directory; only the selected wheels
    # and TouchDesigner's bundled standard/site packages participate in this check.
    code = '''import sys
sys.path.insert(0, sys.argv[1])
import numpy, igraph, leidenalg
g = igraph.Graph(n=6, edges=[(0,1),(1,2),(0,2),(3,4),(4,5),(3,5),(2,3)])
p = leidenalg.find_partition(g, leidenalg.CPMVertexPartition,
    resolution_parameter=0.25, seed=23)
assert len(p.membership) == 6
print('Dependencies OK:', numpy.__version__, igraph.__version__, leidenalg.__file__)
'''
    subprocess.run([sys.executable, '-I', '-c', code, str(folder)], check=True)


def pip_python():
    if subprocess.run([sys.executable, '-I', '-m', 'pip', '--version'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return sys.executable
    # Seed pip in a local environment rather than writing into Program Files.
    env = ROOT / '.deps' / 'setup-python'
    subprocess.run([sys.executable, '-I', '-m', 'venv', str(env)], check=True)
    return str(env / 'Scripts' / 'python.exe')


def setup():
    marker = TARGET / 'installed.json'
    if marker.is_file():
        try:
            if json.loads(marker.read_text())['fingerprint'] == fingerprint():
                check_packages(TARGET)
                return
        except (ValueError, KeyError, subprocess.CalledProcessError):
            pass
    TARGET.parent.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='windows-stage-', dir=TARGET.parent))
    try:
        subprocess.run([pip_python(), '-I', '-m', 'pip', 'install',
                        '--only-binary=:all:', '--no-compile', '--disable-pip-version-check',
                        '--target', str(staging), '-r', str(REQUIREMENTS)], check=True)
        check_packages(staging)
        (staging / 'installed.json').write_text(json.dumps({
            'fingerprint': fingerprint(), 'python': sys.version,
            'requirements': REQUIREMENTS.read_text(),
        }, indent=2), encoding='utf-8')
        # Failed downloads/import checks leave an existing installation intact.
        if TARGET.exists():
            shutil.rmtree(TARGET)
        staging.rename(TARGET)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--td', required=True, help='Path to TouchDesigner.exe')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--setup-only', action='store_true')
    modes.add_argument('--launch-only', action='store_true', help='Offline launch after setup')
    args = parser.parse_args(argv)
    if sys.platform != 'win32' or struct.calcsize('P') != 8 or platform.machine().lower() not in ('amd64', 'x86_64'):
        parser.error('Windows x64 is required.')
    if sys.version_info[:2] != (3, 11):
        parser.error('Use TouchDesigner with Python 3.11 (tested project build: 2025.33230).')
    executable = Path(args.td).resolve()
    if not executable.is_file() or not TOE.is_file():
        parser.error('TouchDesigner executable or project .toe is missing. Extract the entire repository ZIP first.')
    if args.launch_only:
        check_packages(TARGET)
    else:
        setup()
    if args.setup_only:
        print('Setup complete. Run start_windows.cmd to launch.')
        return 0
    env = os.environ.copy()
    env['SOCIAL_LAB_HOME'] = str(ROOT)
    env['SOCIAL_LAB_PACKAGES'] = str(TARGET)
    subprocess.Popen([str(executable), str(TOE)], cwd=str(ROOT), env=env)
    print('TouchDesigner launched. Complete its license/login dialog if prompted. F1 opens Perform mode.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        print('Setup/launch failed. Check network access and the TouchDesigner installation.', file=sys.stderr)
        raise SystemExit(1)
