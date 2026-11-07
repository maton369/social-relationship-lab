"""Rebuild the one official .toe with embedded source and offline platform wheels."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='Social_Relationship_Lab_v3.toe'
COMP='social_relationship_lab_v3'
SOURCES=['model','runtime','view','community','export_analysis','social_dynamics','distribution_bootstrap']


def payload(wheels):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCES:
            archive.writestr('source/'+name+'.py',(ROOT/(name+'.py')).read_bytes())
        archive.writestr('source/THIRD_PARTY.md',(ROOT/'THIRD_PARTY.md').read_bytes())
        for name in ['igraph','leidenalg','texttable.py','igraph-0.11.9.dist-info','leidenalg-0.10.2.dist-info','texttable-1.7.0.dist-info']:
            source=ROOT/'vendor'/name
            paths=[source] if source.is_file() else sorted(source.rglob('*'))
            for path in paths:
                if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                    archive.writestr('platforms/macos-arm64/'+str(path.relative_to(ROOT/'vendor')).replace('\\','/'),path.read_bytes())
        for pattern in ['igraph-0.11.9-*-win_amd64.whl','leidenalg-0.10.2-*-win_amd64.whl','texttable-1.7.0-*.whl']:
            matches=list(wheels.glob(pattern))
            if len(matches)!=1:raise RuntimeError('One wheel required for '+pattern)
            with zipfile.ZipFile(matches[0]) as wheel:
                for entry in wheel.infolist():
                    if not entry.is_dir():archive.writestr('platforms/windows-amd64/'+entry.filename,wheel.read(entry))
    return stream.getvalue()


def replace_text(path,body,header):
    path.write_bytes(header[:-4]+struct.pack('>I',len(body))+body)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template',type=Path,default=ROOT/NAME)
    parser.add_argument('--windows-wheels',type=Path,required=True)
    parser.add_argument('--bin-dir',type=Path,default=Path('/Applications/TouchDesigner.app/Contents/MacOS'))
    args=parser.parse_args()
    data=payload(args.windows_wheels)
    work=Path(tempfile.mkdtemp(prefix='social-v3-release-'))
    stage=work/NAME;shutil.copy2(args.template,stage)
    subprocess.run([str(args.bin_dir/'toeexpand'),str(stage)],capture_output=True)
    folder=Path(str(stage)+'.dir');tocfile=Path(str(stage)+'.toc')
    if not tocfile.exists():raise RuntimeError('toeexpand failed')
    toc=tocfile.read_text().splitlines()
    old=next(p.split('/')[0] for p in toc if p.endswith('/runtime.text'))
    if old!=COMP:
        (folder/old).rename(folder/COMP)
        for item in list(folder.glob(old+'.*')):item.rename(item.with_name(COMP+item.name[len(old):]))
        toc=[COMP+p[len(old):] if p==old or p.startswith(old+'/') or p.startswith(old+'.') else p for p in toc]
        for item in folder.rglob('*'):
            if item.is_file() and item.suffix in ('.n','.parm','.cparm'):
                item.write_bytes(item.read_bytes().replace(old.encode(),COMP.encode()))
    node=folder/COMP
    template=(node/'view.text').read_bytes();i=template.index(b'"""');header=template[:i]
    assert struct.unpack('>I',header[-4:])[0]==len(template)-i
    for name in ['model','runtime','view','community','export_analysis','distribution_bootstrap']:
        replace_text(node/(name+'.text'),(ROOT/(name+'.py')).read_bytes(),header)
    replace_text(node/'distribution_payload.text',base64.b64encode(data),header)
    for name in ['distribution_bootstrap','distribution_payload']:
        (node/(name+'.n')).write_bytes((node/'view.n').read_bytes())
        (node/(name+'.parm')).write_text('?\nlanguage 0 '+('python' if name=='distribution_bootstrap' else 'text')+'\n?\n')
        for suffix in ['n','parm','text']:
            entry=COMP+'/'+name+'.'+suffix
            if entry not in toc:toc.append(entry)
    toc=[p for p in toc if not p.startswith('mcp_webserver_base')]
    tocfile.write_text('\n'.join(toc)+'\n')
    subprocess.run([str(args.bin_dir/'toecollapse'),str(stage)],capture_output=True,check=True)
    # Expand a fresh copy to verify the archive actually contains the payload.
    verify=work/('verify-'+NAME);shutil.copy2(stage,verify)
    subprocess.run([str(args.bin_dir/'toeexpand'),str(verify)],capture_output=True)
    vfolder=Path(str(verify)+'.dir')/COMP
    for name in ['model','runtime','view','distribution_bootstrap']:
        body=(vfolder/(name+'.text')).read_bytes()[len(header):]
        assert body==(ROOT/(name+'.py')).read_bytes(),name
    assert base64.b64decode((vfolder/'distribution_payload.text').read_bytes()[len(header):])==data
    shutil.copy2(stage,ROOT/NAME)
    manifest={'file':NAME,'component':'/'+COMP,'toe_sha256':hashlib.sha256(stage.read_bytes()).hexdigest(),
        'payload_sha256':hashlib.sha256(data).hexdigest(),'size':stage.stat().st_size,
        'platforms':['macos-arm64','windows-amd64'],'python':'3.11',
        'round_trip_verified':True,'sources':{n:hashlib.sha256((ROOT/(n+'.py')).read_bytes()).hexdigest() for n in SOURCES}}
    (ROOT/'docs/release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2));print('Expanded verification files:',work)


if __name__=='__main__':main()
