"""Reversible native wire codec. Selectors COPY objects; no hidden inference.

Source-only prototypes are explicitly selected, never automatically included.
Every document row specifies its state and request mode. Literal row/field
escapes preserve arbitrary native objects, confidence and provenance choices.
The native projection itself still loses planning route/joint-adequacy detail.
"""
from __future__ import annotations
import copy
import sys
import re
from ..wire import canonical, digest, Invalid

FAMILIES={'c':'concepts','r':'relations','b':'branch_predicates','d':'documents'}
KEY={'c':'concept_id','r':'relation_id','b':'predicate_id','d':'item_id'}
STATES=['provided_sufficient','provided_insufficient','missing','conditional','irrelevant','unknown']
MODES=['now','conditional','none']
PRESENCE=['present','missing','unknown']


def integer(value, size):
    if type(value) is not int or not 0 <= value < size:raise Invalid('invalid codebook index')
    return value


class Book:
    def __init__(self, preparation, case, native):
        self.preparation=preparation;self.case=case;self.native=native
        self.source_refs=sorted(case['registry']);self.material_ids=sorted(case['visible']['materials'])
        self.variables=sorted(preparation['prepared']['control']['variables'])
        self.documents=sorted({d for c in preparation['prepared']['capabilities'] for r in c['routes'] for d in r['document_ids']})
        self.capabilities=preparation['prepared']['capabilities']
        unknown={'contract':'casepath.observation-state/1.0.0','case_id':'live_case','materials':{},'guard_verdicts':{},
          'evidence':{'documents':{},'slot_assessments':[],'joint_assessments':[]},'origin':'engineering_fixture','inference_receipt_sha256':None}
        prototype=native.validate(preparation['runtime'].run(unknown)['native_artifact'])
        self.tables={k:prototype[v] for k,v in FAMILIES.items()}
        self.by_id={k:{r[KEY[k]]:i for i,r in enumerate(rows)} for k,rows in self.tables.items()}
        self.expression_originals=list(dict.fromkeys(r['expression'] if tag=='b' else r['active_when'] for tag in ('c','r','b','d') for r in self.tables[tag]))
        self.identity=digest({'tables':self.tables,'source_refs':self.source_refs,'variables':self.variables,
                'material_ids':self.material_ids,'documents':self.documents,'prepared':preparation['manifest']['prepared_sha256']})
        locator_type=sys.modules[native.candidate_type.__module__].SourceLocator
        self.locator_values=[locator_type.model_validate(case['registry'][r]['locator']).model_dump(mode='json') for r in self.source_refs]
        self.locator_ids={digest(loc):i for i,loc in enumerate(self.locator_values)}

    def _prov_encode(self, row):
        row=copy.deepcopy(row)
        if 'provenance' in row:
            refs=[]
            for loc in row['provenance']:
                key=digest(loc)
                # Literal native locators remain possible; no vocabulary contraction.
                refs.append(self.locator_ids[key] if key in self.locator_ids else {'literal':loc})
            row['provenance']=refs
        return row

    def symbol(self,value,*,expression=False):
        if not isinstance(value,dict):return copy.deepcopy(value)
        if len(value)!=1:raise Invalid('invalid symbol reference')
        kind,index=next(iter(value.items()))
        if expression and kind=='e':return self.expression_originals[integer(index,len(self.expression_originals))]
        if expression and kind=='formula':
            if not isinstance(index,str) or len(index)>8192:raise Invalid('invalid alias formula')
            return re.sub(r'\bv([0-9]+)\b',lambda m:self.variables[integer(int(m.group(1)),len(self.variables))],index)
        if not expression and kind in FAMILIES:return self.tables[kind][integer(index,len(self.tables[kind]))][KEY[kind]]
        raise Invalid('invalid symbol kind')

    def _prov_decode(self,row):
        row=copy.deepcopy(row)
        if 'provenance' in row:
            out=[]
            for ref in row['provenance']:
                if type(ref) is int:out.append(copy.deepcopy(self.locator_values[integer(ref,len(self.locator_values))]))
                elif isinstance(ref,dict) and set(ref)=={'literal'}:out.append(copy.deepcopy(ref['literal']))
                else:raise Invalid('invalid provenance reference')
            row['provenance']=out
        for key in ('active_when','expression'):
            if key in row:row[key]=self.symbol(row[key],expression=True)
        for key in ('source_id','target_id','concept_id','item_id','predicate_id','relation_id'):
            if key in row:row[key]=self.symbol(row[key])
        return row

    def encode_native(self,artifact):
        obj=self.native.validate(artifact)
        if obj['case_id'] not in {'live_case',self.case['case_id']}:raise Invalid('cross-case native artifact')
        out={'kind':'native','c':[],'r':[],'b':[],'d':[], 't':obj['terminal_outcome_ids'],'a':obj['abstained_concept_ids']}
        for tag,family in FAMILIES.items():
            for row in obj[family]:
                index=self.by_id[tag].get(row[KEY[tag]])
                if index is None:out[tag].append({'literal':self._prov_encode(row)});continue
                base=self.tables[tag][index];changes={k:v for k,v in row.items() if k not in base or base[k]!=v}
                removed=sorted(set(base)-set(row))
                if tag=='d':
                    changes.pop('state',None);changes.pop('request_mode',None)
                    entry=[index,STATES.index(row['state']),MODES.index(row['request_mode'])]
                    if changes or removed:entry.append({'set':self._prov_encode(changes),'remove':removed})
                elif not changes and not removed:entry=index
                else:entry=[index,{'set':self._prov_encode(changes),'remove':removed}]
                out[tag].append(entry)
        return out

    def decode_native(self,wire):
        if not isinstance(wire,dict) or set(wire)!= {'kind','c','r','b','d','t','a'} or wire['kind']!='native':raise Invalid('complete compact native artifact required')
        out={'artifact_version':'casepath.candidate-artifact/0.1.0','case_id':self.case['case_id'],
             'terminal_outcome_ids':[self.symbol(x) for x in wire['t']],'abstained_concept_ids':[self.symbol(x) for x in wire['a']]}
        for tag,family in FAMILIES.items():
            if not isinstance(wire[tag],list) or len(wire[tag])>2048:raise Invalid('invalid native row family')
            rows=[]
            for entry in wire[tag]:
                if isinstance(entry,dict) and set(entry)=={'literal'}:row=self._prov_decode(entry['literal'])
                else:
                    if tag=='d':
                        if not isinstance(entry,list) or len(entry) not in (3,4):raise Invalid('document state/mode must be explicit')
                        row=copy.deepcopy(self.tables[tag][integer(entry[0],len(self.tables[tag]))])
                        row['state']=STATES[integer(entry[1],len(STATES))];row['request_mode']=MODES[integer(entry[2],len(MODES))]
                        patch=entry[3] if len(entry)==4 else None
                    else:
                        if type(entry) is int:index=entry;patch=None
                        elif isinstance(entry,list) and len(entry)==2:index,patch=entry
                        else:raise Invalid('invalid native selector')
                        row=copy.deepcopy(self.tables[tag][integer(index,len(self.tables[tag]))])
                    if patch is not None:
                        if not isinstance(patch,dict) or set(patch)!= {'set','remove'} or not isinstance(patch['set'],dict) or not isinstance(patch['remove'],list):raise Invalid('invalid explicit field correction')
                        for field in patch['remove']:
                            if not isinstance(field,str) or field not in row:raise Invalid('cannot remove missing field')
                            del row[field]
                        row.update(self._prov_decode(patch['set']))
                rows.append(row)
            out[family]=rows
        return self.native.validate(out)

    def encode_state(self,value):
        guard=value['guard_verdicts'];evidence=value['evidence'];material=self.case['visible']['materials']
        if set(guard)!=set(self.variables) or set(evidence['documents'])!=set(self.documents):raise Invalid('complete assessment required')
        g=[]
        for var in self.variables:
            v=guard[var];source=v['source_id'];quote=v['quote']
            if source is None:loc=None
            else:
                if source not in material or not isinstance(quote,str) or quote not in material[source]:raise Invalid('quote not in source')
                start=material[source].find(quote);loc=[self.material_ids.index(source),start,start+len(quote)]
            g.append([v['value'],loc])
        d=[]
        for doc in self.documents:
            row=evidence['documents'][doc]
            d.append([PRESENCE.index(row['presence']),STATES.index(row['native_state']),[self.material_ids.index(s) for s in row['source_refs']]])
        cap_index={c['capability_id']:i for i,c in enumerate(self.capabilities)}
        s=[];j=[]
        for family, dest in [('slot_assessments',s),('joint_assessments',j)]:
            for row in evidence[family]:
                ci=cap_index[row['capability_id']];routes=self.capabilities[ci]['routes'];ri=[r['route_id'] for r in routes].index(row['route_id'])
                prefix=[ci,ri]+([self.documents.index(row['document_id'])] if family=='slot_assessments' else [])
                dest.append(prefix+[row['adequate'],[self.material_ids.index(x) for x in row['source_refs']]])
        return {'kind':'state','g':g,'d':d,'s':s,'j':j}

    def decode_state(self,wire):
        if not isinstance(wire,dict) or set(wire)!= {'kind','g','d','s','j'} or wire['kind']!='state':raise Invalid('invalid compact assessment')
        if len(wire['g'])!=len(self.variables) or len(wire['d'])!=len(self.documents):raise Invalid('incomplete assessment')
        guard={};evidence={'documents':{},'slot_assessments':[],'joint_assessments':[]}
        for var,row in zip(self.variables,wire['g']):
            if not isinstance(row,list) or len(row)!=2 or row[0] is not None and type(row[0]) is not bool:raise Invalid('invalid ternary assessment')
            loc=row[1];source=quote=None
            if loc is not None:
                if not isinstance(loc,list) or len(loc)!=3:raise Invalid('invalid quote coordinates')
                source=self.material_ids[integer(loc[0],len(self.material_ids))];text=self.case['visible']['materials'][source]
                start,end=loc[1:]
                if type(start) is not int or type(end) is not int or not 0<=start<end<=len(text):raise Invalid('invalid quote span')
                quote=text[start:end]
            if row[0] is not None and quote is None:raise Invalid('decided state lacks case quote')
            guard[var]={'value':row[0],'source_id':source,'quote':quote}
        def material_refs(values):
            if not isinstance(values,list):raise Invalid('source list required')
            return [self.material_ids[integer(i,len(self.material_ids))] for i in values]
        for doc,row in zip(self.documents,wire['d']):
            if not isinstance(row,list) or len(row)!=3:raise Invalid('document assessment row shape')
            evidence['documents'][doc]={'presence':PRESENCE[integer(row[0],len(PRESENCE))], 'native_state':STATES[integer(row[1],len(STATES))],'source_refs':material_refs(row[2])}
        for key,family in [('s','slot_assessments'),('j','joint_assessments')]:
            if not isinstance(wire[key],list):raise Invalid('assessment array required')
            for row in wire[key]:
                n=5 if key=='s' else 4
                if not isinstance(row,list) or len(row)!=n:raise Invalid('adequacy row shape')
                cap=self.capabilities[integer(row[0],len(self.capabilities))];route=cap['routes'][integer(row[1],len(cap['routes']))]
                v=row[-2]
                if v is not None and type(v) is not bool:raise Invalid('invalid adequacy truth')
                item={'capability_id':cap['capability_id'],'route_id':route['route_id'],'adequate':v,'source_refs':material_refs(row[-1])}
                if key=='s':item['document_id']=self.documents[integer(row[2],len(self.documents))]
                evidence[family].append(item)
        return {'guard_verdicts':guard,'evidence':evidence}

    def output_semantics(self,output):
        if output.get('kind')=='native':return self.decode_native(output)
        if output.get('kind')=='state':return self.decode_state(output)
        raise Invalid('unknown model output kind')
