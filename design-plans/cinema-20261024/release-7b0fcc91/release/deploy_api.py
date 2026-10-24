"""Use the installed official client's archive and deployment APIs with bounded upload timeouts."""
if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib,json,subprocess,os,re,shutil,zipfile
import sys
sys.dont_write_bytecode = True
assert len(sys.argv)==3 and len(sys.argv[1])==40, 'usage: deploy_api.py <release-commit> <receipt-dir>'
BASE=Path(sys.argv[2]).resolve()
ROOT=Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-cinema-final-20261024')
NS=ROOT/'.runtime/cinema-release'
assert BASE==NS/'release' and Path(__file__).resolve().parent==BASE
binding=json.loads((NS/'source-binding.json').read_text());SHA=binding['source_commit']
assert re.fullmatch(r'[0-9a-f]{40}',SHA) and sys.argv[1]==SHA and binding['base_commit']=='0ccf1eafcd27e0827e2d0778f9c2642e34cd05f9'
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,SHA)
import fastar
import importlib.metadata
assert importlib.metadata.version("fastapi-cloud-cli") == "0.26.0"
import httpx
from fastapi_cloud_cli.api import APIClient
from fastapi_cloud_cli.commands.deploy.archive import archive
from fastapi_cloud_cli.commands.deploy.cloud import _create_deployment
from fastapi_cloud_cli.commands.deploy.upload import RequestUploadResponse
APP='ebd0862c-cd35-4da4-aae5-d32f1c40ca60'
proof=json.loads((BASE/'full-gate-verified.json').read_text())
assert proof['canonical_commit']==SHA and proof['new_skips']==0 and proof['deselected']==0 and proof['failed']==0 and proof['errors']==0 and proof['exit_code']==0
assert subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
assert not subprocess.check_output(['/usr/bin/git','status','--porcelain'],cwd=ROOT,text=True).strip()
environment=json.loads((BASE/'api-environment-updated.json').read_text())
assert environment['status']=='passed' and environment['source_commit']==SHA and len(environment['receipts'])==2 and {r['name'] for r in environment['receipts']}=={'CASEPATH_SOURCE_COMMIT','CASEPATH_READ_SEED_SHA256'} and all(r['exit_code']==0 and r['no_redeploy'] is True and r['status']=='completed' for r in environment['receipts'])
receipt=BASE/'api-deployment-created.json';assert not receipt.exists(),'Reconcile the existing deployment before continuing'
attempt=BASE/'api-deployment-attempt.json';assert not attempt.exists(),'Reconcile the original deployment attempt before any retry'
reserved=['api-private-package-verified.json','api-private-wheel.log','api-private-wheel-verified.json','api-deployment-uploaded.json']
assert all(not (BASE/name).exists() for name in reserved),'Preserve and reconcile the existing package/deployment evidence'
with attempt.open('x') as f:
    json.dump({'source_commit':SHA,'app_id':APP,'status':'preparing_private_package','retries':0},f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
with TemporaryDirectory(prefix='casepath-authorized-release-') as tmp:
    seed=Path('/Users/kumar0002/Library/Application Support/CasePath')/('private-release-'+SHA[:12])/'hosted-read-seed-v1.json'
    seed_receipt=json.loads((BASE/'seed-renewal-receipt.json').read_text())
    assert seed_receipt['deployment_commit']==SHA and environment['seed_sha256']==seed_receipt['sha256']
    assert seed_receipt['input_commit']=='4864e7347c299bf1b580a5b35667635bc1c47f15' and seed_receipt['input_sha256']=='be37e32d5498aeaf6d61d39de41d26424a009e8d90859de9b95fedd14e3d3997'
    assert seed_receipt['input_bytes']==13330327 and seed_receipt['raw_records_and_sources_unchanged'] is True and seed_receipt['native_replay_and_full_fresh_atomic_proof'] is True
    assert seed_receipt['read_only'] is True and seed_receipt['requests']==1 and seed_receipt['retries']==0
    assert Path(seed_receipt['artifact_path'])==seed and seed.stat().st_size==seed_receipt['bytes']
    seed_bytes=seed.read_bytes()
    assert hashlib.sha256(seed_bytes).hexdigest()==seed_receipt['sha256']
    assert json.loads(seed_bytes)['deployment_commit']==SHA
    official=archive(ROOT,Path(tmp)/'official.tar.zst')
    unpacked=Path(tmp)/'official';unpacked.mkdir()
    with fastar.open(official,'r:zst') as tar:tar.unpack(unpacked)
    originals={p.relative_to(unpacked).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in unpacked.rglob('*') if p.is_file()}
    seed_name='casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json'
    assert seed_name not in originals
    target=unpacked/seed_name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(seed_bytes);target.chmod(0o600)
    path=Path(tmp)/'source.tar.zst'
    with fastar.open(path,'w:zst',sparse=False) as tar:
        for p in sorted(unpacked.rglob('*')):
            if p.is_file():tar.append(p,arcname=p.relative_to(unpacked))
    check=Path(tmp)/'verified';check.mkdir()
    with fastar.open(path,'r:zst') as tar:tar.unpack(check)
    verified={p.relative_to(check).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in check.rglob('*') if p.is_file()}
    assert verified=={**originals,seed_name:seed_receipt['sha256']}
    assert not any('hosted-read-seed' in name for name in originals)
    assert not any((p/'hosted-read-seed-v1.json').exists() for p in [ROOT/'casepath',ROOT/'casepath-public'])
    (BASE/'api-private-package-verified.json').write_text(json.dumps({'canonical_commit':SHA,'official_files_unchanged':len(originals),'added_private_seed':seed_name,'seed_sha256':seed_receipt['sha256'],'seed_bytes':len(seed_bytes),'all_packaged_files_verified':len(verified),'private_payload_only':True},indent=2)+'\n')
    wheels=Path(tmp)/'wheels'
    wheel_command=['/Users/kumar0002/.local/bin/uv','build','--offline','--wheel','--python',str(Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-cinema-final-20261024/.runtime/casepath-dev-v2/venv/bin/python')),'--out-dir',str(wheels),str(unpacked/'casepath-api')]
    with (BASE/'api-private-wheel.log').open('x') as log:
        subprocess.run(wheel_command,stdout=log,stderr=subprocess.STDOUT,check=True)
    built=list(wheels.glob('*.whl'));assert len(built)==1
    with zipfile.ZipFile(built[0]) as wheel:
        seed_members=[name for name in wheel.namelist() if name.endswith('hosted-read-seed-v1.json')]
        assert seed_members==['casepath_api/artifacts/hosted-read-seed-v1.json']
        assert wheel.read(seed_members[0])==seed_bytes
        metadata_members=[name for name in wheel.namelist() if name.endswith('.dist-info/METADATA')]
        assert len(metadata_members)==1
        from email.parser import Parser
        metadata=Parser().parsestr(wheel.read(metadata_members[0]).decode('utf-8'))
        pillow_requirements=[value for value in metadata.get_all('Requires-Dist',[]) if value.lower().startswith('pillow')]
        assert len(pillow_requirements)==1 and pillow_requirements[0].replace(' ','').lower()=='pillow==13.0.0'

    (BASE/'api-private-wheel-verified.json').write_text(json.dumps({'canonical_commit':SHA,'wheel_sha256':hashlib.sha256(built[0].read_bytes()).hexdigest(),'private_seed_sha256':seed_receipt['sha256'],'exact_private_seed_installed':True,'pillow_requirement':pillow_requirements[0],'pillow_security_version':'13.0.0'},indent=2)+'\n')
    size=path.stat().st_size
    require_completed_gate(BASE,SHA)
    with APIClient() as c:
        c.timeout=httpx.Timeout(90)
        attempt.write_text(json.dumps({'source_commit':SHA,'app_id':APP,'status':'creation_requested','archive_bytes':size,'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2)+'\n')
        deployment=_create_deployment(c,APP,size)
        safe={'source_commit':SHA,'deployment_id':deployment.id,'status':str(deployment.status),'archive_bytes':size,'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        receipt.write_text(json.dumps(safe,indent=2)+'\n');attempt.write_text(json.dumps({**safe,'status':'created'},indent=2)+'\n');print(json.dumps(safe),flush=True)
        r=c.post(f'/deployments/{deployment.id}/upload');r.raise_for_status();u=RequestUploadResponse.model_validate(r.json())
        with httpx.Client(timeout=90, trust_env=False) as upload, path.open('rb') as f:
            try:
                response=upload.post(u.url,data=u.fields,files={'file':f})
                response.raise_for_status()
            except httpx.HTTPError as error:
                code=getattr(getattr(error,'response',None),'status_code',None)
                raise RuntimeError(f'Archive upload failed ({type(error).__name__}, HTTP {code}); reconcile created deployment before retrying') from None
        r=c.post(f'/deployments/{deployment.id}/upload-complete');r.raise_for_status()
        safe.update(status=r.json()['status'],upload_http=response.status_code)
        (BASE/'api-deployment-uploaded.json').write_text(json.dumps(safe,indent=2)+'\n');print(json.dumps(safe),flush=True)

