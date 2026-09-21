"""Publish the descriptive error partition; does not rescore model outputs."""
from pathlib import Path
import hashlib,json
here=Path(__file__).resolve().parent
raw=(here/'SPURIOUS_ORIGIN.json').read_bytes(); data=json.loads(raw); audit=[]; lines=[]
assert data['schema']=='casepath.spurious-origin/2'
for arm,tag in [('b5_process_compiled','Cp'),('b1_direct','Dir'),('b3_representation_then_list','Gc'),('b6_evidence_first','Ef')]:
    value=data['arms'][arm]['not_branch_governed']; name='eo'+tag+'Outside'
    lines.append('\\newcommand{\\'+name+'}{'+str(value)+'}')
    audit.append(dict(macro=name,value=value,source='SPURIOUS_ORIGIN.json',source_sha256=hashlib.sha256(raw).hexdigest(),json_pointer='/arms/'+arm+'/not_branch_governed'))
(here.parent/'error_origin_numbers.tex').write_text('\n'.join(lines)+'\n')
(here/'ERROR_ORIGIN_NUMERICAL_AUDIT.json').write_text(json.dumps({'numbers':audit},indent=2)+'\n')
print('Four error-origin counts bound to the descriptive report.')
