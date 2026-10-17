#!/usr/bin/env python3
"""Quick native reproduction and six lit files per patch stage; baseline and v3 only, using prebuilt LLVMs."""
import argparse, hashlib, json, os, pathlib, shutil, struct, subprocess, sys, tempfile

HERE=pathlib.Path(__file__).resolve().parent
BASE_COMMIT='304cb72bcb9350342a021bcd50b9a097d033ac94'
parser=argparse.ArgumentParser(description=__doc__)
for name in ['base','v3','source','linker']:parser.add_argument('--'+name,required=True,type=pathlib.Path)
parser.add_argument('--work-dir',type=pathlib.Path)
parser.add_argument('--repro-only',action='store_true')
args=parser.parse_args()
args.base=args.base.resolve();args.source=args.source.resolve();args.linker=args.linker.resolve()
work=args.work_dir.resolve() if args.work_dir else pathlib.Path(tempfile.mkdtemp(prefix='llvm-pointer-review-'))
work.mkdir(parents=True,exist_ok=True)
BIN=args.base/'bin'
builds={'baseline':args.base,'v3':args.v3.resolve()}
commands=[]

def env(label):
    return {**os.environ,'LD_LIBRARY_PATH':str(builds[label]/'lib')+(':'+os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else ''),
            'PATH':str(BIN)+':'+os.environ.get('PATH','')}

