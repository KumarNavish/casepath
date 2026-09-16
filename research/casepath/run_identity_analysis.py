"""Build a checkable sidecar for the historical interpreter/reference runs."""
from pathlib import Path
import hashlib, json, re

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/'research/casepath'; A=R/'artifacts'; API=ROOT/'casepath-api/casepath_api'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(name):
    d=json.loads((A/name).read_text()); return len(d),len({x['unit_id'] for x in d})
shared={x:sha(API/x) for x in ['process_experiment_v1.py','checklist_baselines_v1.py','case_interpreter_v1.py','obligation_compiler_v1.py']}
configs=[
 ('gpt-5.6-terra','conf_arms.json','runners/conf_arms.py','openai/gpt-5.6-terra','openai'),
 ('claude-haiku-4.5','mm_haiku.json','runners/multimodel.py','anthropic/claude-haiku-4.5',None),
 ('gemini-2.5-flash','mm_gemini.json','runners/multimodel.py','google/gemini-2.5-flash',None),
 ('deepseek-v3.2','mm_deepseek.json','runners/multimodel.py','deepseek/deepseek-v3.2',None),
]
out={'contract':'casepath.run-identity/1.0.0','shared_prompt_code_sha256':shared,'runs':{}}
for tag,artifact,runner,model,provider in configs:
    n,u=rows(artifact); d=json.loads((A/artifact).read_text())
    embedded=sorted({x.get('model') for x in d if x.get('model')})
    out['runs'][tag]={'artifact':f'research/casepath/artifacts/{artifact}','artifact_sha256':sha(A/artifact),
      'rows':n,'unique_units':u,'complete_58_unit_roster':n==u==58,'runner':f'research/casepath/{runner}',
      'runner_sha256':sha(R/runner),'model_from_runner':model,'provider_constraint':provider,
      'model_values_embedded_in_rows':embedded,'temperature':0.0,'max_tokens':8000}
ref=json.loads((A/'conf_ref_raw.json').read_text())
out['reference_adjudication']={
  'artifact':'research/casepath/artifacts/conf_ref_raw.json','artifact_sha256':sha(A/'conf_ref_raw.json'),
  'rows':len(ref),'unique_units':len({x['unit_id'] for x in ref}),'repeats_per_unit':3,
  'runner':'research/casepath/runners/conf_ref.py','runner_sha256':sha(R/'runners/conf_ref.py'),
  'system_prompt':'research/casepath/prompts/reference_adjudication_system.txt',
  'system_prompt_sha256':sha(R/'prompts/reference_adjudication_system.txt'),
  'model_from_runner':'openai/gpt-5.6-terra','provider_constraint':'openai','temperature':0.0,'max_tokens':8000,
}
out['limitation']='Historical arm runners persisted final successful unit outputs, not a per-call transport/error ledger. A 58/58 final roster proves no unit is missing from each committed artifact, but transient retries or failed calls before a final output cannot be reconstructed.'
(A/'RUN_IDENTITY.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,indent=2))
