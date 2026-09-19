"""Review may retain or edit its exact generated draft without reprinting it.

A complete replacement remains allowed with the unchanged response allowance.
No reference, evaluator value, or hand-authored artifact is the edit base.
"""
from __future__ import annotations
import copy
from .wire import canonical, decode, sha, Invalid

CONTRACT='casepath.exact-draft-review/1.0.0'
INSTRUCTION='''You may return the COMPLETE final object as requested, or a review envelope:
{"review_contract":"casepath.exact-draft-review/1.0.0","edits":[{"op":"add|remove|replace","path":"/JSON/pointer","value":...}]}
The edit base is exactly PRIOR_ANALYSIS from this same claim and arm, never a template or another case.
An empty edits list preserves that entire draft. This is valid ONLY if it already is the COMPLETE required final object.
Each operation is sequential. Use standard JSON Pointer escaping (~0 for ~ and ~1 for /); use /- only to append to an array.
You may replace the root with path ""; a full replacement remains permitted.
Review all the original quality criteria and all source/case material. Do not omit corrections to save tokens.
The resulting object, not just the edits, must contain every required final field and pass the unchanged native contract.
'''


def _parts(path: str) -> list[str]:
    if not isinstance(path,str) or (path and not path.startswith('/')):
        raise Invalid('invalid review pointer')
    out=[]
    for part in path.split('/')[1:]:
        i=0
        while i<len(part):
            if part[i]=='~':
                if i+1>=len(part) or part[i+1] not in '01':raise Invalid('invalid pointer escape')
                i+=2
            else:i+=1
        out.append(part.replace('~1','/').replace('~0','~'))
    return out


def _idx(part:str, size:int, *, add:bool=False)->int:
    if part=='-' and add:return size
    if not part.isascii() or not part.isdigit() or (len(part)>1 and part[0]=='0'):
        raise Invalid('invalid array index')
    i=int(part)
    if not 0<=i<=(size if add else size-1):raise Invalid('array index out of range')
    return i


def apply_review(prior_raw:bytes, review_raw:bytes, max_bytes:int)->tuple[dict,dict]:
    review=decode(review_raw)
    if not isinstance(review,dict):raise Invalid('review must be a JSON object')
    if 'review_contract' not in review:
        value=review; mode='full_replacement'
    else:
        if set(review)!={'review_contract','edits'} or review['review_contract']!=CONTRACT:
            raise Invalid('invalid review envelope')
        edits=review['edits']
        if not isinstance(edits,list) or len(edits)>512:raise Invalid('invalid edit count')
        value=copy.deepcopy(decode(prior_raw));mode='exact_generated_draft_edits'
        for edit in edits:
            if not isinstance(edit,dict):raise Invalid('edit must be an object')
            op=edit.get('op')
            required={'op','path'} | ({'value'} if op in ('add','replace') else set())
            if op not in ('add','remove','replace') or set(edit)!=required:raise Invalid('unsupported review edit')
            path=_parts(edit['path'])
            if not path:
                if op=='remove':raise Invalid('cannot remove final root')
                value=copy.deepcopy(edit['value']);continue
            parent=value
            for part in path[:-1]:
                if isinstance(parent,dict):
                    if part not in parent:raise Invalid('missing review ancestor')
                    parent=parent[part]
                elif isinstance(parent,list):parent=parent[_idx(part,len(parent))]
                else:raise Invalid('non-container review ancestor')
            key=path[-1]
            if isinstance(parent,dict):
                if op!='add' and key not in parent:raise Invalid('missing review target')
                if op=='remove':del parent[key]
                else:parent[key]=copy.deepcopy(edit['value'])
            elif isinstance(parent,list):
                index=_idx(key,len(parent),add=op=='add')
                if op=='add':parent.insert(index,copy.deepcopy(edit['value']))
                elif op=='remove':del parent[index]
                else:parent[index]=copy.deepcopy(edit['value'])
            else:raise Invalid('non-container review target')
            if len(canonical(value))>max_bytes:raise Invalid('expanded review exceeds retained artifact byte bound')
    if not isinstance(value,dict) or len(canonical(value))>max_bytes:
        raise Invalid('final review is not a complete bounded object')
    return value, {'contract':CONTRACT,'mode':mode,'base_sha256':sha(prior_raw),'review_sha256':sha(review_raw),
                   'expanded_sha256':sha(canonical(value)), 'source':'same_claim_same_arm_generated_draft',
                   'native_validation_still_required':True}