def run(argv,label='baseline',cwd=None,allow_failure=False):
    argv=list(map(str,argv))
    result=subprocess.run(argv,cwd=cwd,env=env(label),capture_output=True)
    record={'argv':argv,'label':label,'exit':result.returncode,
            'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}
    commands.append(record)
    (work/'commands.json').write_text(json.dumps(commands,indent=2))
    if result.returncode and not allow_failure:raise RuntimeError(json.dumps(record))
    return result

def binding(label):
    tool=BIN/'opt';lib=builds[label]/'lib/libLLVM.so.24.0git'
    result=run(['ldd',tool],label)
    if str(lib) not in result.stdout.decode():
        raise RuntimeError('Runtime LLVM binding differs from requested build: '+label)
    return {'library_sha256':hashlib.sha256(lib.read_bytes()).hexdigest(),'opt_sha256':hashlib.sha256(tool.read_bytes()).hexdigest()}

def native():
    d=work/'native';d.mkdir(exist_ok=True)
    run([BIN/'llc','-filetype=obj','-relocation-model=pic',HERE/'driver.ll','-o',d/'driver.o'])
    run([BIN/'llvm-mc','-triple=x86_64-unknown-linux-gnu','-filetype=obj',HERE/'start.S','-o',d/'start.o'])
    result={}
    for label in builds:
        ir=d/(label+'.ll');obj=d/(label+'.o');exe=d/(label+'.exe')
        run([BIN/'opt','-O2','-S',HERE/'repro.ll','-o',ir],label)
        run([BIN/'llc','-filetype=obj','-relocation-model=pic',ir,'-o',obj],label)
        run([args.linker,'-static','-e','_start',d/'start.o',d/'driver.o',obj,'-o',exe],label)
        out=run([exe],label).stdout
        if len(out)!=32:raise RuntimeError('Unexpected native record length: '+label)
        equal,x,y,memory=struct.unpack('<QQQQ',out)
        result[label]={'equal_address':equal,'first_call':x,'second_call':y,'memory_read':memory}
        if equal!=1:raise RuntimeError('Merged-address branch was not exercised: '+label)
        if label=='baseline' and x==y==memory:raise RuntimeError('Baseline did not reproduce the discrepancy')
        if label!='baseline' and not x==y==memory:raise RuntimeError('Candidate still differs from the actual read: '+label)
    return result

def lit(stage,label,repo,paths):
    d=work/(label+'-'+stage+'-lit');d.mkdir(exist_ok=True)
    for path in paths:
        source=repo/path
        if path.startswith('llvm/test/'):
            shutil.copy2(source,d/(source.parent.name+'-'+source.name))
    (d/'lit.cfg.py').write_text('''import os,lit.formats
config.name='LLVM-review'
config.test_format=lit.formats.ShTest(False)
config.suffixes=['.ll']
config.test_source_root=os.path.dirname(__file__)
config.test_exec_root=config.test_source_root+'/Output'
config.environment['PATH']=os.environ['PATH']
config.environment['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']
config.available_features.add('x86-registered-target')
''')
    run([sys.executable,BIN/'llvm-lit','-v','-j','1','--output',d/'results.json',d],label)
    data=json.loads((d/'results.json').read_text())
    if len(data['tests'])!=6 or any(x['code']!='PASS' for x in data['tests']):raise RuntimeError('Review lit test failed: '+label+'/'+stage)
    return {'tests':6,'passed':6,'run_lines':sum(sum(l.startswith('; RUN:') for l in (repo/p).read_text().splitlines()) for p in paths if p.startswith('llvm/test/'))}

def series():
    metadata=json.loads((HERE/'series.json').read_text());result={}
    for entry in metadata:
        label=entry['variant'];repo=work/(label+'-source');repo.mkdir(exist_ok=True)
        patch1=HERE/'0001-tests.patch';patch2=HERE/'0002-change.patch'
        paths=[]
        first_paths=[]
        for patch in [patch1,patch2]:
            for line in patch.read_text().splitlines():
                if line.startswith('diff --git a/'):
                    path=line.split(' b/',1)[1]
                    if path not in paths:paths.append(path)
                    if patch==patch1:first_paths.append(path)
        for path in paths:
            p=pathlib.PurePosixPath(path)
            if p.is_absolute() or '..' in p.parts:raise RuntimeError('Unexpected patch path')
            original=run(['git','-C',args.source,'show',BASE_COMMIT+':'+path],allow_failure=True)
            if original.returncode==0:
                dest=repo/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(original.stdout)
            elif not path.endswith('/constant-pointer-provenance.ll'):
                raise RuntimeError('Missing original source file: '+path)
        if sorted(first_paths)!=sorted(entry['new_tests']):raise RuntimeError('First patch must add exactly the two new tests')
        run(['git','init','-q',repo])
        run(['git','-C',repo,'apply','--check',patch1])
        run(['git','-C',repo,'apply',patch1])
        before=lit(label+'-tests-first','baseline',repo,paths)
        run(['git','-C',repo,'apply','--check',patch2])
        run(['git','-C',repo,'apply',patch2])
        for path,expected in entry['production_source_sha256'].items():
            actual=hashlib.sha256((repo/path).read_bytes()).hexdigest()
            if actual!=expected:raise RuntimeError('Patched production source differs from recorded build: '+path)
        for path in paths:
            if path.endswith('/constant-pointer-provenance.ll'):
                import re
                source='\n'.join(l for l in (repo/path).read_text().splitlines() if not l.lstrip().startswith(';'))
                if re.search(r'\bpoison\b',source):raise RuntimeError('Literal poison input in new test')
        after=lit(label+'-change',label,repo,paths)
        result[label]={'tests_first':before,'change':after,'production_source_hashes_match':True}
    return result

try:
    bound={label:binding(label) for label in builds}
    metadata=json.loads((HERE/'series.json').read_text())[0]
    if bound['v3']['library_sha256']!=metadata['compiled_library_sha256']:raise RuntimeError('v3 library does not match the compiled production source in the series')
    result={'runtime_bindings':bound,'native':native()}
    if not args.repro_only:result['two_patch_stages']=series()
    result.update(status='OBSERVATIONS_MATCHED',work_dir=str(work),limits='x86_64 Linux, prebuilt matching shared LLVM ABI; narrow checks, not a full regression or proof')
    (work/'RESULT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
except Exception as exc:
    (work/'ERROR.txt').write_text(str(exc));print(str(exc),file=sys.stderr);print('Artifacts: '+str(work),file=sys.stderr);sys.exit(1)
