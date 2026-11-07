"""Extract the official project's embedded code and native dependencies on first use."""
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import sys
import tempfile
import zipfile


def platform_key():
    if sys.version_info[:2]!=(3,11):
        raise RuntimeError('TouchDesigner with Python 3.11 is required for this release.')
    machine=platform.machine().lower()
    if sys.platform=='darwin' and machine in ('arm64','aarch64'):return 'macos-arm64'
    if sys.platform=='win32' and machine in ('amd64','x86_64'):return 'windows-amd64'
    raise RuntimeError('Supported platforms: macOS Apple Silicon and Windows x64.')


def extract(encoded, folder, key):
    raw=base64.b64decode(encoded,validate=True)
    digest=hashlib.sha256(raw).hexdigest()
    parent=Path(folder)/'.social_lab'/digest[:16]
    target=parent/key
    marker=target/'installed.json'
    if marker.is_file():
        try:
            if json.loads(marker.read_text(encoding='utf-8'))['sha256']==digest:
                return target,target/'vendor'
        except (ValueError,KeyError):pass
    parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='extract-',dir=parent))
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():continue
                path=PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or any(':' in p for p in path.parts) or '\\' in entry.filename or stat.S_ISLNK(entry.external_attr>>16):
                    raise ValueError('Unsafe embedded archive entry: '+entry.filename)
                if entry.filename.startswith('source/'):
                    relative=path.relative_to('source')
                elif entry.filename.startswith('platforms/'+key+'/'):
                    relative=PurePosixPath('vendor')/path.relative_to('platforms/'+key)
                else:continue
                output=staging.joinpath(*relative.parts)
                output.parent.mkdir(parents=True,exist_ok=True)
                output.write_bytes(archive.read(entry))
        for required in ('model.py','social_dynamics.py','vendor/igraph/__init__.py','vendor/leidenalg/__init__.py','vendor/texttable.py'):
            if not (staging/required).is_file():raise RuntimeError('Incomplete embedded release: '+required)
        (staging/'installed.json').write_text(json.dumps({'sha256':digest,'platform':key}),encoding='utf-8')
        if target.exists():shutil.rmtree(target)
        staging.rename(target)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return target,target/'vendor'


def resolve(owner):
    folder=Path(project.folder)
    try:
        base,packages=extract(owner.op('distribution_payload').text,folder,platform_key())
    except OSError as exc:
        raise RuntimeError('Move the .toe to a writable folder, then reopen it: '+str(exc)) from exc
    owner.store('standalone_distribution',True)
    return base,packages
